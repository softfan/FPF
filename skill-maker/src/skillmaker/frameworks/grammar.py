#!/usr/bin/env python3
"""
grammar.py -- what counts as an addressable unit in a framework document.

Every framework decomposes the same way: a heading opens a unit, the unit runs
until the next unit heading, and the heading carries (or implies) an identifier.
What differs between framework types is only *the grammar of that heading*:

============================  ==============================================
FPF Core / DPF / Reference    ``## SYSE.24 - Title``  (dotted, ID first)
Architecture Decision Record  ``## ADR-0007 - Title`` (sequential, dashed)
Standards document            ``## 4.3.2 Title``      (numeric, no separator)
Pattern language              ``## 12. Name``         (integer + dot)
Generic Markdown              ``## Any heading``      (identifier = the slug)
============================  ==============================================

:class:`UnitGrammar` states that grammar as data.  One grammar instance drives
matching, role classification and file naming, so a new framework type never
needs new parsing code -- only a new grammar value.

The dotted-identifier grammar is deliberately identical to the one the
existing engine builds in ``split_spec.build_heading_re``; ``test_frameworks``
asserts that the two agree on every published unit, so the two code paths
cannot drift apart silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Optional, Pattern

from .._fpf_common import (
    GENERIC_ID_RE,
    ID_SEGMENT_RE,
    is_end_marker,
    slugify,
    unit_role,
)

#: Characters a Markdown heading may use as an ID/title separator.
DEFAULT_TITLE_SEP = r"[-–—:]"

#: ``**DocID:** `SYSE` `` in a publication header (FPF Core prefixes it with
#: a list bullet, so the bullet is optional).
DOCID_RE = re.compile(r"^\s*(?:[-*]\s*)?\*\*DocID:\*\*\s*`([^`\n]+)`", re.MULTILINE)


def docid_of(text: str) -> str:
    """Return the publication's declared DocID, or ``""`` when it has none."""
    m = DOCID_RE.search(text[:20000])
    return m.group(1).strip() if m else ""


@dataclass(frozen=True)
class UnitGrammar:
    """The heading grammar of one framework kind.

    Instances are frozen and hashable, so compiled regexes are cached per
    grammar value.
    """

    unit_level: int = 2
    """Heading level that opens a unit (2 for ``##``)."""

    id_pattern: Optional[str] = None
    """Regex fragment for the identifier, or ``None`` when the heading text
    itself is the unit key (generic Markdown)."""

    id_optional: bool = False
    """When True, a heading that does not match ``id_pattern`` is still a unit
    and its key is the slug of its title.  Guides use this: most of their
    headings are prose, but a few carry real identifiers."""

    title_sep: Optional[str] = None
    """Regex character class separating ID from title.  ``None`` means the
    title simply follows whitespace (clause-numbered standards)."""

    allow_bare: bool = True
    """Accept ``## ID`` with no title at all."""

    id_abuts_separator: bool = False
    """True when the separator directly follows the identifier.

    ``## 12. THE GATE`` needs it; ``## A.1 - Title`` must not have it, because
    the dotted identifier may itself contain the separator."""

    part_level: Optional[int] = 1
    """Heading level used for part dividers after the document title."""

    classify_roles: bool = True
    """Classify dotted identifiers into roles (pattern / reference / ...).

    When False every unit takes :attr:`default_role`."""

    fence_aware: bool = True
    """Ignore headings inside fenced code blocks."""

    filename_style: str = "id"
    """``id`` (``MATH.Reference-3.2``), ``slug`` (title slug) or
    ``id_slug`` (both)."""

    default_role: str = "section"
    """Role for units that carry no recognisable identifier."""

    # --- compiled regexes -------------------------------------------------
    @property
    def heading_re(self) -> Pattern:
        return _heading_re(self)

    @property
    def bare_heading_re(self) -> Optional[Pattern]:
        return _bare_re(self)

    @property
    def id_re(self) -> Optional[Pattern]:
        return _id_re(self)

    # --- construction -----------------------------------------------------
    def for_prefix(self, prefix_re: str) -> "UnitGrammar":
        """Return this grammar bound to one publication's ID prefix.

        ``SYSE``, ``MATH`` and ``Engineering`` share one grammar shape; only
        the prefix differs.  The prefix is wrapped so it cannot capture.
        """
        return replace(self, id_pattern="(?:" + prefix_re + ")" + ID_SEGMENT_RE)

    # --- classification ---------------------------------------------------
    def classify(self, unit_id: str) -> str:
        """Role of a unit: ``pattern``, ``reference``, ``section``, ..."""
        if self.classify_roles and GENERIC_ID_RE.match(unit_id or ""):
            return unit_role(unit_id)
        return self.default_role

    def is_end_marker(self, unit_id: str) -> bool:
        """True for closing markers such as ``MATH.Reference:End``."""
        return bool(unit_id) and is_end_marker(unit_id)

    # --- naming -----------------------------------------------------------
    def filename(self, unit_id: str, title: str = "") -> str:
        """Filesystem-safe file stem for one unit.

        ``:`` is illegal in Windows file names, so it becomes ``-``:
        ``MATH.Reference:3.2`` -> ``MATH.Reference-3.2``.
        """
        uid = (unit_id or "").replace(":", "-")
        if self.filename_style == "slug":
            return slugify(title or unit_id) or "unit"
        if self.filename_style == "id_slug":
            slug = slugify(title or "")
            return f"{uid}_{slug}"[:120] if slug else uid
        return uid

    def describe(self) -> str:
        """Compact human description, used by ``probe`` output."""
        if self.id_pattern is None:
            ident = "heading slug"
        else:
            ident = self.id_pattern
        sep = "whitespace" if self.title_sep is None else self.title_sep
        return (f"level {'#' * self.unit_level}, id={ident}, "
                f"sep={sep}, roles={'dotted' if self.classify_roles else self.default_role}")


