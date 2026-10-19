#!/usr/bin/env python3
"""
profiles -- one module per framework kind.

This package is the extension point of the toolchain.  To teach the tool a new
kind of framework, add a module here that exports ``PROFILE`` and list it in
:data:`PROFILES` below.  Nothing in ``decompose``, ``catalogue`` or the CLI
needs to change.

Order matters.  Profiles are registered from most specific to most general, and
a scoring tie is resolved in favour of the earlier entry.  ``generic`` must
stay last: it is the fallback for any Markdown that no other profile claims.
"""

from __future__ import annotations

from typing import Tuple

from . import (
    adr,
    dpf_framework,
    fpf_core,
    generic,
    guide,
    pattern_language,
    standards,
    suite_reference,
)

#: Registered profiles, most specific first.
PROFILES: Tuple = (
    fpf_core.PROFILE,
    suite_reference.PROFILE,
    dpf_framework.PROFILE,
    guide.PROFILE,
    adr.PROFILE,
    standards.PROFILE,
    pattern_language.PROFILE,
    generic.PROFILE,
)

__all__ = ["PROFILES"]
