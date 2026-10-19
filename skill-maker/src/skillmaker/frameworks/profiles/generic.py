#!/usr/bin/env python3
"""Generic Markdown -- the fallback that makes "any framework" true.

No identifiers are assumed.  Every ``##`` heading opens a section whose key is
the slug of its title.  A document of any shape decomposes into something
retrievable, which is the difference between a tool that handles the four
Library kinds and a tool that handles frameworks.
"""

from __future__ import annotations

from ..grammar import GENERIC
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import GUIDE_SKILL

PROFILE = DecompositionProfile(
    key="generic",
    kind=PublicationKind.GENERIC,
    name="Generic Markdown",
    description="Fallback: headings become sections, keyed by title slug.",
    grammar=GENERIC,
    shape=GUIDE_SKILL,
    path_globs=(),
    header_markers=(),
    structural=False,
)
