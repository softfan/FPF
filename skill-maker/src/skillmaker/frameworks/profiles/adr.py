#!/usr/bin/env python3
"""Architecture decision records -- ``## ADR-0007 - Choose a message broker``.

An extension kind: FPF Library does not publish ADRs, but a project that keeps
them should be able to turn them into a retrievable skill.  The profile shows
how little a new kind costs -- one grammar, one shape, a few globs.
"""

from __future__ import annotations

from ..grammar import ADR
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import REFERENCE_SKILL

PROFILE = DecompositionProfile(
    key="adr",
    kind=PublicationKind.ADR,
    name="Architecture Decision Record set",
    description="One file per decision: context, decision, consequences.",
    grammar=ADR,
    shape=REFERENCE_SKILL,
    path_globs=(
        "**/adr/*.md",
        "**/adr-*.md",
        "**/*-adr.md",
        "**/decisions/*.md",
    ),
    header_markers=("## Status", "## Consequences", "## Decision Outcome"),
)
