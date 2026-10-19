#!/usr/bin/env python3
"""
sections.py -- where the working sections of a unit are, and what they cost.

A pattern is one file, but it is not one reading.  Its first sections answer
"does this apply?", "what are the moves?", "how do I check the result?"; the
later ones carry worked cases, rationale and source comparisons that answer
"why?" and are usually unnecessary.  Measured over the built tree, the working
sections are 54% of the bytes overall -- 56% across Systems Engineering, 60%
across FPF Core.  The FPF median unit is 33 KB and the largest is 258 KB,
roughly 65k tokens for a single unit.

So a reader needs two things this module computes:

* **tiers** -- which sections answer the question, and which are depth;
* **offsets** -- exactly where each section starts and how big it is, so a
  caller can read a range instead of a file.

Both are derived, never hand-maintained: :func:`analyse` reads the unit's own
headings.  Nothing is duplicated on disk, so a unit file stays the canonical
whole and a rebuild stays byte-identical.

The vocabulary follows the sections the publications actually use.  Counting
across FPF Core and the DPFs:

    forces 487   problem frame 478   problem 477   consequences 466
    relations 484   conformance checklist 432   solution 416
    rationale 363   archetypal grounding 304   anti-patterns 373
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

#: Section titles that answer the question rather than explain the history.
#: Matched case-insensitively as a prefix of the section title, so
#: "Conformance Checklist (normative)" and "Problem Frame" both match.
CONTRACT_PREFIXES: Tuple[str, ...] = (
    "use this when",
    "problem frame",
    "problem",
    "forces",
    "solution",
    "conformance checklist",
    "conformance",
    "consequences",
    "relations",
    "dependencies",
    "invariants",
)

#: A closing marker, never a section of its own.
_END_RE = re.compile(r"(?:^|:)\s*end$", re.IGNORECASE)


def tier_for(title: str) -> str:
    """``contract`` when the section answers the question, else ``source``."""
    t = re.sub(r"\s+", " ", title.strip().lower())
    for prefix in CONTRACT_PREFIXES:
        if t.startswith(prefix):
            return "contract"
    return "source"


def anchor_for(title: str) -> str:
    """GitHub-style anchor for a section title.

    ``Conformance Checklist (normative)`` -> ``conformance-checklist-normative``
    """
    text = title.strip().lower()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[`*_]", "", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


@dataclass
class Section:
    """One section of a unit."""

    n: str
    """Section number or word as it appears in the ID (``4``, ``Reference``)."""

    title: str
    anchor: str
    tier: str
    line: int
    """1-based line of the section heading."""

    end_line: int
    """1-based line of the next section heading (exclusive)."""

    bytes: int = 0

    @property
    def lines(self) -> int:
        return max(0, self.end_line - self.line)

    def to_dict(self) -> Dict:
        return {
            "n": self.n, "title": self.title, "anchor": self.anchor,
            "tier": self.tier, "line": self.line, "end_line": self.end_line,
            "bytes": self.bytes, "lines": self.lines,
        }


@dataclass
class UnitSections:
    """The section map of one unit file."""

    unit_id: str
    file: str
    bytes: int = 0
    lines: int = 0
    sections: List[Section] = field(default_factory=list)

    # --- views ------------------------------------------------------------
    def of_tier(self, tier: str) -> List[Section]:
        return [s for s in self.sections if s.tier == tier]

    def tier_bytes(self, tier: str) -> int:
        return sum(s.bytes for s in self.of_tier(tier))

    def find(self, key: str) -> Optional[Section]:
        """Locate a section by anchor, number, or title prefix."""
        k = key.strip().lower().lstrip("#")
        for s in self.sections:
            if s.anchor == k or s.n.lower() == k:
                return s
        for s in self.sections:
            if s.title.lower().startswith(k):
                return s
        return None

    def budget(self) -> Dict[str, int]:
        """Byte cost per tier.  A token is roughly four bytes of Markdown."""
        contract = self.tier_bytes("contract")
        return {
            "contract": contract,
            "source": self.tier_bytes("source"),
            "all": self.bytes,
            "contract_tokens": contract // 4,
            "all_tokens": self.bytes // 4,
        }

    def to_dict(self) -> Dict:
        return {
            "file": self.file,
            "bytes": self.bytes,
            "lines": self.lines,
            "tier": {"contract": self.tier_bytes("contract"),
                     "source": self.tier_bytes("source")},
            "sections": [s.to_dict() for s in self.sections],
        }


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _heading_re(unit_id: str) -> re.Pattern:
    """Match a section heading belonging to *unit_id*.

    The section ID is the unit ID plus one segment: ``A.1`` -> ``A.1:4``;
    ``MATH.Reference:3`` -> ``MATH.Reference:3.1``.  The segment separator is
    whatever the unit's own last separator was, so both shapes work.
    """
    return re.compile(
        r"^(?P<hashes>#{3,6})\s+(?:\*\*)?"
        r"(?P<id>" + re.escape(unit_id) + r"[.:][A-Za-z0-9_]+)"
        r"(?=\s|$)(?:\*\*)?\s*[-–—:]\s*(?P<title>.+?)\s*$"
    )


def _segment(unit_id: str, section_id: str) -> str:
    return section_id[len(unit_id) + 1:]


def analyse(unit_id: str, text: str, file: str = "") -> UnitSections:
    """Build the section map for one unit.

    Sections are the shallowest heading level below the unit heading that
    carries an ID derived from the unit's own ID.  Deeper headings belong to
    the section they sit in, so they are not listed separately -- they are part
    of its byte range.
    """
    lines = text.splitlines(keepends=True)
    result = UnitSections(unit_id=unit_id, file=file,
                          bytes=len(text.encode("utf-8")), lines=len(lines))

    pattern = _heading_re(unit_id)
    heads: List[Tuple[int, int, str, str]] = []      # (line, level, seg, title)
    for index, raw in enumerate(lines, 1):
        m = pattern.match(raw.rstrip("\n"))
        if not m:
            continue
        seg = _segment(unit_id, m.group("id"))
        if _END_RE.search(seg):
            continue
        heads.append((index, len(m.group("hashes")), seg, m.group("title").strip()))

    if not heads:
        return result

    shallowest = min(h[1] for h in heads)
    heads = [h for h in heads if h[1] == shallowest]

    # Byte offset of each line, so section sizes are exact rather than counted
    # in characters (the sources are UTF-8 with non-ASCII typography).
    offsets = [0]
    for raw in lines:
        offsets.append(offsets[-1] + len(raw.encode("utf-8")))

    for position, (line, _level, seg, title) in enumerate(heads):
        end_line = heads[position + 1][0] if position + 1 < len(heads) else len(lines) + 1
        section = Section(
            n=seg,
            title=title,
            anchor=anchor_for(title),
            tier=tier_for(title),
            line=line,
            end_line=end_line,
        )
        section.bytes = offsets[min(end_line, len(lines)) - 1] - offsets[line - 1]
        result.sections.append(section)

    return result


def read_tier(unit_id: str, text: str, tier: str = "contract") -> str:
    """Return only the sections of *tier*, in their original order.

    This is the whole point of the section map: the working sections of a unit
    are not contiguous in the source, so selecting them requires offsets rather
    than a truncation.
    """
    if tier == "all":
        return text
    info = analyse(unit_id, text)
    if not info.sections:
        return text
    lines = text.splitlines(keepends=True)
    chunks: List[str] = []
    for section in info.of_tier(tier):
        chunks.extend(lines[section.line - 1:section.end_line - 1])
    return "".join(chunks)


def read_section(unit_id: str, text: str, key: str) -> Optional[str]:
    """Return one named section, including its subsections."""
    info = analyse(unit_id, text)
    section = info.find(key)
    if section is None:
        return None
    lines = text.splitlines(keepends=True)
    return "".join(lines[section.line - 1:section.end_line - 1])


def summarise(info: UnitSections) -> str:
    """One-line description used by the CLI and the indexes."""
    b = info.budget()
    if not info.sections:
        return f"{info.unit_id}: no sections ({b['all'] // 1024} KB)"
    return (f"{info.unit_id}: {len(info.sections)} sections, "
            f"contract {b['contract'] // 1024} KB / all {b['all'] // 1024} KB "
            f"({b['contract'] * 100 // max(1, b['all'])}%)")
