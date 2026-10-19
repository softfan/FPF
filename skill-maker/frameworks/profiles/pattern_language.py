#!/usr/bin/env python3
"""An Alexander-style pattern language -- ``## 12. THE GATE``.

The third extension kind.  Patterns here are numbered but carry no prefix, and
the useful file name is the pattern name rather than the bare number, so the
grammar names files ``<id>_<slug>``.
"""

from __future__ import annotations

from ..grammar import PATTERN_LANGUAGE
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import DPF_SKILL

PROFILE = DecompositionProfile(
    key="pattern-language",
    kind=PublicationKind.PATTERN_LANGUAGE,
    name="Pattern language",
    description="One file per numbered pattern: context, forces, solution.",
    grammar=PATTERN_LANGUAGE,
    shape=DPF_SKILL,
    path_globs=(
        "**/patterns/*.md",
        "**/*pattern-language*.md",
        "**/*PATTERN-LANGUAGE*.md",
    ),
    header_markers=("Forces", "Therefore", "Context"),
)
