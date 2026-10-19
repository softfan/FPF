#!/usr/bin/env python3
"""A DPF Suite Architectural Reference -- four publications, one profile.

Each Reference declares its own DocID (``Engineering``, ``Management``,
``Foundational``, ``HCE``) and publishes ``<DocID>.Reference:N`` units.  Nothing
in those units is a pattern, which is why this profile uses
:data:`~frameworks.shape.REFERENCE_SKILL` rather than a pattern shape.
"""

from __future__ import annotations

from ..grammar import DOTTED
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import REFERENCE_SKILL

PROFILE = DecompositionProfile(
    key="suite-reference",
    kind=PublicationKind.REFERENCE,
    name="Suite Architectural Reference",
    description="Addressable reference units: composition, connections, cases.",
    grammar=DOTTED,
    shape=REFERENCE_SKILL,
    path_globs=("*-SUITE-REFERENCE.md", "**/*-SUITE-REFERENCE.md"),
    header_markers=("Architectural Reference",),
    docid_prefix=True,
)
