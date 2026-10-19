#!/usr/bin/env python3
"""
decompose.py -- turn one framework document into addressable units.

The decomposer is deliberately smaller than the skill builder in
``split_spec.py``: it does not write files, read tables of contents or build
indexes.  It answers one question -- *what are the units of this document, and
what is each one for* -- for any framework kind, so that the answer can be
inspected, compared and planned before anything is generated.

That separation is what makes the toolchain general.  ``split_spec`` knows how
to emit one particular skill layout; :class:`Decomposer` knows how to read
arbitrary frameworks, and the two meet at :class:`UnitTree`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_MAKER_DIR = Path(__file__).resolve().parent.parent
if str(_MAKER_DIR) not in sys.path:
    sys.path.insert(0, str(_MAKER_DIR))

from _fpf_common import FenceTracker, clean  # noqa: E402

from .grammar import UnitGrammar, heading_level, split_heading
from .profile import DecompositionProfile


@dataclass
class Unit:
    """One addressable unit: a heading and the body it owns."""

    id: str
    title: str
    role: str
    level: int
    start: int
    """1-based line number of the unit heading."""

    end: int
    """1-based line number of the first line *after* the unit (exclusive)."""

    part: str = ""
    """Enclosing part divider, when the document has one."""

    subsections: int = 0
    """Number of nested headings inside the unit."""

    @property
    def lines(self) -> int:
        return max(0, self.end - self.start)

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "title": self.title, "role": self.role,
            "level": self.level, "start": self.start, "end": self.end,
            "part": self.part, "subsections": self.subsections,
            "lines": self.lines,
        }


@dataclass
class UnitTree:
    """The decomposition of one document."""

    path: str
    title: str
    profile: DecompositionProfile
    grammar: UnitGrammar
    units: List[Unit] = field(default_factory=list)
    parts: List[Tuple[int, str]] = field(default_factory=list)
    intros: List[Tuple[int, str]] = field(default_factory=list)
    """Headings that are not units (contents, prefaces, dividers)."""

    headings: int = 0
    line_count: int = 0

    # --- views ------------------------------------------------------------
    @property
    def patterns(self) -> List[Unit]:
        return [u for u in self.units if u.role == "pattern"]

    @property
    def references(self) -> List[Unit]:
        return [u for u in self.units if u.role != "pattern"]

    def by_role(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for unit in self.units:
            out[unit.role] = out.get(unit.role, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    def ids(self) -> List[str]:
        return [u.id for u in self.units]

    def filenames(self) -> List[str]:
        return [self.grammar.filename(u.id, u.title) for u in self.units]

    def stats(self) -> Dict:
        return {
            "path": self.path,
            "title": self.title,
            "profile": self.profile.key,
            "kind": self.profile.kind.value,
            "units": len(self.units),
            "patterns": len(self.patterns),
            "references": len(self.references),
            "roles": self.by_role(),
            "parts": len(self.parts),
            "headings": self.headings,
            "lines": self.line_count,
        }


class Decomposer:
    """Split a document into units using one profile's grammar."""

    def __init__(self, profile: DecompositionProfile):
        self.profile = profile

    def run(self, text: str, path: str = "") -> UnitTree:
        grammar = self.profile.grammar_for(text)
        lines = text.splitlines()
        tree = UnitTree(path=path, title="", profile=self.profile,
                        grammar=grammar, line_count=len(lines))

        fence = FenceTracker()
        current: Optional[Unit] = None
        part = ""
        seen_title = False
        part_level = grammar.part_level
        subsection_levels = {lvl for lvl in range(grammar.unit_level + 1, 7)}

        def close(at: int) -> None:
            nonlocal current
            if current is not None:
                current.end = at
                tree.units.append(current)
                current = None

        for lineno, line in enumerate(lines, 1):
            in_code = fence.in_fence
            level = 0 if in_code else heading_level(line)
            if level:
                tree.headings += 1

            if level == 1 and not in_code:
                title = clean(line[1:].strip())
                if not seen_title:
                    tree.title = title
                    seen_title = True
                elif part_level == 1:
                    close(lineno)
                    part = title
                    tree.parts.append((lineno, title))
                fence.update(line)
                continue

            if part_level is not None and level == part_level and level != 1 and not in_code:
                close(lineno)
                part = clean(line[level:].strip())
                tree.parts.append((lineno, part))
                fence.update(line)
                continue

            if level == grammar.unit_level and not in_code:
                found = split_heading(line, grammar)
                if found is not None:
                    unit_id, unit_title = found
                    if grammar.is_end_marker(unit_id):
                        # A closing marker belongs to the unit it closes; it is
                        # not a unit of its own and never becomes a file.  The
                        # unit ends *after* the marker so the marker travels
                        # with the block it closes.
                        #
                        # ``current`` may already be None -- a marker can close
                        # a block whose last unit was closed by a following
                        # heading.  The marker still must not become a unit, so
                        # it extends the preceding unit instead, or is dropped
                        # when there is none.  (``RHY.Edition:End`` is the case
                        # that exposed this: it used to be counted as a unit.)
                        if current is not None:
                            current.end = lineno + 1
                            tree.units.append(current)
                            current = None
                        elif tree.units:
                            tree.units[-1].end = lineno + 1
                        fence.update(line)
                        continue
                    close(lineno)
                    current = Unit(id=unit_id,
                                   title=clean(unit_title) or unit_id,
                                   role=grammar.classify(unit_id),
                                   level=level, start=lineno, end=lineno,
                                   part=part)
                    fence.update(line)
                    continue
                if level and not in_code:
                    tree.intros.append((lineno, clean(line[level:].strip())))

            elif level in subsection_levels and current is not None and not in_code:
                current.subsections += 1

            fence.update(line)

        close(len(lines) + 1)

        # The document title is a heading too; keep the count honest.
        return tree


def decompose(profile: DecompositionProfile, text: str, path: str = "") -> UnitTree:
    """Convenience wrapper: decompose *text* with *profile*."""
    return Decomposer(profile).run(text, path)


def read(path: Path) -> str:
    """Read a publication, tolerating non-UTF-8 bytes in third-party sources."""
    return path.read_text("utf-8", errors="replace")
