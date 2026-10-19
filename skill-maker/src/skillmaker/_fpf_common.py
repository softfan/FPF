#!/usr/bin/env python3
"""
_fpf_common.py — Shared utilities for the FPF / DPF toolchain.

Used by split_spec.py, fpf_lookup.py, audit_fpf_patterns.py and the tests.

The same helpers serve two different identifier families:

* **FPF Core** — ``A.1``, ``C.40.OD``, ``C.2.2a`` (single-letter prefix, dotted
  numeric/word segments).
* **DPF frameworks** — ``SYSE.24``, ``MATH.Reference:3.2``,
  ``PSDA.Advising:1``, ``HCD.Application:10`` (word prefix, dotted segments and
  ``:``-separated section or role segments).

A *unit* is any ``## <ID> - <Title>`` block.  A unit whose first segment after
the prefix is numeric is a **pattern**; a unit whose first segment is a word
(``Reference``, ``Application``, ``Sources``, ``Advising``, ...) is a
**reference unit** of that role.  This distinction is what keeps a framework's
Architectural Reference, worked applications and source notes out of the
pattern index while still making them individually addressable.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Console encoding
# ---------------------------------------------------------------------------

def ensure_utf8_stdio() -> None:
    """Make stdout and stderr write UTF-8 whatever the console code page is.

    A Windows terminal defaults to a legacy code page (cp1251, cp437, ...), and
    printing a check mark, an en dash or a pattern title in another script
    raises ``UnicodeEncodeError`` there.  ``errors="replace"`` is the belt to
    the braces: a stream that still cannot represent a character degrades to
    ``?`` instead of aborting a build half-way through.

    Safe to call more than once, and safe when the streams are redirected to a
    file or a pipe.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            # AttributeError: a stream that is not a TextIOWrapper (a test
            # double, or Python < 3.7).  ValueError: a detached stream.
            pass

# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------

