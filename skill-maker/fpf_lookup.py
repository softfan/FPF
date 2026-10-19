#!/usr/bin/env python3
"""
fpf_lookup.py -- Search, read, and navigate an FPF skill.

Tool functions (sync, no framework dependency):

    fpf_search_index(keyword, limit)   -- search patterns by ID / title / keyword
    fpf_read_pattern(pattern_id)       -- load one pattern body
    fpf_list_domain(domain)            -- list the patterns of one Core Part
    fpf_read_intro(query)              -- read a readme / contents / practical entry
    fpf_read_doc(query)                -- read a Library document (USING-FPF, ...)
    fpf_list_docs()                    -- list the shipped Library documents

Usage:
    python skill-maker/fpf_lookup.py --skill-root skills/fpf search "holon"
    python skill-maker/fpf_lookup.py --skill-root skills/fpf read A.1
    python skill-maker/fpf_lookup.py --skill-root skills/fpf list A
    python skill-maker/fpf_lookup.py --skill-root skills/fpf intro "practical"
    python skill-maker/fpf_lookup.py --skill-root skills/fpf doc using-fpf
    python skill-maker/fpf_lookup.py --skill-root skills/fpf docs
"""

from __future__ import annotations

import argparse
import os
import pickle
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure sibling modules are importable regardless of cwd
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

try:
    import skill_root
    from _fpf_common import id_to_filename, sort_key
except ImportError:  # pragma: no cover - standalone fallback
    skill_root = None
    def sort_key(pattern_id: str) -> tuple:
        parts = re.split(r"[.:]", pattern_id)
        result = []
        for p in parts:
            try:
                result.append((0, int(p), ""))
            except ValueError:
                result.append((1, 0, p))
        return tuple(result)

    def id_to_filename(pid: str) -> str:
        return pid.replace(":", "-")


DOMAIN_NAMES = {
    "A": "Kernel Architecture", "B": "Trans-disciplinary Reasoning",
    "C": "Kernel Extensions", "D": "Multi-scale Ethics",
    "E": "Constitution & Authoring", "F": "Unification Suite",
    "G": "Discipline SoTA Patterns", "H": "Glossary & Index",
    "I": "Annexes & Tutorials", "J": "Indexes & Navigation",
    "K": "Lexical Debt",
}
VALID_DOMAINS = set("ABCDEFGHIJK")


@dataclass
class PatternEntry:
    pattern_id: str
    title: str
    domain: str
    status: str
    keywords: str = ""
    file_path: str = ""
    role: str = "pattern"

    @property
    def search_text(self) -> str:
        return f"{self.pattern_id} {self.title} {self.keywords}".lower()


