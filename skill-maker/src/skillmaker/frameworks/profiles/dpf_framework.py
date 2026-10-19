#!/usr/bin/env python3
"""A Domain Principle Framework -- a profile shared by arbitrary publications.

The DocID is the ID prefix: ``PSDA`` publishes ``PSDA.1``, ``MATH`` publishes
``MATH.1``, and so on.  A DPF that forgot its header is still recognised: the
prefix is then recovered from the first dotted heading.
"""

from __future__ import annotations

from ..grammar import DOTTED
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import DPF_SKILL

PROFILE = DecompositionProfile(
    key="dpf-framework",
    kind=PublicationKind.DPF,
    name="Domain Principle Framework",
    description="Flat tree per framework: patterns plus reference units.",
    grammar=DOTTED,
    shape=DPF_SKILL,
    path_globs=(
        "DPFs/*.md",
        "DPFs/*/*.md",
        "**/*PRINCIPLES-FRAMEWORK.md",
        "**/*-DPF.md",
    ),
    header_markers=("**DocID:**", "domain pattern language", "pattern language"),
    docid_prefix=True,
)
