#!/usr/bin/env python3
"""
profile.py -- one framework kind, end to end.

A :class:`DecompositionProfile` is the unit of extension for the toolchain.  It
bundles the four things a new framework type needs:

1. **identity** -- which :class:`~frameworks.kinds.PublicationKind` it is;
2. **detection** -- the path globs and header markers that recognise it;
3. **grammar** -- how its headings split into addressable units
   (:class:`~frameworks.grammar.UnitGrammar`);
4. **shape** -- what the decomposition produces
   (:class:`~frameworks.shape.SkillShape`).

A profile that resolves its ID prefix from the publication's own ``DocID``
covers a whole family: one ``dpf_framework`` profile serves all 33 DPFs, and one
``suite_reference`` profile serves all 4 Suite References.

Detection is scored, not guessed.  Path globs are decisive for documents the
Library publishes under known names; header markers and structural evidence
take over for documents it does not (a third-party DPF, an ADR set, a
standard).  The score and its reasons are reported by ``probe`` so a surprising
classification can be explained rather than merely observed.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .grammar import UnitGrammar, docid_of, heading_level
from .kinds import KindInfo, PublicationKind, info as kind_info
from .shape import SkillShape


@dataclass(frozen=True)
class Detection:
    """Why one profile was chosen (or rejected) for a document."""

    profile_key: str
    score: int
    reasons: Tuple[str, ...] = ()

    def describe(self) -> str:
        return f"{self.profile_key} (score {self.score}: {', '.join(self.reasons) or 'fallback'})"


def _glob_specificity(glob: str) -> int:
    """How much literal text a glob pins down.

    Used to break ties between overlapping globs without hard-coding an order:
    ``**/README.md`` (10 literal chars) is more specific than ``DPFs/*.md`` (8),
    so a Suite README is a guide rather than a DPF.
    """
    return len(re.sub(r"[*?\[]", "", glob))


def _match_ratio(grammar: UnitGrammar, text: str, limit: int = 200_000) -> float:
    """Fraction of unit-level headings that the grammar recognises.

    A cheap structural signal: a standards document is recognised because its
    ``##`` headings are clause numbers, not because of its file name.
    """
    if grammar.id_pattern is None:
        # A grammar with no identifier requirement matches every heading, so it
        # carries no discriminating evidence.  Without this guard the DPF
        # profile would "match" a README perfectly and outrank the guide
        # profile on structure alone.
        return 0.0

    head = text[:limit]
    total = 0
    matched = 0
    for line in head.splitlines():
        if heading_level(line) != grammar.unit_level:
            continue
        total += 1
        if total > 400:            # enough evidence; do not scan 17 MB
            break
        m = grammar.heading_re.match(line)
        if m:
            matched += 1
        elif grammar.bare_heading_re is not None and grammar.bare_heading_re.match(line):
            matched += 1
    if total < 3:
        # One or two headings is a coincidence, not a grammar.
        return 0.0
    return matched / total


@dataclass(frozen=True)
class DecompositionProfile:
    """Everything the toolchain knows about one kind of framework document."""

    key: str
    """Stable identifier, e.g. ``dpf-framework``."""

    kind: PublicationKind
    """The publication kind this profile decomposes."""

    name: str
    """Human label."""

    description: str
    """One sentence: what a decomposition of this kind produces."""

    grammar: UnitGrammar
    """The heading grammar, possibly unbound (see :attr:`docid_prefix`)."""

    shape: SkillShape
    """The artefact set the decomposition produces."""

    path_globs: Tuple[str, ...] = ()
    """Repo-relative globs that identify this kind by path."""

    header_markers: Tuple[str, ...] = ()
    """Substrings in the document header that identify this kind."""

    docid_prefix: bool = False
    """Resolve the ID prefix from the publication's own ``DocID``.

    One profile then serves every member of a family (all 33 DPFs)."""

    fixed_prefix: Optional[str] = None
    """A constant ID prefix, for publications whose IDs do not match their
    DocID (FPF Core declares ``DocID: FPF`` but publishes ``A.1``...)."""

    structural: bool = True
    """Use heading-shape evidence when scoring."""

    def kind_info(self) -> KindInfo:
        return kind_info(self.kind)

    # --- grammar resolution ----------------------------------------------
    def grammar_for(self, text: str) -> UnitGrammar:
        """Bind the grammar to this publication's identifiers."""
        if self.fixed_prefix:
            return self.grammar.for_prefix(self.fixed_prefix)
        if self.docid_prefix:
            docid = docid_of(text)
            if docid:
                return self.grammar.for_prefix(re.escape(docid))
            inferred = self._infer_prefix(text)
            if inferred:
                return self.grammar.for_prefix(re.escape(inferred))
        return self.grammar

    def _infer_prefix(self, text: str) -> str:
        """Fall back to the first dotted identifier in the document.

        A DPF that forgot its ``DocID`` header still publishes ``XYZ.1``
        headings; the prefix is recoverable from the first one.
        """
        m = re.search(r"^##\s+(?:\*\*)?([A-Za-z][A-Za-z0-9]*)\.[A-Za-z0-9]",
                      text[:400_000], re.MULTILINE)
        return m.group(1) if m else ""

    # --- detection --------------------------------------------------------
    def detect(self, path: str, text: str) -> Detection:
        """Score this profile against one document."""
        score = 0
        reasons: List[str] = []

        best_glob = ""
        for glob in self.path_globs:
            if fnmatch.fnmatch(path, glob) and _glob_specificity(glob) > _glob_specificity(best_glob):
                best_glob = glob
        if best_glob:
            score += 100 + _glob_specificity(best_glob)
            reasons.append(f"path~{best_glob}")

        head = text[:6000]
        for marker in self.header_markers:
            if marker in head:
                score += 25
                reasons.append(f"header:{marker!r}")

        if self.structural:
            grammar = self.grammar_for(text)
            ratio = _match_ratio(grammar, text)
            if ratio >= 0.5:
                score += int(40 * ratio)
                reasons.append(f"headings {ratio:.0%}")
            elif ratio > 0:
                reasons.append(f"headings {ratio:.0%}")

        return Detection(profile_key=self.key, score=score, reasons=tuple(reasons))

    # --- presentation -----------------------------------------------------
    def describe(self) -> str:
        return (f"{self.key:<20} {self.kind.value:<16} {self.shape.layout.value:<11} "
                f"{self.description}")


def best(candidates: List[Tuple[DecompositionProfile, Detection]],
         ) -> Tuple[Optional[DecompositionProfile], Detection]:
    """Pick the highest-scoring profile; ties keep registration order.

    Registration order runs from most specific to most general, so a tie is
    resolved in favour of the narrower kind.
    """
    if not candidates:
        return None, Detection("", 0, ())
    return max(enumerate(candidates),
               key=lambda item: (item[1][1].score, -item[0]))[1]
