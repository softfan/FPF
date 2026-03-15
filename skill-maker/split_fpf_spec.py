#!/usr/bin/env python3
"""
split_fpf_spec.py — Three-phase splitter for FPF-Spec.md

Exit codes: 0 = success, 1 = parse error.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _fpf_common import (
    PATTERN_ID_RE, PATTERN_HEADING_RE, PATTERN_HEADING_BARE_RE,
    H1_RE, H2_RE, TOC_START_RE, FENCE_OPEN_RE, PART_TOC_RE,
    FenceTracker, sha256, sort_key, clean, slugify,
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    kind: str
    key: str
    content: str
    order: int


@dataclass
class TOCEntry:
    pattern_id: str = ""
    title: str = ""
    status: str = ""
    keywords: str = ""
    search_queries: str = ""
    dependencies: str = ""
    part_name: str = ""
    is_cluster: bool = False

    @property
    def is_stub(self) -> bool:
        return self.status.strip().lower() == "stub"

    @property
    def is_valid(self) -> bool:
        return bool(PATTERN_ID_RE.match(self.pattern_id))


# ---------------------------------------------------------------------------
# Phase 1+2: Streaming parse
# ---------------------------------------------------------------------------

class SpecParser:
    def __init__(self, source: Path, intro_split: str = "h2"):
        self.source = source
        self.intro_split = intro_split
        self.chunks: List[Chunk] = []
        self.toc_entries: List[TOCEntry] = []
        self.toc_raw: str = ""
        self._fence = FenceTracker()

    def _match_pattern_heading(self, line: str):
        if self._fence.in_fence:
            return None
        m = PATTERN_HEADING_RE.match(line)
        if m:
            return m.group("id"), clean(m.group("title"))
        m = PATTERN_HEADING_BARE_RE.match(line)
        if m:
            return m.group("id"), ""
        return None

    def parse(self) -> None:
        in_intro = True
        in_toc = False
        toc_lines: List[str] = []
        intro_sections: List[Tuple[str, List[str]]] = []
        cur_intro_heading = ""
        cur_intro_lines: List[str] = []
        pattern_buf: Optional[Dict[str, Any]] = None
        pending_h1_lines: List[str] = []
        chunk_order = 0
        split_level = 1 if self.intro_split == "h1" else 2

        def flush_intro():
            nonlocal cur_intro_heading, cur_intro_lines
            if cur_intro_lines:
                content = "\n".join(cur_intro_lines)
                if content.strip():
                    intro_sections.append((cur_intro_heading, cur_intro_lines[:]))
            cur_intro_heading = ""
            cur_intro_lines = []

        def flush_pattern():
            nonlocal pattern_buf, chunk_order
            if pattern_buf is not None:
                self.chunks.append(Chunk(
                    kind="pattern", key=f"{pattern_buf['id']}.md",
                    content="\n".join(pattern_buf["lines"]), order=chunk_order,
                ))
                chunk_order += 1
                pattern_buf = None

        def start_pattern(pid, title, heading_line):
            nonlocal pattern_buf, pending_h1_lines
            flush_pattern()
            lines = pending_h1_lines + [heading_line]
            pending_h1_lines = []
            pattern_buf = {"id": pid, "title": title, "lines": lines}

        with open(self.source, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                self._fence.update(line)

                if in_intro:
                    if not self._fence.in_fence and TOC_START_RE.match(line):
                        flush_intro()
                        in_toc = True
                        toc_lines = [line]
                        cur_intro_heading = "Table of Content"
                        cur_intro_lines = [line]
                        continue
                    if in_toc:
                        ph = self._match_pattern_heading(line)
                        if ph:
                            in_toc = False
                            in_intro = False
                            self.toc_raw = "\n".join(toc_lines)
                            self._parse_toc(toc_lines)
                            flush_intro()
                            for heading, hlines in intro_sections:
                                slug = slugify(heading) if heading else "preamble"
                                self.chunks.append(Chunk(
                                    kind="intro", key=f"intro_{slug}.md",
                                    content="\n".join(hlines), order=chunk_order,
                                ))
                                chunk_order += 1
                            start_pattern(ph[0], ph[1], line)
                            continue
                        else:
                            toc_lines.append(line)
                            cur_intro_lines.append(line)
                            continue
                    if not self._fence.in_fence:
                        h1m = H1_RE.match(line)
                        h2m = H2_RE.match(line)
                        if h1m:
                            flush_intro()
                            cur_intro_heading = clean(h1m.group(1))
                            cur_intro_lines = [line]
                            continue
                        elif h2m and split_level <= 2:
                            flush_intro()
                            cur_intro_heading = clean(h2m.group(1))
                            cur_intro_lines = [line]
                            continue
                    cur_intro_lines.append(line)
                    continue

                if not self._fence.in_fence:
                    ph = self._match_pattern_heading(line)
                    if ph:
                        start_pattern(ph[0], ph[1], line)
                        continue
                    h1m = H1_RE.match(line)
                    if h1m:
                        flush_pattern()
                        pending_h1_lines.append(line)
                        continue

                if pattern_buf is not None:
                    pattern_buf["lines"].append(line)
                elif pending_h1_lines:
                    pending_h1_lines.append(line)

        if in_intro:
            flush_intro()
            for heading, hlines in intro_sections:
                slug = slugify(heading) if heading else "preamble"
                self.chunks.append(Chunk(
                    kind="intro", key=f"intro_{slug}.md",
                    content="\n".join(hlines), order=chunk_order,
                ))
                chunk_order += 1
        flush_pattern()
        if pending_h1_lines and self.chunks:
            self.chunks[-1].content += "\n" + "\n".join(pending_h1_lines)

    def _parse_toc(self, lines: List[str]) -> None:
        part = "Preface"
        cols: Optional[List[str]] = None
        for line in lines:
            s = line.strip()
            pm = PART_TOC_RE.search(s)
            if pm:
                part = f"Part {pm.group(1)}"; continue
            if s.startswith("**Preface") or s.startswith("*Preface"):
                part = "Preface"; continue
            if not s.startswith("|"): continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not cells: continue
            if all(re.match(r"^:?-+:?$", c) for c in cells if c): continue
            first = cells[0].lower().replace("*", "")
            if first in ("§", "id", "id & title") or "status" in first:
                cols = [c.lower().replace("*", "") for c in cells]; continue
            entry = self._parse_row(cells, cols, part)
            if entry:
                self.toc_entries.append(entry)

    def _parse_row(self, cells, cols, part) -> Optional[TOCEntry]:
        e = TOCEntry(part_name=part)
        if cols is None:
            if len(cells) >= 2:
                e.title = clean(cells[0])
                e.status = cells[1].replace("*", "").strip() if len(cells) > 1 else ""
            return e if e.title else None
        for i, cell in enumerate(cells):
            if i >= len(cols): break
            c = cols[i]; v = cell.strip()
            if "§" in c:
                m = re.match(r"\*?\*?([A-K](?:\.(?:\d+|[A-Za-z]\w*))+)", clean(v))
                if m: e.pattern_id = m.group(1)
            elif "id" in c and "title" in c:
                t = clean(v)
                m = re.match(r"([A-K](?:\.(?:\d+|[A-Za-z]\w*))+)\s*[-–—:]?\s*(.*)", t)
                if m: e.pattern_id = m.group(1); e.title = m.group(2).strip()
                else: e.title = t
            elif c.strip() == "id":
                m = re.match(r"([A-K](?:\.(?:\d+|[A-Za-z]\w*))+)", clean(v))
                if m: e.pattern_id = m.group(1)
            elif "status" in c: e.status = clean(v)
            elif "keyword" in c or "search" in c or "queries" in c:
                cv = v.replace("*", "")
                km = re.search(r"Keywords?:?\s*(.+?)(?:Queries?:|$)", cv, re.I | re.S)
                if km: e.keywords = km.group(1).strip().rstrip(".")
                qm = re.search(r"Queries?:?\s*(.+)", cv, re.I | re.S)
                if qm: e.search_queries = qm.group(1).strip()
                if not km and not qm: e.keywords = cv
            elif "depend" in c: e.dependencies = v
            elif "title" in c: e.title = clean(v)
        if not e.pattern_id and e.title:
            m = re.match(r"([A-K](?:\.(?:\d+|[A-Za-z]\w*))+)", e.title)
            if m:
                e.pattern_id = m.group(1)
                e.title = e.title[m.end():].strip().lstrip("-–— :")
        if not e.pattern_id and ("cluster" in (e.title or "").lower()):
            e.is_cluster = True
        return e if (e.pattern_id or e.title) else None


# ---------------------------------------------------------------------------
# Phase 3: Generate files
# ---------------------------------------------------------------------------

DOMAIN_DESCRIPTIONS = {
    "A": "Kernel Architecture -- Ontology, holons, bounded contexts, transformers",
    "B": "Trans-disciplinary Reasoning -- Gamma algebra, assurance F-G-R, loops",
    "C": "Kernel Extensions -- Pluggable calculi (CAL), logics (LOG), CHR",
    "D": "Multi-scale Ethics -- Bias audits, conflict-optimisation",
    "E": "Constitution & Authoring -- 11 Pillars, guard-rails, MVPK, TGA",
    "F": "Unification Suite -- SenseCells, concept-sets, alignment bridges",
    "G": "Discipline SoTA Kit -- SoTA harvesting, benchmarks, portfolios",
    "H": "Glossary & Index", "I": "Annexes & Tutorials",
    "J": "Indexes & Navigation", "K": "Lexical Debt & Replacement Maps",
}


class FileWriter:
    SKILL_SCRIPTS = [
        "_fpf_common.py",
        "fpf_tools.py",
        "audit_fpf_patterns.py",
    ]



    def __init__(self, parser: SpecParser, output: Path,
                 readme_path: Optional[Path] = None,
                 maker_dir: Optional[Path] = None):
        self.parser = parser
        self.output = output
        self.ref = output / "reference"
        self.pats = self.ref / "fpf-patterns"
        self.scripts_dir = output / "scripts"
        self._hpath = output / ".fpf_hashes.json"
        self._mpath = output / ".fpf_manifest.json"
        self._readme_path = readme_path
        self._maker_dir = maker_dir or _SCRIPT_DIR
        self._templates_dir = self._maker_dir / "templates"
        self._old: Dict[str, str] = {}
        self._new: Dict[str, str] = {}
        self._written = 0
        self._skipped = 0

    def write_all(self) -> Dict[str, int]:
        self._load_cache()
        self.pats.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        manifest: List[Dict[str, str]] = []
        for chunk in self.parser.chunks:
            path = (self.ref / chunk.key) if chunk.kind == "intro" else (self.pats / chunk.key)
            self._put(path, chunk.content)
            manifest.append({"kind": chunk.kind, "key": chunk.key, "order": chunk.order})

        self._mpath.write_text(json.dumps(manifest, indent=2), "utf-8")

        if self.parser.toc_raw:
            self._put(self.ref / "intro_table_of_content.md", self.parser.toc_raw)

        toc_map = {e.pattern_id: e for e in self.parser.toc_entries if e.pattern_id}
        pat_ids = [c.key[:-3] for c in self.parser.chunks if c.kind == "pattern"]
        intro_keys = [c.key for c in self.parser.chunks if c.kind == "intro"]

        self._gen_pattern_index(toc_map, pat_ids)
        self._gen_agent_patterns(toc_map, pat_ids)
        self._gen_agent_keywords(toc_map)
        self._gen_agent_queries(toc_map)
        self._gen_skill_md(toc_map, pat_ids, intro_keys)
        self._gen_readme(pat_ids)
        self._copy_scripts()
        self._gen_init()

        self._save_cache()
        return {"written": self._written, "skipped": self._skipped}

    def _put(self, path: Path, content: str) -> bool:
        h = sha256(content)
        rel = str(path.relative_to(self.output))
        self._new[rel] = h
        if self._old.get(rel) == h and path.exists():
            self._skipped += 1
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, "utf-8")
        self._written += 1
        return True

    def _put_bytes(self, path: Path, data: bytes) -> bool:
        """Write raw bytes (for copying scripts that may have varied encodings)."""
        h = sha256(data.decode("utf-8", errors="replace"))
        rel = str(path.relative_to(self.output))
        self._new[rel] = h
        if self._old.get(rel) == h and path.exists():
            self._skipped += 1
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._written += 1
        return True

    def _load_cache(self):
        if self._hpath.exists():
            try: self._old = json.loads(self._hpath.read_text("utf-8"))
            except Exception: self._old = {}

    def _save_cache(self):
        self._hpath.write_text(json.dumps(self._new, indent=2), "utf-8")


    def _copy_scripts(self):
        """Copy runtime scripts from skill-maker/ into skills/fpf/scripts/ as raw bytes."""
        for name in self.SKILL_SCRIPTS:
            src = self._maker_dir / name
            if not src.exists():
                print(f"  Warning: {src} not found, skipping", file=sys.stderr)
                continue
            self._put_bytes(self.scripts_dir / name, src.read_bytes())



    # --- Index generators ---

    def _gen_pattern_index(self, toc, pids):
        lines = ["# FPF Pattern Index", "",
                 "| ID | Title | Domain | Status |", "| :--- | :--- | :--- | :--- |"]
        for pid in sorted(pids, key=sort_key):
            e = toc.get(pid)
            lines.append(f"| {pid} | {e.title if e else ''} | {pid[0]} | {e.status if e else ''} |")
        self._put(self.pats / "index.md", "\n".join(lines) + "\n")

    def _gen_agent_patterns(self, toc, pids):
        lines = [
            "# FPF Pattern Index (Agent)", "",
            "## Range expansion", "",
            "En-dash `\u2013` \u2192 enumerate: `C.17\u2013C.19` \u2192 `C.17, C.18, C.19`.", "",
            "## Kernel patterns (no deps)", "",
        ]
        kernel = []
        for pid in sorted(toc, key=sort_key):
            e = toc[pid]; d = e.dependencies.strip()
            if not d or d in ("\u2014", "-"):
                kernel.append(pid)
            elif "prerequisite for" in d.lower() and "builds on" not in d.lower():
                kernel.append(pid)
        lines.append(", ".join(f"`{k}`" for k in kernel) + "\n")
        lines += ["## All Patterns", "", "| ID | Title | Builds on |", "| :--- | :--- | :--- |"]
        for pid in sorted(pids, key=sort_key):
            e = toc.get(pid); t = e.title if e else ""; bo = ""
            if e and e.dependencies:
                m = re.search(r"Builds?\s+on:?\s*\*?\*?\s*(.+?)(?:\.\s*\*|\*|\.?\s*$)",
                              e.dependencies, re.I)
                if m: bo = m.group(1).strip().rstrip(".")
            lines.append(f"| {pid} | {t} | {bo} |")
        self._put(self.ref / "agent_index_patterns.md", "\n".join(lines) + "\n")

    def _gen_agent_keywords(self, toc):
        kw: Dict[str, Set[str]] = {}
        for pid, e in toc.items():
            if not e.keywords: continue
            for w in e.keywords.replace("*", "").split(","):
                w = w.strip().strip(".")
                if w and len(w) > 1:
                    kw.setdefault(w.lower(), set()).add(pid)
        lines = ["# FPF Keyword Index", "", "| Keyword | Pattern IDs |", "| :--- | :--- |"]
        for k in sorted(kw):
            lines.append(f"| {k} | {', '.join(sorted(kw[k], key=sort_key))} |")
        self._put(self.ref / "agent_index_keywords.md", "\n".join(lines) + "\n")

    def _gen_agent_queries(self, toc):
        lines = ["# FPF Query Index", "", "| Query | Pattern ID |", "| :--- | :--- |"]
        for pid in sorted(toc, key=sort_key):
            e = toc[pid]
            if e.search_queries:
                qs = re.findall(r'"([^"]+)"', e.search_queries)
                if not qs:
                    qs = [q.strip().strip('"\'') for q in re.split(r'[?.]', e.search_queries)
                          if q.strip() and len(q.strip()) > 5]
                for q in qs:
                    q = q.strip().rstrip("?").strip()
                    if q: lines.append(f"| {q}? | {pid} |")
            elif e.title:
                lines.append(f"| {e.title} | {pid} |")
        self._put(self.ref / "agent_index_queries.md", "\n".join(lines) + "\n")

    # --- SKILL.md from template ---

    def _gen_skill_md(self, toc_map, pat_ids, intro_keys):
        doms: Dict[str, int] = {}
        for p in pat_ids:
            doms[p[0]] = doms.get(p[0], 0) + 1

        domain_lines = []
        for d in sorted(doms):
            domain_lines.append(f"- **Part {d}** -- {DOMAIN_DESCRIPTIONS.get(d, d)} ({doms[d]} patterns)")

        kernel = []
        for pid in sorted(toc_map, key=sort_key):
            e = toc_map[pid]; dep = e.dependencies.strip()
            if not dep or dep in ("\u2014", "-"):
                kernel.append(pid)
            elif "prerequisite for" in dep.lower() and "builds on" not in dep.lower():
                kernel.append(pid)
        kernel_str = ", ".join(f"`{k}`" for k in kernel[:20])
        if len(kernel) > 20:
            kernel_str += f", ... ({len(kernel)} total)"

        intro_lines = [f"- [{k}](reference/{k})" for k in intro_keys]

        replacements = {
            "{{KERNEL_PATTERNS}}": kernel_str,
            "{{PATTERN_COUNT}}": str(len(pat_ids)),
            "{{DOMAIN_BLOCK}}": "\n".join(domain_lines),
            "{{INTRO_BLOCK}}": "\n".join(intro_lines) if intro_lines else "_(none)_",
        }

        template = self._load_template("SKILL.md.template")
        content = template
        for key, val in replacements.items():
            content = content.replace(key, val)

        self._put(self.output / "SKILL.md", content)

    # --- README.md ---

    def _gen_readme(self, pat_ids):
        # Try to use external README from source dir
        external = self._load_external_readme()
        if external:
            self._put(self.output / "README.md", external)
            return

        # Use template
        doms: Dict[str, int] = {}
        for p in pat_ids:
            doms[p[0]] = doms.get(p[0], 0) + 1

        replacements = {
            "{{PATTERN_COUNT}}": str(len(pat_ids)),
            "{{DOMAIN_COUNT}}": str(len(doms)),
        }

        template = self._load_template("README.md.template")
        content = template
        for key, val in replacements.items():
            content = content.replace(key, val)

        self._put(self.output / "README.md", content)

    def _load_external_readme(self) -> Optional[str]:
        if self._readme_path and self._readme_path.exists():
            return self._readme_path.read_text("utf-8")
        candidates = [
            self.parser.source.parent / "README.md",
            self.parser.source.parent / "Readme.md",
            self.parser.source.parent / "Readme-for-FPF-Spec.md",
        ]
        for c in candidates:
            if c.exists():
                content = c.read_text("utf-8")
                if re.search(r"First\s+Principles\s+Framework|FPF", content, re.I):
                    return content
        return None

    def _load_template(self, name: str) -> str:
        """Load a template file from templates/ directory."""
        path = self._templates_dir / name
        if path.exists():
            return path.read_text("utf-8")
        # Fallback: return a minimal placeholder
        print(f"  Warning: template {path} not found, using fallback", file=sys.stderr)
        return f"# {name}\n\nTemplate not found. Re-run with templates/ directory.\n"

    def _gen_init(self):
        self._put(self.scripts_dir / "__init__.py",
                  "from .fpf_tools import fpf_search_index, fpf_read_pattern, fpf_list_domain, fpf_read_intro\n"
                  "__all__ = ['fpf_search_index', 'fpf_read_pattern', 'fpf_list_domain', 'fpf_read_intro']\n")


# ---------------------------------------------------------------------------
# Rebuild
# ---------------------------------------------------------------------------

def rebuild_spec(skill_dir: Path, output: Path) -> None:
    mpath = skill_dir / ".fpf_manifest.json"
    if not mpath.exists():
        print(f"Error: manifest not found at {mpath}", file=sys.stderr)
        sys.exit(1)
    manifest = json.loads(mpath.read_text("utf-8"))
    manifest.sort(key=lambda x: x["order"])
    parts: List[str] = []
    for entry in manifest:
        if entry["kind"] == "intro":
            path = skill_dir / "reference" / entry["key"]
        else:
            path = skill_dir / "reference" / "fpf-patterns" / entry["key"]
        if not path.exists():
            print(f"Warning: {path} missing", file=sys.stderr); continue
        parts.append(path.read_text("utf-8"))
    rebuilt = "\n".join(parts)
    if rebuilt and not rebuilt.endswith("\n"):
        rebuilt += "\n"
    output.write_text(rebuilt, "utf-8")
    print(f"Rebuilt: {output} ({len(rebuilt)} bytes)")


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------

def analyze(source: Path):
    p = SpecParser(source)
    p.parse()
    intros = [c for c in p.chunks if c.kind == "intro"]
    pats = [c for c in p.chunks if c.kind == "pattern"]
    total = sum(len(c.content.encode("utf-8")) for c in p.chunks)
    print(f"=== Analysis ===\nSource: {source}")
    print(f"Chunks: {len(p.chunks)} ({len(intros)} intro, {len(pats)} patterns)")
    print(f"TOC entries: {len(p.toc_entries)}\nSize: ~{total / 1024 / 1024:.2f} MB")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(prog="split_fpf_spec")
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("split")
    s.add_argument("--source", required=True, type=Path)
    s.add_argument("--output", required=True, type=Path)
    s.add_argument("--intro-split", choices=["h1", "h2"], default="h2")
    s.add_argument("--readme", type=Path, default=None)

    a = sub.add_parser("analyze")
    a.add_argument("--source", required=True, type=Path)

    r = sub.add_parser("rebuild")
    r.add_argument("--skill-dir", required=True, type=Path)
    r.add_argument("--output", required=True, type=Path)

    d = sub.add_parser("diff")
    d.add_argument("--source", required=True, type=Path)
    d.add_argument("--skill-dir", required=True, type=Path)

    args = ap.parse_args()

    if args.cmd == "split":
        if not args.source.exists():
            print(f"Error: {args.source} not found", file=sys.stderr); return 1
        print(f"Parsing {args.source}...")
        p = SpecParser(args.source, args.intro_split)
        p.parse()
        pats = [c for c in p.chunks if c.kind == "pattern"]
        intros = [c for c in p.chunks if c.kind == "intro"]
        print(f"  {len(pats)} patterns, {len(intros)} intro sections, {len(p.toc_entries)} TOC entries")
        print(f"Writing {args.output}/...")
        w = FileWriter(p, args.output, readme_path=args.readme)
        stats = w.write_all()
        print(f"  Written: {stats['written']}, Skipped: {stats['skipped']}")
        return 0
    elif args.cmd == "analyze":
        analyze(args.source); return 0
    elif args.cmd == "rebuild":
        rebuild_spec(args.skill_dir, args.output); return 0
    elif args.cmd == "diff":
        p = SpecParser(args.source); p.parse()
        pdir = args.skill_dir / "reference" / "fpf-patterns"
        new = {c.key[:-3] for c in p.chunks if c.kind == "pattern"}
        old = {f.stem for f in pdir.glob("*.md") if f.name != "index.md"} if pdir.exists() else set()
        added = sorted(new - old, key=sort_key)
        removed = sorted(old - new, key=sort_key)
        changed = []
        for pid in sorted(new & old, key=sort_key):
            nc = next(c for c in p.chunks if c.kind == "pattern" and c.key == f"{pid}.md")
            oc = (pdir / f"{pid}.md").read_text("utf-8")
            if sha256(nc.content) != sha256(oc): changed.append(pid)
        print(f"Added: {len(added)}, Removed: {len(removed)}, Changed: {len(changed)}, "
              f"Unchanged: {len((new & old) - set(changed))}")
        for p_ in added: print(f"  + {p_}")
        for p_ in removed: print(f"  - {p_}")
        for p_ in changed: print(f"  ~ {p_}")
        return 0

    ap.print_help(); return 1


if __name__ == "__main__":
    sys.exit(main())