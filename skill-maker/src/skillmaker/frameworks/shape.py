#!/usr/bin/env python3
"""
shape.py -- what a decomposition is allowed to produce.

A grammar says *how* a publication splits.  A shape says *what the split turns
into*: which artefacts a skill gets, and therefore what an agent can retrieve.

The four published kinds need four different shapes, and the difference is not
cosmetic:

* **FPF Core** -- one flat ``reference/fpf-patterns/`` tree of source-derived units,
  plus the three Library guides copied whole into ``reference/``.
* **A DPF** -- one flat tree per framework, patterns and reference units
  separated by role in the indexes.
* **A Suite** -- one tree per constituent framework under a shared
  ``reference/`` root, grouping its constituent frameworks.
* **A Guide** -- no unit files at all: the guide is one document an agent reads
  top to bottom, with an entry-point hub.

Naming the shapes makes the difference explicit and testable instead of
implicit in a fixed catalogue of hand-written configs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Sequence, Tuple


class Layout(str, Enum):
    """Directory layout of the generated reference tree."""

    FLAT = "flat"
    """One ``reference/<framework>/`` directory (FPF, a standalone DPF)."""

    FRAMEWORKS = "frameworks"
    """One ``reference/<framework>/`` directory per constituent (a Suite)."""

    SINGLE = "single"
    """No unit directories: whole documents under ``reference/``."""


#: Index artefacts a pattern-shaped skill generates.  The keys are stable
#: identifiers; :data:`INDEX_FILES` maps them to the files actually written.
PATTERN_INDEXES: Tuple[str, ...] = (
    "root",              # reference/index.md -- framework table
    "framework",         # reference/<key>/index.md -- units of one framework
    "agent_patterns",    # reference/pattern-index.md -- ID -> file
    "agent_references",  # reference/reference-index.md
    "agent_keywords",    # reference/keyword-index.md
    "agent_queries",     # reference/query-index.md
)

#: Index artefacts a reference-shaped skill generates (no pattern queries).
REFERENCE_INDEXES: Tuple[str, ...] = (
    "root",
    "framework",
    "agent_references",
)

#: Artefact key -> file it produces, relative to the skill's ``reference/``.
INDEX_FILES = {
    "root": "index.md",
    "agent_patterns": "pattern-index.md",
    "agent_references": "reference-index.md",
    "agent_keywords": "keyword-index.md",
    "agent_queries": "query-index.md",
}

#: A guide needs an entry point, not an index of units.
GUIDE_INDEXES: Tuple[str, ...] = ("root",)


@dataclass(frozen=True)
class SkillShape:
    """The artefact set a decomposition produces."""

    layout: Layout = Layout.FLAT

    unit_files: bool = True
    """Write one file per addressable unit."""

    intro_files: bool = True
    """Write the narrative sections that precede the units."""

    doc_files: bool = False
    """Copy whole companion documents into ``reference/``."""

    hub: bool = True
    """Write ``SKILL.md`` -- the entry point an agent loads first."""

    readme: bool = True
    """Write ``README.md`` -- the human-facing account of the skill."""

    indexes: Tuple[str, ...] = PATTERN_INDEXES
    """Which index artefacts to generate."""

    tools: bool = True
    """Ship the retrieval scripts in ``scripts/``."""

    def outputs(self, skill_name: str,
                framework_keys: Sequence[str] = (),
                unit_names: Sequence[str] = ()) -> List[str]:
        """Planned file list, in generation order.

        ``plan`` prints this before anything is written, so a decomposition can
        be reviewed without touching the output tree.
        """
        out: List[str] = []
        if self.hub:
            out.append(f"{skill_name}/SKILL.md")
        if self.readme:
            out.append(f"{skill_name}/README.md")

        if self.layout is not Layout.SINGLE and framework_keys:
            if self.layout is Layout.FRAMEWORKS:
                for key in framework_keys:
                    out.append(f"{skill_name}/reference/{key}/")
            else:
                out.append(f"{skill_name}/reference/{framework_keys[0]}/")

        if self.unit_files and unit_names:
            if self.layout is Layout.FRAMEWORKS:
                for key in framework_keys:
                    for name in unit_names:
                        out.append(f"{skill_name}/reference/{key}/{name}.md")
            else:
                base = framework_keys[0] if framework_keys else "reference"
                for name in unit_names:
                    out.append(f"{skill_name}/reference/{base}/{name}.md")

        if "root" in self.indexes:
            out.append(f"{skill_name}/reference/index.md")
        if "framework" in self.indexes and self.layout is Layout.FRAMEWORKS:
            for key in framework_keys:
                out.append(f"{skill_name}/reference/{key}/index.md")
        for name in self.indexes:
            if name != "root" and name in INDEX_FILES:
                out.append(f"{skill_name}/reference/{INDEX_FILES[name]}")

        if self.tools:
            out.append(f"{skill_name}/scripts/")
        return out

    def describe(self) -> str:
        """Compact description used by the ``plan`` CLI."""
        bits = [f"layout={self.layout.value}"]
        if self.unit_files:
            bits.append("unit files")
        if self.intro_files:
            bits.append("intro files")
        if self.doc_files:
            bits.append("whole docs")
        if self.indexes:
            bits.append(f"{len(self.indexes)} indexes")
        if self.tools:
            bits.append("tools")
        return ", ".join(bits)


#: FPF Core: flat pattern tree plus the Library guides copied whole.
PATTERN_SKILL = SkillShape(
    layout=Layout.FLAT,
    unit_files=True,
    intro_files=True,
    doc_files=True,
    indexes=PATTERN_INDEXES,
    tools=True,
)

#: A DPF on its own: flat tree, no companion documents.
DPF_SKILL = SkillShape(
    layout=Layout.FLAT,
    unit_files=True,
    intro_files=True,
    doc_files=False,
    indexes=PATTERN_INDEXES,
    tools=True,
)

#: A Suite: one tree per constituent framework.
SUITE_SKILL = SkillShape(
    layout=Layout.FRAMEWORKS,
    unit_files=True,
    intro_files=True,
    doc_files=False,
    indexes=PATTERN_INDEXES,
    tools=True,
)

#: A Suite Reference: addressable, but nothing in it is a pattern.
REFERENCE_SKILL = SkillShape(
    layout=Layout.FLAT,
    unit_files=True,
    intro_files=True,
    doc_files=False,
    indexes=REFERENCE_INDEXES,
    tools=True,
)

#: A guide: one document, an entry point, no unit tree.
GUIDE_SKILL = SkillShape(
    layout=Layout.SINGLE,
    unit_files=False,
    intro_files=False,
    doc_files=True,
    hub=True,
    indexes=GUIDE_INDEXES,
    tools=False,
)
