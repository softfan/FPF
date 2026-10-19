#!/usr/bin/env python3
"""A Guide -- introductions and working instructions.

Guides are mostly prose: ``## Make the publications available`` is a section, not
a unit with an identifier.  But not entirely -- ``FPF-LIBRARY-REFERENCE.md``
publishes ``Library.Reference:11.1`` and a skill must still resolve that
address.  Hence :data:`~frameworks.grammar.DOTTED_OPTIONAL`: an identifier is
captured when the heading carries one, and the title slug is used when it does
not.
"""

from __future__ import annotations

from ..grammar import DOTTED_OPTIONAL
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import GUIDE_SKILL

PROFILE = DecompositionProfile(
    key="guide",
    kind=PublicationKind.GUIDE,
    name="Guide",
    description="One document plus an entry point; sections, not patterns.",
    grammar=DOTTED_OPTIONAL,
    shape=GUIDE_SKILL,
    path_globs=(
        "DPFs/README.md",
        "**/README.md",
        "**/Readme.md",
        "README.md",
        "Readme.md",
        "USING-*.md",
        "**/USING-*.md",
        "FPF-LIBRARY-REFERENCE.md",
    ),
    header_markers=("**Methods for solving difficult problems",),
    # Any dotted identifier at all: guides carry no single prefix.
    fixed_prefix=r"[A-Za-z][A-Za-z0-9]*",
)