# ---------------------------------------------------------------------------
# Compiled regexes (cached per grammar value)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _heading_re(g: UnitGrammar) -> Pattern:
    hashes = "#" * g.unit_level
    if g.id_pattern is None:
        return re.compile(r"^" + hashes + r"\s+(?P<title>.+?)\s*$")
    # The identifier must end at whitespace or at end of line.  Grammars whose
    # separator abuts the identifier (``## 12. Name``) relax this to also allow
    # the separator itself; grammars whose identifiers may *contain* the
    # separator (``FPF.Reference:End``) must not, or the identifier would be
    # split at its own colon.
    lookahead = r"(?=\s|$)"
    if g.title_sep is not None and g.id_abuts_separator:
        lookahead = r"(?=\s|$|(?:" + g.title_sep + r"))"
    head = (r"^" + hashes + r"\s+(?:\*\*)?(?P<id>" + g.id_pattern +
            r")" + lookahead + r"(?:\*\*)?")
    if g.title_sep is None:
        tail = r"\s+(?P<title>.+)$"
    else:
        tail = r"\s*(?:" + g.title_sep + r")\s*(?P<title>.+)$"
    return re.compile(head + tail)


@lru_cache(maxsize=None)
def _bare_re(g: UnitGrammar) -> Optional[Pattern]:
    if g.id_pattern is None or not g.allow_bare:
        return None
    hashes = "#" * g.unit_level
    return re.compile(r"^" + hashes + r"\s+(?:\*\*)?(?P<id>" + g.id_pattern +
                      r")(?:\*\*)?\s*$")


@lru_cache(maxsize=None)
def _id_re(g: UnitGrammar) -> Optional[Pattern]:
    if g.id_pattern is None:
        return None
    return re.compile(r"^(?:" + g.id_pattern + r")$")


# ---------------------------------------------------------------------------
# Ready-made grammars
# ---------------------------------------------------------------------------

#: Dotted, identifier-first headings -- FPF Core, DPFs, Suite References.
#: Bind it to a publication with :meth:`UnitGrammar.for_prefix`.
DOTTED = UnitGrammar(
    unit_level=2,
    title_sep=DEFAULT_TITLE_SEP,
    allow_bare=True,
    part_level=1,
    classify_roles=True,
    filename_style="id",
    default_role="section",
)

#: Same shape, but a heading without an identifier is still a unit whose key
#: is the title slug.  Guides need this: prose sections plus a few real IDs.
DOTTED_OPTIONAL = replace(DOTTED, id_optional=True)

#: Architecture decision records: ``## ADR-0007 - Title``.
ADR = UnitGrammar(
    unit_level=2,
    id_pattern=r"ADR[-\s]?\d+",
    title_sep=DEFAULT_TITLE_SEP,
    allow_bare=False,
    part_level=1,
    classify_roles=False,
    filename_style="id",
    default_role="decision",
)

#: Clause-numbered standards: ``## 4.3.2 Clause title``.
STANDARDS = UnitGrammar(
    unit_level=2,
    id_pattern=r"\d+(?:\.\d+)*",
    title_sep=None,
    allow_bare=False,
    part_level=1,
    classify_roles=False,
    filename_style="id",
    default_role="clause",
)

#: Alexander-style pattern language: ``## 12. Name``.
PATTERN_LANGUAGE = UnitGrammar(
    unit_level=2,
    id_pattern=r"\d+",
    title_sep=r"[.):]",
    allow_bare=False,
    id_abuts_separator=True,
    part_level=1,
    classify_roles=False,
    filename_style="id_slug",
    default_role="pattern",
)

#: Anything else: every heading at the unit level is a section.
GENERIC = UnitGrammar(
    unit_level=2,
    id_pattern=None,
    title_sep=None,
    allow_bare=False,
    part_level=1,
    classify_roles=False,
    filename_style="slug",
    default_role="section",
)


def heading_text(line: str) -> Optional[str]:
    """Return the text of an ATX heading line, or ``None``."""
    m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
    return m.group(2) if m else None


def heading_level(line: str) -> int:
    """ATX heading level (``## x`` -> 2), or 0 when the line is not a heading."""
    m = re.match(r"^(#{1,6})\s+", line)
    return len(m.group(1)) if m else 0


def split_heading(line: str, g: UnitGrammar):
    """Match one line against *g*.

    Returns ``(unit_id, title)`` for a unit heading, ``None`` otherwise.
    Generic grammars return the slug of the heading as the identifier.
    """
    if g.id_pattern is None:
        m = g.heading_re.match(line)
        if not m:
            return None
        title = m.group("title").strip()
        return slugify(title) or "section", title

    m = g.heading_re.match(line)
    if m:
        return m.group("id"), m.group("title").strip()
    bare = g.bare_heading_re
    if bare is not None:
        m = bare.match(line)
        if m:
            return m.group("id"), ""
    if g.id_optional:
        m = re.match(r"^" + "#" * g.unit_level + r"\s+(?P<title>.+?)\s*$", line)
        if m:
            title = m.group("title").replace("**", "").strip()
            return slugify(title) or "section", title
    return None