def write_text_lf(path: Path, content: str) -> None:
    """Write UTF-8 text with ``\\n`` line endings on every platform.

    ``Path.write_text`` opens in text mode, which translates ``\\n`` to
    ``os.linesep`` -- so the same build on Windows would write CRLF and differ
    byte-for-byte from the build on Linux.  The generated tree is meant to be a
    function of the sources alone, and ``rebuild`` is compared byte-for-byte,
    so the newline is pinned here rather than left to the platform.

    Creates the parent directory, which every caller would otherwise repeat.

    Open/create without O_TRUNC, then truncate the opened handle. On Windows,
    O_CREAT|O_TRUNC maps to CREATE_ALWAYS, which rejects existing hidden/system
    files unless their attributes are specified. Opening without truncation
    preserves those attributes (and ACLs); readonly/locked files still fail.
    This is an in-place write, not an atomic replacement or a lock bypass.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    def opener(name, flags):
        return os.open(name, flags & ~os.O_TRUNC, 0o666)
    with open(path, "w", encoding="utf-8", newline="\n", opener=opener) as fh:
        fh.truncate(0)
        fh.write(content)

# ---------------------------------------------------------------------------
# Identifier grammar
# ---------------------------------------------------------------------------

#: One identifier segment: a dot- or colon-separated run of word characters.
#: ``[A-Za-z0-9_]+`` (not just ``\d+``) is required because FPF and DPF both
#: publish IDs such as ``C.2.2a``, ``A.19.SCR`` and ``SYSE.Reference:3.2``.
#: Hyphens are allowed *inside* a segment because FPF publishes IDs such as
#: ``A.19.SOURCE-SET-SPACE-SUBSTRATE`` and ``C.30.TFS-REL``.
ID_SEGMENT_RE = r"(?:[.:][A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*)+"

#: Prefix: a leading word (``A``, ``SYSE``, ``Engineering``, ``Library``).
ID_PREFIX_RE = r"[A-Za-z][A-Za-z0-9]*"

#: Full generic unit identifier, anchored.
GENERIC_ID_RE = re.compile(r"^" + ID_PREFIX_RE + ID_SEGMENT_RE + r"$")

#: FPF Core pattern identifiers (single capital letter A–K).
PATTERN_ID_RE = re.compile(r"^[A-K]" + ID_SEGMENT_RE + r"$")

#: Unit heading: ``## ID - Title`` or ``## ID — Title`` / ``## ID: Title``.
#: The separator may be preceded by bold markers, which ``clean()`` strips.
#: ``## <ID> - <Title>``.  The ``(?=\s|$)`` lookahead keeps the ID greedy so
#: that sectioned IDs such as ``IS.Reference:1`` are read whole instead of
#: being split at the ``:`` that belongs to the identifier.
PATTERN_HEADING_RE = re.compile(
    r"^##\s+(?:\*\*)?(?P<id>" + ID_PREFIX_RE + ID_SEGMENT_RE + r")(?=\s|$)"
    r"(?:\*\*)?\s*[-–—:]\s*(?P<title>.+)$"
)
PATTERN_HEADING_BARE_RE = re.compile(
    r"^##\s+(?:\*\*)?(?P<id>" + ID_PREFIX_RE + ID_SEGMENT_RE + r")(?:\*\*)?\s*$"
)

H1_RE = re.compile(r"^#\s+(.+)$")
H2_RE = re.compile(r"^##\s+(.+)$")
TOC_START_RE = re.compile(r"^#\s+Table\s+of\s+Content", re.IGNORECASE)
FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")
PART_H1_RE = re.compile(r"^#\s+(?:\*\*)?Part\b", re.IGNORECASE)

#: Roles that are never pattern bodies, keyed by the first non-numeric segment.
KNOWN_ROLES = {
    "reference", "application", "applications", "sources", "advising",
    "annex", "appendix", "glossary", "index",
}


def is_pattern_id(pid: str) -> bool:
    """True when *pid* is a pattern ID rather than a reference unit."""
    return unit_role(pid) == "pattern"


def unit_role(pid: str) -> str:
    """Classify a unit ID.

    ``SYSE.24``, ``KCAE.USE`` and ``G.Core`` -> ``pattern``;
    ``MATH.Reference:3.2`` -> ``reference``; ``PSDA.Advising:1`` ->
    ``advising``; ``HCD.Application:10`` -> ``application``.

    The distinguishing feature is the ``:`` section separator: a unit heading
    such as ``## SYSE.24 - ...`` is a pattern body, while
    ``## SYSE.Reference:1 - ...`` names a sectioned reference unit.  Word-only
    IDs without a section (``KCAE.USE``) are ordinary patterns.
    """
    if ":" not in pid:
        return "pattern"
    head = pid.split(":", 1)[0]
    for seg in re.split(r"[.:]", head)[1:]:
        if not seg.isdigit():
            return seg.lower()
    return "section"


def is_end_marker(pid: str) -> bool:
    """True for ``X.Reference:End`` style closing markers (no body of their own)."""
    return pid.rsplit(":", 1)[-1].lower() == "end"


def id_to_filename(pid: str) -> str:
    """Filesystem-safe file stem for a unit ID.

    ``:`` cannot appear in Windows file names, so section separators become
    ``-``: ``MATH.Reference:3.2`` -> ``MATH.Reference-3.2``.
    """
    return pid.replace(":", "-")


def filename_to_id(stem: str) -> str:
    """Inverse of :func:`id_to_filename` for the ``X.Y-N`` shape."""
    return stem


# ---------------------------------------------------------------------------
# Fence tracker
# ---------------------------------------------------------------------------

class FenceTracker:
    """Tracks fenced code blocks correctly, handling nested examples.

    Call ``update(line)`` for every line. Check ``in_fence`` to know
    whether the parser is currently inside a fenced block.
    """

    def __init__(self):
        self.in_fence: bool = False
        self._char: str = ""
        self._min_len: int = 0

    def update(self, line: str) -> bool:
        """Process a line, return ``True`` if inside a fence AFTER this line."""
        stripped = line.strip()
        m = FENCE_OPEN_RE.match(stripped)
        if m:
            marker = m.group(1)
            ch = marker[0]
            ln = len(marker)
            if not self.in_fence:
                self.in_fence = True
                self._char = ch
                self._min_len = ln
            elif ch == self._char and ln >= self._min_len:
                after = stripped[ln:]
                if not after or after.isspace():
                    self.in_fence = False
        return self.in_fence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256(content: str) -> str:
    """Return hex SHA-256 of a UTF-8 string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def manifest_entry_path(skill_root: Path, entry: Dict[str, Any]) -> Path:
    """Resolve the engine's flat manifest format within exactly one skill.

    Keys and framework names are individual portable filename components, not
    paths. Validate both POSIX and Windows separators on every platform.
    """
    if not isinstance(entry, dict):
        raise ValueError("manifest entry must be an object")
    kind = entry.get("kind")
    key = entry.get("key")
    if kind not in ("unit", "intro", "doc"):
        raise ValueError(f"unknown manifest entry kind: {kind!r}")
    framework = entry.get("framework") if kind == "unit" else None
    for value in ([key, framework] if kind == "unit" else [key]):
        if (not isinstance(value, str) or not value or value in (".", "..")
                or any(char in value for char in '/\\:\x00')
                or Path(value).is_absolute()):
            raise ValueError(f"invalid manifest filename component: {value!r}")
    if not key.endswith(".md"):
        raise ValueError(f"manifest key must name Markdown: {key!r}")
    directory = framework if kind == "unit" else ("intro" if kind == "intro" else "docs")
    path = skill_root / "reference" / directory / key
    if not path.resolve().is_relative_to(skill_root.resolve()):
        raise ValueError(f"manifest file escapes its skill: {key!r}")
    return path


