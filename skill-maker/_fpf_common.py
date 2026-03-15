#!/usr/bin/env python3
"""
_fpf_common.py — Shared utilities for FPF toolchain.

Used by split_fpf_spec.py, fpf_tools.py, and audit_fpf_patterns.py.
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

PATTERN_ID_RE = re.compile(
    r"^[A-K](?:\.(?:\d+|[A-Za-z][A-Za-z0-9_]*))+$"
)

PATTERN_HEADING_RE = re.compile(
    r"^##\s+(?:\*\*)?(?P<id>[A-K](?:\.(?:\d+|[A-Za-z][A-Za-z0-9_]*))+)"
    r"(?:\*\*)?\s*[-–—:]\s*(?P<title>.+)$"
)
PATTERN_HEADING_BARE_RE = re.compile(
    r"^##\s+(?:\*\*)?(?P<id>[A-K](?:\.(?:\d+|[A-Za-z][A-Za-z0-9_]*))+)"
    r"(?:\*\*)?\s*$"
)

H1_RE = re.compile(r"^#\s+(.+)$")
H2_RE = re.compile(r"^##\s+(.+)$")
TOC_START_RE = re.compile(r"^#\s+Table\s+of\s+Content", re.IGNORECASE)
FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")
PART_TOC_RE = re.compile(r"\*\*Part\s+([A-K])\s*[-–—]")


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


def sort_key(pattern_id: str) -> Tuple:
    """Sort key that orders pattern IDs naturally (A.1 < A.2 < A.10)."""
    parts = pattern_id.split(".")
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
    return re.sub(r"_+", "_", slug).strip("_")[:120]