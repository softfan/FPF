#!/usr/bin/env python3
"""
fpf_tools.py -- Search, read, and navigate FPF patterns and intro sections.

Four tool functions (sync, no framework dependency):
  fpf_search_index, fpf_read_pattern, fpf_list_domain, fpf_read_intro

Usage:
    python skill-maker/fpf_tools.py --skill-root skills/fpf search "holon"
    python skill-maker/fpf_tools.py --skill-root skills/fpf read A.1
    python skill-maker/fpf_tools.py --skill-root skills/fpf list A
    python skill-maker/fpf_tools.py --skill-root skills/fpf intro "preface"
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

# Ensure UTF-8 stdout for cp1251 consoles
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# Ensure sibling modules are importable regardless of cwd
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from _fpf_common import sort_key
except ImportError:
    def sort_key(pattern_id: str) -> tuple:
        parts = pattern_id.split(".")
        result = []
        for p in parts:
            try:
                result.append((0, int(p), ""))
            except ValueError:
                result.append((1, 0, p))
        return tuple(result)


@dataclass
class PatternEntry:
    pattern_id: str
    title: str
    domain: str
    status: str
    keywords: str = ""
    file_path: str = ""

    @property
    def search_text(self) -> str:
        return f"{self.pattern_id} {self.title} {self.keywords}".lower()


class PatternIndex:
    def __init__(self, skill_root: Optional[Path] = None):
        self._skill_root = skill_root or self._detect_skill_root()
        self._entries: Optional[Dict[str, PatternEntry]] = None
        self._cache_path = self._skill_root / ".fpf_index.pickle"

    @staticmethod
    def _detect_skill_root() -> Path:
        env = os.environ.get("FPF_SKILL_ROOT")
        if env:
            return Path(env)
        here = Path(__file__).resolve().parent
        if here.name == "scripts" and (here.parent / "SKILL.md").exists():
            return here.parent
        if (here.parent / "SKILL.md").exists():
            return here.parent
        cwd_skill = Path.cwd() / "skills" / "fpf"
        if (cwd_skill / "SKILL.md").exists():
            return cwd_skill
        return here.parent

    @property
    def skill_root(self) -> Path:
        return self._skill_root

    def _load_index(self) -> Dict[str, PatternEntry]:
        index_path = self._skill_root / "reference" / "fpf-patterns" / "index.md"
        if not index_path.exists():
            return {}
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
            if not re.match(r"[A-K]", pid):
                continue
            entries[pid] = PatternEntry(
                pattern_id=pid, title=cells[1] if len(cells) > 1 else "",
                domain=cells[2] if len(cells) > 2 else pid[0],
                status=cells[3] if len(cells) > 3 else "",
                keywords=kw_map.get(pid, ""),
                file_path=f"reference/fpf-patterns/{pid}.md",
            )
        try:
            with open(self._cache_path, "wb") as f:
                pickle.dump(entries, f)
        except OSError:
            pass
        return entries

    def _load_keyword_map(self) -> Dict[str, str]:
        kw_path = self._skill_root / "reference" / "agent_index_keywords.md"
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
            [e for e in self.entries.values() if e.domain.upper() == domain],
            key=lambda e: sort_key(e.pattern_id),
        )

    def read_pattern(self, pattern_id: str) -> Optional[str]:
        if pattern_id and pattern_id[0].islower():
            pattern_id = pattern_id[0].upper() + pattern_id[1:]
        path = self._skill_root / "reference" / "fpf-patterns" / f"{pattern_id}.md"
        if path.exists():
            return path.read_text("utf-8")
        for f in (self._skill_root / "reference" / "fpf-patterns").glob(f"{pattern_id}_*.md"):
            return f.read_text("utf-8")
        return None

    def available_in_domain(self, domain: str) -> List[str]:
        domain = domain.upper()
        return sorted(
            [e.pattern_id for e in self.entries.values() if e.domain.upper() == domain],
            key=sort_key,
        )

    def list_intros(self) -> List[Tuple[str, Path]]:
        ref = self._skill_root / "reference"
        if not ref.exists():
            return []
        return [(f.stem.replace("intro_", "", 1), f) for f in sorted(ref.glob("intro_*.md"))]

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


_INDEX: Optional[PatternIndex] = None

def _get_index(skill_root: Optional[Path] = None) -> PatternIndex:
    global _INDEX
    if _INDEX is None or skill_root is not None:
        _INDEX = PatternIndex(skill_root)
    return _INDEX


DOMAIN_NAMES = {
    "A": "Kernel Architecture", "B": "Trans-disciplinary Reasoning",
    "C": "Kernel Extensions", "D": "Multi-scale Ethics",
    "E": "Constitution & Authoring", "F": "Unification Suite",
    "G": "Discipline SoTA Patterns", "H": "Glossary & Index",
    "I": "Annexes & Tutorials", "J": "Indexes & Navigation",
    "K": "Lexical Debt",
}
VALID_DOMAINS = set("ABCDEFGHIJK")


def fpf_search_index(keyword: str, limit: int = 10) -> str:
    index = _get_index()
    results = index.search(keyword, limit)
    if not results:
        return f"No patterns found matching '{keyword}'."
    lines = [f"Search results for '{keyword}':\n"]
    for entry, score in results:
        lines.append(f"  {entry.pattern_id} -- {entry.title} (score: {score:.0f})")
    lines.append(f"\nLoad: reference/fpf-patterns/<ID>.md")
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
            avail_str += f", ... ({len(available)} total)"
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


def main() -> int:
    parser = argparse.ArgumentParser(description="FPF Pattern Tools")
    parser.add_argument("--skill-root", type=Path, default=None,
                        help="Path to skills/fpf/ directory")
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
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
