#!/usr/bin/env python3
"""
skill_root.py -- find a skill's root without being told where it is.

A skill directory is meant to be movable.  If its tools hard-code
``skills/<name>``, then copying the directory somewhere else breaks them, and a
copied skill is exactly what people do: into a project, into a container, into
another repository.

The fix is a marker.  Every built skill carries ``.skill.json`` at its root:

    {"schema": 1, "name": "decision-design", "kind": "Framework", ...}

A tool given any path inside the skill walks up until it finds that file.  This
is the same idea as ``.git`` or ``pyproject.toml``, and it costs one file per
skill.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from _fpf_common import write_text_lf

#: The marker file's name.
MARKER = ".skill.json"

#: How far up to look.  A skill is shallow; a deep search would find a marker in
#: an unrelated parent directory.
MAX_DEPTH = 6


def marker_path(skill_root: Path) -> Path:
    return skill_root / MARKER


def write_marker(skill_root: Path, name: str, title: str, kind: str,
                 genre: str, profile: str, source: str,
                 patterns: int, units: int) -> None:
    """Write the marker at a skill's root."""
    payload = {
        "schema": 1,
        "name": name,
        "title": title,
        "kind": kind,
        "genre": genre,
        "profile": profile,
        "source": source,
        "patterns": patterns,
        "units": units,
        "layout": "reference/{docs,intro,<docid>}",
    }
    write_text_lf(marker_path(skill_root),
                  json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def read_marker(skill_root: Path) -> Optional[Dict]:
    path = marker_path(skill_root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return None


def find_root(start: Path) -> Optional[Path]:
    """Walk up from *start* until a skill marker is found.

    Returns ``None`` when there is no marker, so a caller can fall back to the
    path it was given instead of guessing.
    """
    current = start if start.is_dir() else start.parent
    for _ in range(MAX_DEPTH):
        if marker_path(current).exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def resolve(start: Path) -> Path:
    """The skill root containing *start*, or *start* itself.

    The fallback matters: a directory that was built before markers existed, or
    one being inspected mid-build, must still work.
    """
    return find_root(start) or start


def discover(skills_root: Path) -> List[Path]:
    """Every immediate child of *skills_root* that carries a marker."""
    if not skills_root.is_dir():
        return []
    return sorted(p for p in skills_root.iterdir()
                  if p.is_dir() and marker_path(p).exists())
