#!/usr/bin/env python3
"""
frameworks -- decompose any kind of framework document.

The toolchain started with two hard-coded families (FPF Core and the DPFs) and
grew a config entry per publication.  This package replaces that with four
small ideas:

``kinds``
    The vocabulary: what kinds of framework exist (``FPF``, ``DPF``,
    ``Reference``, ``Guide``, plus extension kinds such as ``ADR``,
    ``Standards`` and ``Generic``).

``grammar``
    What counts as an addressable unit in each kind -- as data, not code.

``shape``
    What a decomposition produces: unit files, whole documents, indexes, hub.

``profile``
    One kind, end to end: identity + detection + grammar + shape.

On top of those sit three services:

``decompose``
    Read a document, return its :class:`~frameworks.decompose.UnitTree`.

``catalogue``
    The register of publications, local and from a publisher's catalogue, with
    a verification that compares the two.

``registry``
    Classify a document: which profile claims it, and on what evidence.

The public surface is re-exported here so callers do not depend on module
layout::

    from skillmaker.frameworks import detect, decompose, catalogue

    profile, why = detect("DPFs/README.md", text)
    tree = decompose(profile, text, "DPFs/README.md")
    print(len(tree.units), tree.by_role())
"""

from __future__ import annotations

from .catalogue import (
    CATALOGUE_SHAPE,
    REMOTE_URL,
    Issue,
    Publication,
    discover_paths,
    load_local,
    load_remote,
    load_snapshot,
    summarise,
    verify,
)
from .decompose import Decomposer, Unit, UnitTree, decompose, read
from .grammar import (
    ADR,
    DOTTED,
    DOTTED_OPTIONAL,
    GENERIC,
    PATTERN_LANGUAGE,
    STANDARDS,
    UnitGrammar,
    docid_of,
    split_heading,
)
from .kinds import (
    CATALOGUE_KINDS,
    KINDS,
    KindInfo,
    PublicationKind,
    describe as describe_kind,
    info as kind_info,
    kind_from_catalogue,
)
from .profile import DecompositionProfile, Detection
from .registry import (
    all_profiles,
    by_key,
    by_kind,
    classify,
    detect,
    detect_all,
    fallback,
    register,
)
from .shape import (
    DPF_SKILL,
    GUIDE_SKILL,
    PATTERN_SKILL,
    REFERENCE_SKILL,
    SUITE_SKILL,
    Layout,
    SkillShape,
)

__all__ = [
    # kinds
    "PublicationKind", "KindInfo", "KINDS", "CATALOGUE_KINDS",
    "kind_from_catalogue", "kind_info", "describe_kind",
    # grammar
    "UnitGrammar", "DOTTED", "DOTTED_OPTIONAL", "ADR", "STANDARDS",
    "PATTERN_LANGUAGE", "GENERIC", "docid_of", "split_heading",
    # shape
    "SkillShape", "Layout", "PATTERN_SKILL", "DPF_SKILL", "SUITE_SKILL",
    "REFERENCE_SKILL", "GUIDE_SKILL",
    # profile / registry
    "DecompositionProfile", "Detection", "all_profiles", "by_key", "by_kind",
    "classify", "detect", "detect_all", "fallback", "register",
    # decompose
    "Decomposer", "Unit", "UnitTree", "decompose", "read",
    # catalogue
    "Publication", "Issue", "discover_paths", "load_local", "load_remote",
    "load_snapshot", "summarise", "verify", "REMOTE_URL", "CATALOGUE_SHAPE",
]