class PatternIndex:
    """Lazy index over a built skill directory."""

    def __init__(self, skill_root: Optional[Path] = None):
        self._skill_root = skill_root or self._detect_skill_root()
        self._entries: Optional[Dict[str, PatternEntry]] = None
        self._cache_path = self._skill_root / ".fpf_index.pickle"

    # --- location ---------------------------------------------------------
    @staticmethod
    def _detect_skill_root() -> Path:
        """Find the skill this script belongs to.

        In order: an explicit environment variable, the marker file above this
        script, the marker in the working directory, and finally the legacy
        ``SKILL.md`` check.  The marker comes first because it is what makes a
        copied skill work: the directory can move anywhere and still resolve.
        """
        env = os.environ.get("FPF_SKILL_ROOT")
        if env:
            return Path(env)

        here = Path(__file__).resolve().parent
        if skill_root is not None:
            found = skill_root.find_root(here)
            if found is not None:
                return found
            found = skill_root.find_root(Path.cwd())
            if found is not None:
                return found

        if here.name == "scripts" and (here.parent / "SKILL.md").exists():
            return here.parent
        if (here.parent / "SKILL.md").exists():
            return here.parent
        for candidate in (Path.cwd() / "skills" / "fpf", Path.cwd()):
            if (candidate / "SKILL.md").exists():
                return candidate
        return here.parent

    @property
    def skill_root(self) -> Path:
        return self._skill_root

    @property
    def reference_dir(self) -> Path:
        return self._skill_root / "reference"

    def _patterns_dir(self) -> Optional[Path]:
        ref = self.reference_dir
        preferred = ref / "fpf-patterns"
        if (preferred / "index.md").exists():
            return preferred
        if ref.exists():
            for d in sorted(ref.iterdir()):
                if d.is_dir() and (d / "index.md").exists():
                    return d
        return None

    # --- index ------------------------------------------------------------
    def _load_index(self) -> Dict[str, PatternEntry]:
        pdir = self._patterns_dir()
        if pdir is None:
            return {}
        index_path = pdir / "index.md"
        if self._cache_path.exists():
            try:
                if self._cache_path.stat().st_mtime >= index_path.stat().st_mtime:
                    with open(self._cache_path, "rb") as f:
                        data = pickle.load(f)
                        if isinstance(data, dict):
                            return data
            except (pickle.UnpicklingError, EOFError, OSError):
                pass

        entries: Dict[str, PatternEntry] = {}
        kw_map = self._load_keyword_map()
        for line in index_path.read_text("utf-8").splitlines():
            if not line.startswith("|") or line.startswith("| :"):
                continue
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]
            if len(cells) < 2 or cells[0] in ("ID", "id"):
                continue
            pid = cells[0]
            if not re.match(r"^[A-Za-z][A-Za-z0-9]*[.:]", pid):
                continue
            # Current layout: ID | Title | Role | Status | File
            if len(cells) >= 5 and cells[2] in ("pattern", "reference", "application",
                                                "sources", "advising", "edition",
                                                "profiles", "reminder", "use", "source"):
                role, status, fname = cells[2], cells[3], cells[4]
            else:  # legacy: ID | Title | Domain | Status
                role = "pattern"
                status = cells[3] if len(cells) > 3 else ""
                fname = id_to_filename(pid) + ".md"
            entries[pid] = PatternEntry(
                pattern_id=pid,
                title=cells[1] if len(cells) > 1 else "",
                domain=pid[0].upper(),
                status=status,
                keywords=kw_map.get(pid, ""),
                file_path=str(pdir.relative_to(self._skill_root) / fname),
                role=role,
            )
        try:
            with open(self._cache_path, "wb") as f:
                pickle.dump(entries, f)
        except OSError:
            pass
        return entries

    def _load_keyword_map(self) -> Dict[str, str]:
        kw_path = self.reference_dir / "keyword-index.md"
        result: Dict[str, List[str]] = {}
        if not kw_path.exists():
            return {}
        for line in kw_path.read_text("utf-8").splitlines():
            if not line.startswith("|") or line.startswith("| :"):
                continue
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]
            if len(cells) < 2 or cells[0].lower() == "keyword":
                continue
            kw = cells[0]
            for pid in cells[1].split(","):
                pid = pid.strip()
                if pid:
                    result.setdefault(pid, []).append(kw)
        return {pid: ", ".join(kws) for pid, kws in result.items()}

    @property
    def entries(self) -> Dict[str, PatternEntry]:
        if self._entries is None:
            self._entries = self._load_index()
        return self._entries

    # --- queries ----------------------------------------------------------
    def search(self, query: str, limit: int = 10) -> List[Tuple[PatternEntry, float]]:
        q = query.lower().strip()
        results: List[Tuple[PatternEntry, float]] = []
        for entry in self.entries.values():
            score = 0.0
            if entry.pattern_id.lower() == q:
                score = 100.0
            elif q in entry.pattern_id.lower():
                score = max(score, 50.0)
            title_lower = entry.title.lower()
            if q == title_lower:
                score = max(score, 80.0)
            elif q in title_lower:
                score = max(score, 30.0)
            if q in entry.keywords.lower():
                score = max(score, 20.0)
            words = q.split()
            if len(words) > 1:
                hits = sum(1 for w in words if w in entry.search_text)
                score = max(score, (hits / len(words)) * 25.0)
            if score > 0:
                results.append((entry, score))
        results.sort(key=lambda x: (-x[1], x[0].pattern_id))
        return results[:limit]

    def get(self, pattern_id: str) -> Optional[PatternEntry]:
        if pattern_id and pattern_id[0].islower():
            pattern_id = pattern_id[0].upper() + pattern_id[1:]
        return self.entries.get(pattern_id)

    def list_domain(self, domain: str) -> List[PatternEntry]:
        domain = domain.upper().strip()
        return sorted(
            [e for e in self.entries.values()
             if e.domain.upper() == domain and e.role == "pattern"],
            key=lambda e: sort_key(e.pattern_id),
        )

    def read_pattern(self, pattern_id: str) -> Optional[str]:
        if pattern_id and pattern_id[0].islower():
            pattern_id = pattern_id[0].upper() + pattern_id[1:]
        pdir = self._patterns_dir()
        if pdir is None:
            return None
        for stem in (id_to_filename(pattern_id), pattern_id):
            path = pdir / f"{stem}.md"
            if path.exists():
                return path.read_text("utf-8")
        for f in pdir.glob(f"{pattern_id}_*.md"):
            return f.read_text("utf-8")
        return None

    def available_in_domain(self, domain: str) -> List[str]:
        return [e.pattern_id for e in self.list_domain(domain)]

    # --- intros and documents --------------------------------------------
    def list_intros(self) -> List[Tuple[str, Path]]:
        ref = self.reference_dir
        if not ref.exists():
            return []
        out: List[Tuple[str, Path]] = []
        for pattern in ("intro/*.md", "*/intro/*.md"):
            for f in sorted(ref.glob(pattern)):
                slug = f.stem
                out.append((slug, f))
        return out

    def read_intro(self, query: str) -> Optional[Tuple[str, str]]:
        q = query.lower().strip()
        intros = self.list_intros()
        if not intros:
            return None
        for slug, path in intros:
            if slug == q:
                return (path.name, path.read_text("utf-8"))
        for slug, path in intros:
            if q in slug:
                return (path.name, path.read_text("utf-8"))
        for slug, path in intros:
            content = path.read_text("utf-8")
            if q in content.lower():
                return (path.name, content)
        return None

    def list_docs(self) -> List[Tuple[str, Path]]:
        ref = self.reference_dir
        if not ref.exists():
            return []
        return [(f.stem, f) for f in sorted(ref.glob("docs/*.md"))]

    def read_doc(self, query: str) -> Optional[Tuple[str, str]]:
        q = query.lower().strip().replace(" ", "-")
        docs = self.list_docs()
        if not docs:
            return None
        for slug, path in docs:
            if slug == q or slug.replace("-", "") == q.replace("-", ""):
                return (path.name, path.read_text("utf-8"))
        for slug, path in docs:
            if q in slug:
                return (path.name, path.read_text("utf-8"))
        for slug, path in docs:
            content = path.read_text("utf-8")
            if q in content.lower():
                return (path.name, content)
        return None


