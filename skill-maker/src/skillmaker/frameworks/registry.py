#!/usr/bin/env python3
"""
registry.py -- profile lookup and document classification.

One place decides what a document is.  The catalogue asks it (so a publication
has a kind), ``probe`` asks it (so a human can see why), and a future builder
will ask it (so a new framework kind needs no new build code).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .kinds import PublicationKind
from .profile import DecompositionProfile, Detection, best
from .profiles import PROFILES

#: Registered profiles, most specific first.
_ORDER: List[DecompositionProfile] = list(PROFILES)
_BY_KEY = {p.key: p for p in _ORDER}

#: The fallback profile.  Never removed: every document must decompose.
FALLBACK_KEY = "generic"


def all_profiles() -> Tuple[DecompositionProfile, ...]:
    """Every registered profile, most specific first."""
    return tuple(_ORDER)


def by_key(key: str) -> DecompositionProfile:
    """Look up a profile by its stable key."""
    try:
        return _BY_KEY[key]
    except KeyError:
        raise KeyError(
            f"unknown profile {key!r}; known profiles: " + ", ".join(_BY_KEY)
        ) from None


def by_kind(kind: PublicationKind) -> Tuple[DecompositionProfile, ...]:
    """Every profile that decomposes *kind*."""
    return tuple(p for p in _ORDER if p.kind is kind)


def fallback() -> DecompositionProfile:
    """The profile used when no other profile claims a document."""
    return _BY_KEY[FALLBACK_KEY]


def register(profile: DecompositionProfile, before: Optional[str] = None) -> None:
    """Add a profile at runtime.

    *before* inserts ahead of the named profile, which is how a caller makes a
    narrower kind win a tie.  Registration is process-local: the durable way to
    add a kind is a module under ``profiles/``.
    """
    if profile.key in _BY_KEY:
        raise ValueError(f"profile {profile.key!r} is already registered")
    _BY_KEY[profile.key] = profile
    if before and before in _BY_KEY:
        index = _ORDER.index(_BY_KEY[before])
        _ORDER.insert(index, profile)
    elif before is None:
        _ORDER.insert(len(_ORDER) - 1, profile)     # keep the fallback last
    else:
        _ORDER.append(profile)


def detect(path: str, text: str) -> Tuple[DecompositionProfile, Detection]:
    """Classify one document.

    Returns the winning profile and the evidence for it.  When nothing scores,
    the fallback profile is returned with an explicit "no evidence" reason, so
    a generic result is never mistaken for a confident classification.
    """
    scored = [(p, p.detect(path, text)) for p in _ORDER]
    winner, detection = best(scored)
    if winner is None or detection.score <= 0:
        fallback_profile = fallback()
        return fallback_profile, Detection(
            profile_key=fallback_profile.key,
            score=0,
            reasons=("no path, header or heading evidence",),
        )
    return winner, detection


def classify(path: str) -> DecompositionProfile:
    """Classify by path alone (no document read).

    Used by the catalogue, which must not read 17 MB of FPF Core to learn that
    ``FPF-Spec.md`` is FPF Core.
    """
    profile, _ = detect(path, "")
    return profile


def detect_all(path: str, text: str) -> List[Tuple[DecompositionProfile, Detection]]:
    """Every profile's score for one document, highest first.

    ``probe --all`` uses this to show the near misses.
    """
    scored = [(p, p.detect(path, text)) for p in _ORDER]
    return sorted(scored, key=lambda item: -item[1].score)
