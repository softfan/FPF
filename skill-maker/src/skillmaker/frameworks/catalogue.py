#!/usr/bin/env python3
"""
catalogue.py -- the register of publications the toolchain can decompose.

Two sources, one model:

* **local** -- the Markdown files in this repository, discovered by path;
* **remote** -- a publisher's machine-readable catalogue: a JSON document
  listing each publication with its ``kind``, its ``suite``, a pattern count
  and a section count.  The URL is configuration, not a constant: any
  publisher that serves the same shape can be verified against.

The remote catalogue is not decoration.  It is an independent statement of what
the Library contains and of how each publication is classified, so
``fpf_frameworks.py catalogue --verify`` can check the local decomposition
against the publisher instead of against itself.  A disagreement is reported as
an issue rather than smoothed over.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .grammar import docid_of

#: Default catalogue endpoint.  Override with ``--catalogue-url`` or the
#: ``FPF_CATALOGUE_URL`` environment variable; nothing in the code assumes a
#: particular host.
REMOTE_URL = os.environ.get("FPF_CATALOGUE_URL", "")

#: Documented shape of the endpoint, for error messages.
CATALOGUE_SHAPE = "JSON: {\"publications\": [{path, kind, suite, patterns, sections}]}"

#: Publication roots that are not inside ``DPFs/``.
ROOT_DOCUMENTS = (
    "FPF-Spec.md",
    "Readme.md",
    "USING-FPF.md",
    "FPF-LIBRARY-REFERENCE.md",
)

#: Directories scanned for publications.
DOCUMENT_DIRS = ("DPFs",)


@dataclass(frozen=True)
class Publication:
    """One publication, from either source."""

    path: str
    """Repo-relative POSIX path (``DPFs/README.md``)."""

    title: str = ""
    kind: str = ""
    """Catalogue kind value (``FPF``, ``DPF``, ``Reference``, ``Guide``)."""

    suite: Optional[str] = None
    """Suite directory, for members of a Suite."""

    patterns: int = 0
    sections: int = 0
    size: int = 0
    docid: str = ""
    url: str = ""

    def to_dict(self) -> Dict:
        return {
            "path": self.path, "title": self.title, "kind": self.kind,
            "suite": self.suite, "patterns": self.patterns,
            "sections": self.sections, "size": self.size,
            "docid": self.docid, "url": self.url,
        }


@dataclass
class Issue:
    """One disagreement between the local tree and the publisher."""

    path: str
    problem: str
    local: str = ""
    remote: str = ""

    def describe(self) -> str:
        detail = f"local={self.local!r} remote={self.remote!r}" if self.local or self.remote else ""
        return f"{self.path}: {self.problem}" + (f" ({detail})" if detail else "")


# ---------------------------------------------------------------------------
# Local catalogue
# ---------------------------------------------------------------------------

def discover_paths(repo_root: Path) -> List[str]:
    """Every publication path in the repository, sorted."""
    paths: List[str] = []
    for name in ROOT_DOCUMENTS:
        if (repo_root / name).exists():
            paths.append(name)
    for directory in DOCUMENT_DIRS:
        base = repo_root / directory
        if base.is_dir():
            for md in base.rglob("*.md"):
                paths.append(md.relative_to(repo_root).as_posix())
    return sorted(paths)


def load_local(repo_root: Path, classify=None) -> List[Publication]:
    """Discover local publications.

    *classify* is a callable ``path -> profile``; when given, it supplies the
    kind, so the catalogue and the decomposer cannot disagree about what a file
    is.
    """
    out: List[Publication] = []
    for rel in discover_paths(repo_root):
        full = repo_root / rel
        suite = None
        parts = rel.split("/")
        if len(parts) == 3 and parts[0] == "DPFs":
            suite = "/".join(parts[:2])
        text = full.read_text("utf-8", errors="replace")
        title = ""
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        kind = ""
        if classify is not None:
            profile = classify(rel)
            kind = profile.kind.value if profile else ""
        out.append(Publication(
            path=rel,
            title=title,
            kind=kind,
            suite=suite,
            size=full.stat().st_size,
            docid=docid_of(text),
        ))
    return out


# ---------------------------------------------------------------------------
# Remote catalogue
# ---------------------------------------------------------------------------

def load_remote(url: str = REMOTE_URL, timeout: float = 20.0) -> Tuple[List[Publication], Dict]:
    """Fetch the publisher's catalogue.

    Returns ``(publications, meta)`` where *meta* carries the snapshot id and
    suite list.  Raises ``urllib.error.URLError`` when the service is
    unreachable -- callers decide whether that is fatal.
    """
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "skill-maker/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    pubs = [
        Publication(
            path=item.get("path", ""),
            title=item.get("title", ""),
            kind=item.get("kind", ""),
            suite=item.get("suite"),
            patterns=int(item.get("patterns") or 0),
            sections=int(item.get("sections") or 0),
            size=int(item.get("bytes") or 0),
            url=item.get("url", ""),
        )
        for item in payload.get("publications", [])
    ]
    meta = {
        "snapshot": payload.get("snapshot", ""),
        "suites": payload.get("suites", []),
        "count": len(pubs),
        "url": url,
    }
    return pubs, meta


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def load_snapshot(path: Path) -> Tuple[List[Publication], Dict]:
    """Load a saved copy of the publisher catalogue.

    ``catalogue.snapshot.json`` in this directory is such a copy.  It lets
    verification run offline and, more importantly, lets the tests check the
    decomposition against the publisher rather than against itself.
    """
    payload = json.loads(path.read_text("utf-8"))
    pubs = [
        Publication(
            path=item.get("path", ""),
            title=item.get("title", ""),
            kind=item.get("kind", ""),
            suite=item.get("suite"),
            patterns=int(item.get("patterns") or 0),
            sections=int(item.get("sections") or 0),
        )
        for item in payload.get("publications", [])
    ]
    meta = {
        "snapshot": payload.get("snapshot", ""),
        "source": payload.get("source", ""),
        "retrieved": payload.get("retrieved", ""),
        "count": len(pubs),
    }
    return pubs, meta


def verify(local: Iterable[Publication], remote: Iterable[Publication]) -> List[Issue]:
    """Compare a local catalogue against the publisher's.

    Checks membership, kind and pattern count.  Section counts are *not*
    compared: they count every heading including fenced examples, so they are
    a publisher-side rendering detail rather than a decomposition fact.
    """
    by_path = {p.path: p for p in remote}
    local_by_path = {p.path: p for p in local}
    issues: List[Issue] = []

    for path in sorted(local_by_path):
        mine = local_by_path[path]
        theirs = by_path.get(path)
        if theirs is None:
            issues.append(Issue(path, "not in the publisher catalogue"))
            continue
        if mine.kind and theirs.kind and mine.kind != theirs.kind:
            issues.append(Issue(path, "kind differs", mine.kind, theirs.kind))
        if mine.patterns and theirs.patterns and mine.patterns != theirs.patterns:
            issues.append(Issue(path, "pattern count differs",
                                str(mine.patterns), str(theirs.patterns)))
        elif theirs.patterns and not mine.patterns:
            issues.append(Issue(path, "no local pattern count",
                                "0", str(theirs.patterns)))

    for path in sorted(set(by_path) - set(local_by_path)):
        issues.append(Issue(path, "published but missing locally"))
    return issues


def summarise(pubs: Iterable[Publication]) -> Dict[str, int]:
    """Count publications by kind."""
    out: Dict[str, int] = {}
    for pub in pubs:
        out[pub.kind or "?"] = out.get(pub.kind or "?", 0) + 1
    return dict(sorted(out.items()))
