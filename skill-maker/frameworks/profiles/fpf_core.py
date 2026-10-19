#!/usr/bin/env python3
"""FPF Core -- ``FPF-Spec.md``, the shared pattern language."""

from __future__ import annotations

from ..grammar import DOTTED
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import PATTERN_SKILL

PROFILE = DecompositionProfile(
    key="fpf-core",
    kind=PublicationKind.FPF,
    name="FPF Core",
    description="Flat tree of ~400 pattern units plus the Library guides.",
    grammar=DOTTED,
    shape=PATTERN_SKILL,
    path_globs=("FPF-Spec.md", "**/FPF-Spec.md"),
    header_markers=("**DocID:** `FPF`", "Core Conceptual Specification"),
    # FPF Core declares ``DocID: FPF`` but publishes ``A.1``..``K.x`` patterns,
    # plus ``FPF.Reference:N`` for its embedded Architectural Reference.
    fixed_prefix=r"(?:[A-K]|FPF)",
)