_INDEX: Optional[PatternIndex] = None


def _get_index(skill_root: Optional[Path] = None) -> PatternIndex:
    global _INDEX
    if _INDEX is None or skill_root is not None:
        _INDEX = PatternIndex(skill_root)
    return _INDEX


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

def fpf_search_index(keyword: str, limit: int = 10) -> str:
    index = _get_index()
    results = index.search(keyword, limit)
    if not results:
        return f"No patterns found matching '{keyword}'."
    lines = [f"Search results for '{keyword}':\n"]
    for entry, score in results:
        lines.append(f"  {entry.pattern_id} -- {entry.title} "
                     f"[{entry.role}] (score: {score:.0f})")
    lines.append("\nLoad the file from reference/pattern-index.md.")
    return "\n".join(lines)


def fpf_read_pattern(pattern_id: str) -> str:
    index = _get_index()
    if pattern_id and pattern_id[0].islower():
        pattern_id = pattern_id[0].upper() + pattern_id[1:]
    content = index.read_pattern(pattern_id)
    if content:
        return content
    domain = pattern_id[0].upper() if pattern_id else ""
    available = index.available_in_domain(domain)
    if available:
        avail_str = ", ".join(available[:15])
        if len(available) > 15:
            avail_str += f", ... ({len(available)} available)"
        return f"Pattern '{pattern_id}' not found. Available in {domain}: {avail_str}"
    return f"Pattern '{pattern_id}' not found."


def fpf_list_domain(domain: str) -> str:
    index = _get_index()
    domain = domain.upper().strip()
    if domain not in VALID_DOMAINS:
        return f"Invalid domain '{domain}'. Valid: {', '.join(sorted(VALID_DOMAINS))}"
    entries = index.list_domain(domain)
    if not entries:
        return f"No patterns in domain {domain}."
    lines = [f"Part {domain} -- {DOMAIN_NAMES.get(domain, '')} ({len(entries)} patterns):\n"]
    for e in entries:
        lines.append(f"  {e.pattern_id} - {e.title}")
    return "\n".join(lines)


def fpf_read_intro(query: str) -> str:
    index = _get_index()
    result = index.read_intro(query)
    if result:
        fname, content = result
        return f"# Source: {fname}\n\n{content}"
    intros = index.list_intros()
    if intros:
        slugs = ", ".join(slug for slug, _ in intros)
        return f"Intro section '{query}' not found. Available: {slugs}"
    return "No intro sections found."


def fpf_list_docs() -> str:
    index = _get_index()
    docs = index.list_docs()
    if not docs:
        return "No Library documents shipped in this skill."
    lines = ["Library documents:\n"]
    for slug, path in docs:
        lines.append(f"  {slug}  ({path.name})")
    return "\n".join(lines)


def fpf_read_doc(query: str) -> str:
    index = _get_index()
    result = index.read_doc(query)
    if result:
        fname, content = result
        return f"# Source: {fname}\n\n{content}"
    docs = index.list_docs()
    if docs:
        slugs = ", ".join(slug for slug, _ in docs)
        return f"Document '{query}' not found. Available: {slugs}"
    return "No Library documents shipped in this skill."


def main() -> int:
    parser = argparse.ArgumentParser(description="FPF Pattern Tools")
    parser.add_argument("--skill-root", type=Path, default=None,
                        help="Path to the skill directory (skills/fpf)")
    sub = parser.add_subparsers(dest="command")

    p_s = sub.add_parser("search")
    p_s.add_argument("query")
    p_s.add_argument("--limit", type=int, default=10)

    p_r = sub.add_parser("read")
    p_r.add_argument("pattern_id")

    p_l = sub.add_parser("list")
    p_l.add_argument("domain")

    p_i = sub.add_parser("intro")
    p_i.add_argument("query")

    p_d = sub.add_parser("doc")
    p_d.add_argument("query")

    sub.add_parser("docs")

    args = parser.parse_args()

    if args.skill_root:
        _get_index(args.skill_root)

    if args.command == "search":
        print(fpf_search_index(args.query, args.limit))
    elif args.command == "read":
        print(fpf_read_pattern(args.pattern_id))
    elif args.command == "list":
        print(fpf_list_domain(args.domain))
    elif args.command == "intro":
        print(fpf_read_intro(args.query))
    elif args.command == "doc":
        print(fpf_read_doc(args.query))
    elif args.command == "docs":
        print(fpf_list_docs())
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
