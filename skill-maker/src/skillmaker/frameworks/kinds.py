#!/usr/bin/env python3
"""
kinds.py -- the publication-kind vocabulary the decomposer dispatches on.

A published Library classifies each of its publications with one ``kind``
value.  The current catalogue uses exactly four:

===========  ============================================================
``FPF``      FPF Core -- the shared pattern language (``FPF-Spec.md``)
``DPF``      A domain principles framework (33 publications)
``Reference``A DPF Suite Architectural Reference (4 publications)
``Guide``    An introduction or working instruction (8 publications)
===========  ============================================================

That vocabulary is the starting point, not the limit.  A framework that FPF
Library does not publish still has a *kind*, and the toolchain must be able to
decompose it: an architecture decision record set, a clause-numbered standard,
an Alexander-style pattern language, or plain Markdown with no identifiers at
all.  :class:`PublicationKind` therefore carries both the four published kinds
and the extension kinds the engine already knows how to handle.

Adding a kind is a two-step change:

1. add the member here with its :class:`KindInfo` facts;
2. add a :class:`~frameworks.profile.DecompositionProfile` under
   ``frameworks/profiles/`` that states the unit grammar and the skill shape.

Nothing else in the engine needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class PublicationKind(str, Enum):
    """Every kind of framework document the toolchain can decompose."""

    # --- kinds in the published Library catalogue -------------------------
    FPF = "FPF"
    DPF = "DPF"
    REFERENCE = "Reference"
    GUIDE = "Guide"

    # --- extension kinds (not in the Library catalogue) -------------------
    ADR = "ADR"
    STANDARDS = "Standards"
    PATTERN_LANGUAGE = "PatternLanguage"
    GENERIC = "Generic"


@dataclass(frozen=True)
class KindInfo:
    """What a kind *is*, independent of how a particular document is shaped."""

    kind: PublicationKind
    label: str
    """Short human label for tables and CLI output."""

    summary: str
    """One sentence: what the reader gets from a publication of this kind."""

    addressable: bool
    """True when the publication publishes its own unit identifiers.

    An addressable publication can be cited unit by unit (``SYSE.24``,
    ``Library.Reference:11.1``); a guide usually cannot."""

    pattern_bearing: bool
    """True when its units may be patterns rather than prose sections."""

    in_library: bool
    """True for the kinds the FPF Library catalogue publishes today."""


KINDS: Dict[PublicationKind, KindInfo] = {
    PublicationKind.FPF: KindInfo(
        kind=PublicationKind.FPF,
        label="FPF Core",
        summary="The shared pattern language: kernel concepts, calculi and "
                "cross-domain methods.",
        addressable=True,
        pattern_bearing=True,
        in_library=True,
    ),
    PublicationKind.DPF: KindInfo(
        kind=PublicationKind.DPF,
        label="Domain Principle Framework",
        summary="A domain pattern language: connected patterns for one field "
                "of practice, with conditions and worked cases.",
        addressable=True,
        pattern_bearing=True,
        in_library=True,
    ),
    PublicationKind.REFERENCE: KindInfo(
        kind=PublicationKind.REFERENCE,
        label="Suite Architectural Reference",
        summary="The composition of a DPF Suite: which disciplines contribute "
                "what, and how their contributions meet in one decision.",
        addressable=True,
        pattern_bearing=False,
        in_library=True,
    ),
    PublicationKind.GUIDE: KindInfo(
        kind=PublicationKind.GUIDE,
        label="Guide",
        summary="An introduction or working instruction: how to choose, read "
                "and apply the publications.",
        addressable=False,
        pattern_bearing=False,
        in_library=True,
    ),
    PublicationKind.ADR: KindInfo(
        kind=PublicationKind.ADR,
        label="Architecture Decision Record",
        summary="A numbered decision record: context, decision, consequences "
                "and status.",
        addressable=True,
        pattern_bearing=False,
        in_library=False,
    ),
    PublicationKind.STANDARDS: KindInfo(
        kind=PublicationKind.STANDARDS,
        label="Standards document",
        summary="A clause-numbered normative document: requirements, terms "
                "and conformance.",
        addressable=True,
        pattern_bearing=False,
        in_library=False,
    ),
    PublicationKind.PATTERN_LANGUAGE: KindInfo(
        kind=PublicationKind.PATTERN_LANGUAGE,
        label="Pattern language",
        summary="A numbered pattern language in the Alexander tradition: "
                "context, problem, forces, solution.",
        addressable=True,
        pattern_bearing=True,
        in_library=False,
    ),
    PublicationKind.GENERIC: KindInfo(
        kind=PublicationKind.GENERIC,
        label="Generic Markdown",
        summary="Any Markdown document: headings become sections, no "
                "identifiers are assumed.",
        addressable=False,
        pattern_bearing=False,
        in_library=False,
    ),
}


#: Catalogue kind strings, as served by ``/api/publications``.
CATALOGUE_KINDS: Tuple[str, ...] = tuple(
    info.kind.value for info in KINDS.values() if info.in_library
)


def kind_from_catalogue(value: str) -> PublicationKind:
    """Map a catalogue ``kind`` string to a :class:`PublicationKind`.

    Raises ``KeyError`` with the known values listed, because an unknown kind
    is a signal that the catalogue grew a kind this toolchain cannot decompose
    yet -- not something to paper over with a default.
    """
    for kind in PublicationKind:
        if kind.value.lower() == value.strip().lower():
            return kind
    raise KeyError(
        f"unknown publication kind {value!r}; known kinds: "
        + ", ".join(k.value for k in PublicationKind)
    )


def info(kind: PublicationKind) -> KindInfo:
    """Look up the facts for *kind*."""
    return KINDS[kind]


def describe(kind: PublicationKind) -> str:
    """One-line description used by the ``kinds`` CLI subcommand."""
    k = KINDS[kind]
    flags = []
    if k.addressable:
        flags.append("addressable")
    if k.pattern_bearing:
        flags.append("patterns")
    if k.in_library:
        flags.append("library")
    return f"{k.kind.value:<16} {k.label:<32} {', '.join(flags):<26} {k.summary}"
