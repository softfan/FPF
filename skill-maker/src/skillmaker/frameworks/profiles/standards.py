#!/usr/bin/env python3
"""Clause-numbered standards -- ``## 4.3.2 Architecture description``.

Another extension kind.  The distinctive feature is the absence of a separator
between the clause number and its title, which is why
:data:`~frameworks.grammar.STANDARDS` sets ``title_sep=None``.
"""

from __future__ import annotations

from ..grammar import STANDARDS
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import REFERENCE_SKILL

PROFILE = DecompositionProfile(
    key="standards",
    kind=PublicationKind.STANDARDS,
    name="Standards document",
    description="One file per clause; numbered requirements, no prefixes.",
    grammar=STANDARDS,
    shape=REFERENCE_SKILL,
    path_globs=(
        "**/standard*.md",
        "**/*-standard.md",
        "**/iso*.md",
        "**/ieee*.md",
        "**/rfc*.md",
    ),
    header_markers=("Normative", "Conformance", "shall", "Scope"),
)