def sort_key(pattern_id: str) -> Tuple:
    """Sort key that orders IDs naturally (A.1 < A.2 < A.10)."""
    parts = re.split(r"[.:]", pattern_id)
    result: List[Tuple[int, int, str]] = []
    for p in parts:
        try:
            result.append((0, int(p), ""))
        except ValueError:
            result.append((1, 0, p))
    return tuple(result)


def clean(text: str) -> str:
    """Strip bold markers and backticks."""
    return text.replace("**", "").replace("`", "").strip()


def slugify(text: str) -> str:
    """Convert a heading string into a filesystem-safe slug."""
    text = clean(text)
    reps = {
        "–": "-", "—": "-", "\u2019": "", "\u201c": "", "\u201d": "",
        "≠": "neq", "≤": "leq", "≥": "geq", "→": "to", "←": "from",
        "↔": "bidi", "⊗": "otimes", "⊥": "perp", "⊑": "sqsubseteq",
        "Γ": "Gamma", "Φ": "Phi", "Ψ": "Psi", "χ": "chi",
        "/": "_", "\\": "_", ":": "", "(": "", ")": "",
        "&": "and", ",": "", ".": "", ";": "", "?": "", "!": "",
        '"': "", "'": "", "'": "", "#": "", "[": "", "]": "",
    }
    for k, v in reps.items():
        text = text.replace(k, v)
    cyr = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
        "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
        "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
        "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
    }
    out: List[str] = []
    for ch in text.lower():
        if ch in cyr:
            out.append(cyr[ch])
        elif ch.isascii() and (ch.isalnum() or ch in "-_ "):
            out.append(ch)
        else:
            out.append("_")
    slug = "_".join("".join(out).split())
    # "part_c_-_kernel" -> "part_c_kernel": a lone dash between words carries
    # no information in a file name.
    slug = re.sub(r"_+-+_+", "_", slug)
    return re.sub(r"_+", "_", slug).strip("_")[:120]


#: Short, predictable names for the recurring navigation sections of a
#: publication.  Anything else falls back to :func:`slugify` of its heading.
_INTRO_ALIASES = (
    ("table of content", "table_of_content"),
    ("contents", "contents"),
    ("practical entries", "practical_entries"),
    ("architectural reference", "architectural_reference"),
    ("readme", "readme"),
    ("citation", "citation"),
    ("public units", "public_units"),
    ("pattern index", "pattern_index"),
)


def intro_slug(heading: str) -> str:
    """Filesystem slug for an intro section heading."""
    text = clean(heading)
    low = text.lower()
    for needle, slug in _INTRO_ALIASES:
        if needle in low:
            return slug
    if not text:
        return "preamble"
    return slugify(text)
