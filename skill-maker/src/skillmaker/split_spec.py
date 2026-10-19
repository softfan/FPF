#!/usr/bin/env python3
"""
split_spec.py -- Config-driven splitter for skill generation.

One generic engine turns a source publication into an agent-readable skill:
per-unit files, navigation indexes, ``SKILL.md`` and ``README.md``.  It is
driven entirely by a ``SkillConfig`` (see ``skill_config.py``), so FPF Core,
DPF Suites and standalone frameworks share one parser.

Parsing model
-------------
A publication is a sequence of sections.  ``# <H1>`` headings open a section;
``## <ID> - <Title>`` headings open an addressable *unit*:

* a unit whose first segment after the prefix is numeric is a **pattern**
  (``SYSE.24``, ``A.1``, ``C.40.OD``);
* a unit whose first segment is a word is a **reference unit** of that role
  (``MATH.Reference:3.2``, ``PSDA.Application:1``, ``SYSE.Sources:2``).

Everything else (readme prose, ``Practical entries``, ``Contents``) becomes an
*intro* chunk.  A heading-only section (a ``# Part I`` divider, a trailing
``# Sources and Edition Notes`` header) is held and prepended to the next unit
or intro so no empty files are produced.

Exit codes: 0 = success, 1 = parse error.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

_SCRIPT_DIR = Path(__file__).resolve().parent

#: Import name of this package.  A built skill carries a copy of it under
#: ``scripts/skillmaker/``, so the copied tree presents the same names.
_PKG_NAME = "skillmaker"

_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import (
    FenceTracker, clean, id_to_filename, intro_slug, is_end_marker,
    sha256, sort_key, unit_role, write_text_lf, ID_SEGMENT_RE, manifest_entry_path,
)

from skillmaker.frameworks.grammar import split_heading
from skillmaker import sections as section_map
from skillmaker import derive
from skillmaker import skill_root
from skillmaker.frameworks import genre as genre_mod

from skillmaker.skill_config import SkillConfig, FrameworkSpec


# ---------------------------------------------------------------------------
# Regex construction
# ---------------------------------------------------------------------------

def _build_id_fragment(prefix_re: str) -> str:
    return r"(?:" + prefix_re + r")" + ID_SEGMENT_RE


def build_heading_re(framework: FrameworkSpec):
    frag = _build_id_fragment(framework.prefix_re)
    with_title = re.compile(
        r"^##\s+(?:\*\*)?(?P<id>" + frag + r")(?=\s|$)"
        r"(?:\*\*)?\s*[-–—:]\s*(?P<title>.+)$"
    )
    bare = re.compile(
        r"^##\s+(?:\*\*)?(?P<id>" + frag + r")(?:\*\*)?\s*$"
    )
    return with_title, bare


def build_skill_id_re(config: SkillConfig):
    frags = "|".join(_build_id_fragment(f.prefix_re) for f in config.frameworks)
    return re.compile(r"^(?:" + frags + r")$")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    kind: str                 # "intro" | "unit"
    key: str                  # file name relative to its directory
    content: str
    order: int
    framework_key: str = ""
    id: str = ""              # unit ID (empty for intros)
    title: str = ""
    role: str = ""            # pattern | reference | application | ...


@dataclass
class TOCEntry:
    pattern_id: str = ""
    title: str = ""
    status: str = ""
    keywords: str = ""
    search_queries: str = ""
    dependencies: str = ""
    framework_key: str = ""

    @property
    def is_stub(self) -> bool:
        return self.status.strip().lower() in ("stub", "transitional stub")

    @property
    def is_valid(self) -> bool:
        return bool(self.pattern_id)


# ---------------------------------------------------------------------------
# Parser (one source document)
# ---------------------------------------------------------------------------

class SpecParser:
    """Split one publication into intro chunks and addressable units."""

    def __init__(self, config: SkillConfig, framework: FrameworkSpec):
        self.config = config
        self.framework = framework
        self.grammar = getattr(framework, "grammar", None)
        self.heading_re, self.bare_heading_re = build_heading_re(framework)
        self.chunks: List[Chunk] = []
        self.toc_entries: List[TOCEntry] = []
        self.toc_raw: str = ""
        self.pattern_ids: Set[str] = set()
        self._fence = FenceTracker()
        self._order = 0
        self._used_intro_keys: Set[str] = set()
        self._dropped: List[str] = []
        self._closed: List[str] = []

    # --- helpers -----------------------------------------------------------
    def _match_unit_heading(self, line: str):
        """Return ``(id, title)`` for a unit heading, else ``None``.

        Two modes.  Without a grammar the heading regex is built from the
        publication's ID prefix, which is how FPF Core and the DPFs have always
        been parsed.  With a grammar (ADR, standards, pattern languages,
        generic Markdown) the grammar itself decides what a unit is, so a new
        framework kind needs no new parsing code.
        """
        if self._fence.in_fence:
            return None
        if self.grammar is not None:
            found = split_heading(line, self.grammar)
            if found is None:
                return None
            return found[0], clean(found[1])
        m = self.heading_re.match(line)
        if m:
            return m.group("id"), clean(m.group("title"))
        m = self.bare_heading_re.match(line)
        if m:
            return m.group("id"), ""
        return None

    def _emit_intro(self, heading: str, lines: List[str]) -> None:
        if not lines:
            return
        content = "\n".join(lines)
        if not content.strip():
            return
        slug = intro_slug(heading)
        # A Suite bundles several publications, and they share section names:
        # four of them have an ``Architectural Reference``, three a
        # ``Table of Content``.  Without the framework key they all landed on
        # one file and the last writer won -- a silent loss of four fifths of
        # the front matter, and a different winner depending on build order.
        if len(self.config.frameworks) > 1:
            slug = f"{self.framework.key}_{slug}"
        key = f"{slug}.md"
        if key in self._used_intro_keys:
            n = 2
            while f"{slug}_{n}.md" in self._used_intro_keys:
                n += 1
            key = f"{slug}_{n}.md"
        self._used_intro_keys.add(key)
        self.chunks.append(Chunk(
            kind="intro", key=key, content=content, order=self._order,
            framework_key=self.framework.key,
        ))
        self._order += 1

    def _emit_unit(self, unit: Dict[str, Any]) -> None:
        pid = unit["id"]
        if (self.grammar.is_end_marker(pid) if self.grammar
                else is_end_marker(pid)):
            # ``## X.Reference:End`` closes the preceding block.  Keep the line
            # with that block so the publication can be reassembled exactly,
            # but never create a file that holds only an end marker.
            if self.chunks:
                self.chunks[-1].content += "\n" + "\n".join(unit["lines"])
                self._closed.append(pid)
            else:
                self._dropped.append(pid)
            return
        body = unit["lines"][1:]
        if not any(l.strip() for l in body):
            self._dropped.append(pid)
            return
        role = self.grammar.classify(pid) if self.grammar else unit_role(pid)
        stem = (self.grammar.filename(pid, unit["title"]) if self.grammar
                else id_to_filename(pid))
        self.chunks.append(Chunk(
            kind="unit",
            key=stem + ".md",
            content="\n".join(unit["lines"]),
            order=self._order,
            framework_key=self.framework.key,
            id=pid,
            title=unit["title"],
            role=role,
        ))
        self._order += 1

    # --- main parse --------------------------------------------------------
    def parse(self) -> None:
        cfg = self.config
        fw = self.framework
        h1_re = cfg.h1_compiled()
        h2_re = cfg.h2_compiled()
        toc_re = cfg.toc_re()
        split_at_h2 = cfg.intro_split == "h2"

        held: List[str] = []
        intro: Optional[Dict[str, Any]] = None
        unit: Optional[Dict[str, Any]] = None
        in_toc = False
        toc_lines: List[str] = []

        def flush_intro() -> None:
            nonlocal intro
            if intro is None:
                return
            body = intro["lines"][1:]
            if not any(l.strip() for l in body):
                held.extend(intro["lines"])
                intro = None
                return
            lines = held + intro["lines"]
            del held[:]
            self._emit_intro(intro["heading"], lines)
            intro = None

        def flush_unit() -> None:
            nonlocal unit
            if unit is None:
                return
            self._emit_unit(unit)
            unit = None

        def start_intro(line: str) -> None:
            nonlocal intro
            flush_intro()
            intro = {"heading": line, "lines": [line]}

        def start_unit(pid: str, title: str, line: str) -> None:
            nonlocal unit
            flush_intro()
            flush_unit()
            unit = {"id": pid, "title": title, "lines": held + [line]}
            del held[:]

        def close_toc() -> None:
            nonlocal in_toc
            in_toc = False
            self.toc_raw = "\n".join(toc_lines)
            self._parse_toc(toc_lines)

        with open(fw.source, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                self._fence.update(line)
                in_fence = self._fence.in_fence

                if in_toc and not in_fence:
                    if line.startswith("# ") or self._match_unit_heading(line):
                        close_toc()
                        # fall through to normal handling
                    else:
                        toc_lines.append(line)
                        if intro is not None:
                            intro["lines"].append(line)
                        else:
                            start_intro(line)
                        continue

                if not in_fence:
                    h1m = h1_re.match(line)
                    if h1m:
                        flush_unit()
                        flush_intro()
                        if held:
                            self._emit_intro(held[-1], held[:])
                            del held[:]
                        start_intro(line)
                        if toc_re.match(line):
                            in_toc = True
                            toc_lines = [line]
                        continue

                    ph = self._match_unit_heading(line)
                    if ph:
                        start_unit(ph[0], ph[1], line)
                        continue

                    h2m = h2_re.match(line)
                    if h2m and split_at_h2 and unit is None:
                        start_intro(line)
                        continue

                # ordinary body line
                if unit is not None:
                    unit["lines"].append(line)
                elif intro is not None:
                    intro["lines"].append(line)
                else:
                    start_intro("")
                    intro["lines"].append(line)

        # EOF
        flush_unit()
        flush_intro()
        if held:
            self._emit_intro(held[-1], held[:])
            del held[:]
        if in_toc:
            close_toc()

    # --- TOC parsing -------------------------------------------------------
    def _parse_toc(self, lines: List[str]) -> None:
        cfg = self.config
        fw = self.framework
        cols: Optional[List[str]] = None
        pattern_table = False
        for line in lines:
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not cells:
                continue
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                continue
            first = cells[0].lower().replace("*", "")
            if first in ("§", "id", "id & title") or "status" in first:
                cols = [c.lower().replace("*", "") for c in cells]
                # Only the main pattern table declares dependencies; the
                # "Public units" / readme tables list reference units.
                pattern_table = "depend" in " ".join(cols)
                continue
            entry = self._parse_row(cells, cols)
            if entry:
                entry.framework_key = fw.key
                self.toc_entries.append(entry)
                if pattern_table and entry.pattern_id:
                    self.pattern_ids.add(entry.pattern_id)

    def _parse_row(self, cells, cols) -> Optional[TOCEntry]:
        cfg = self.config
        fw = self.framework
        e = TOCEntry()
        id_frag = _build_id_fragment(fw.prefix_re)

        if cfg.toc_id_location == "section":
            if cols is None:
                if len(cells) >= 2:
                    e.title = clean(cells[0])
                    e.status = cells[1].replace("*", "").strip()
                return e if e.title else None
            for i, cell in enumerate(cells):
                if i >= len(cols):
                    break
                c = cols[i]
                v = cell.strip()
                if "§" in c:
                    m = re.match(r"\*?\*?(" + id_frag + r")", clean(v))
                    if m:
                        e.pattern_id = m.group(1)
                elif "id" in c and "title" in c:
                    t = clean(v)
                    m = re.match(r"(" + id_frag + r")\s*[-–—:]?\s*(.*)", t)
                    if m:
                        e.pattern_id = m.group(1)
                        e.title = m.group(2).strip()
                    else:
                        e.title = t
                elif c.strip() == "id":
                    m = re.match(r"(" + id_frag + r")", clean(v))
                    if m:
                        e.pattern_id = m.group(1)
                elif "status" in c:
                    e.status = clean(v)
                elif "keyword" in c or "search" in c or "queries" in c:
                    cv = v.replace("*", "")
                    km = re.search(r"Keywords?:?\s*(.+?)(?:Queries?:|$)", cv, re.I | re.S)
                    if km:
                        e.keywords = km.group(1).strip().rstrip(".")
                    qm = re.search(r"Queries?:?\s*(.+)", cv, re.I | re.S)
                    if qm:
                        e.search_queries = qm.group(1).strip()
                    if not km and not qm:
                        # DPF tables often write "keywords. Question?" in one
                        # cell: keep the keywords and use the question as a
                        # search query.
                        qm2 = re.search(r"[^.]*\?", cv)
                        if qm2:
                            e.keywords = cv[:qm2.start()].strip().rstrip(".").strip()
                            e.search_queries = qm2.group(0).strip()
                        else:
                            e.keywords = cv
                elif "depend" in c:
                    e.dependencies = v
                elif "title" in c:
                    e.title = clean(v)

        elif cfg.toc_id_location == "id_title":
            for i, cell in enumerate(cells):
                c = cols[i] if (cols and i < len(cols)) else ""
                v = cell.strip()
                if "id" in c and "title" in c:
                    lm = re.search(r"\[([^\]]+)\]\(([^)]*)\)", v)
                    if lm:
                        inner = clean(lm.group(1))
                        m = re.match(r"(" + id_frag + r")\s*[-–—:]?\s*(.*)", inner)
                        if m:
                            e.pattern_id = m.group(1)
                            e.title = m.group(2).strip()
                        else:
                            e.title = inner
                    else:
                        m = re.match(r"(" + id_frag + r")\s*[-–—:]?\s*(.*)", clean(v))
                        if m:
                            e.pattern_id = m.group(1)
                            e.title = m.group(2).strip()
                        else:
                            e.title = clean(v)
                elif "status" in c:
                    e.status = clean(v)
                elif "keyword" in c or "search" in c or "queries" in c:
                    cv = v.replace("*", "")
                    km = re.search(r"Keywords?:?\s*(.+?)(?:Queries?:|$)", cv, re.I | re.S)
                    if km:
                        e.keywords = km.group(1).strip().rstrip(".")
                    qm = re.search(r"Queries?:?\s*(.+)", cv, re.I | re.S)
                    if qm:
                        e.search_queries = qm.group(1).strip()
                    if not km and not qm:
                        # DPF tables often write "keywords. Question?" in one
                        # cell: keep the keywords and use the question as a
                        # search query.
                        qm2 = re.search(r"[^.]*\?", cv)
                        if qm2:
                            e.keywords = cv[:qm2.start()].strip().rstrip(".").strip()
                            e.search_queries = qm2.group(0).strip()
                        else:
                            e.keywords = cv
                elif "depend" in c:
                    e.dependencies = v
                elif c.strip() == "id":
                    m = re.match(r"(" + id_frag + r")", clean(v))
                    if m:
                        e.pattern_id = m.group(1)
                elif "title" in c and "id" not in c:
                    e.title = clean(v)
            if not e.pattern_id and e.title:
                m = re.match(r"(" + id_frag + r")", e.title)
                if m:
                    e.pattern_id = m.group(1)
                    e.title = e.title[m.end():].strip().lstrip("-–— :")

        elif cfg.toc_id_location == "locus":
            for i, cell in enumerate(cells):
                cv = cell.strip()
                m = re.search(r"`(" + id_frag + r")`", cv)
                if m:
                    e.pattern_id = m.group(1)
                    if i + 1 < len(cells):
                        e.title = clean(cells[i + 1])
                    break

        return e if (e.pattern_id or e.title) else None


# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------

class FileWriter:
    def __init__(self, config: SkillConfig, parsers: Dict[str, SpecParser],
                 maker_dir: Optional[Path] = None):
        self.config = config
        self.parsers = parsers
        self.output = config.output
        self.ref = self.output / "reference"
        self.scripts_dir = self.output / "scripts"
        self._hpath = self.output / f".{config.name}_hashes.json"
        self._mpath = self.output / f".{config.name}_manifest.json"
        self._maker_dir = maker_dir or _SCRIPT_DIR
        self._templates_dir = self._maker_dir / "templates"
        self._old: Dict[str, str] = {}
        self._new: Dict[str, str] = {}
        self._sections: Dict[str, section_map.UnitSections] = {}
        self._written = 0
        self._skipped = 0

    # --- path helpers ------------------------------------------------------
    def _unit_dir(self, fw_key: str) -> Path:
        return self.ref / fw_key

    def _intro_dir(self, fw_key: str = "") -> Path:
        """Narrative sections, shared by every framework in the skill.

        They used to sit in ``reference/`` for flat skills but inside each
        framework directory for Suites, so the layout depended on the skill
        type for no benefit.  One ``intro/`` directory now holds them all."""
        return self.ref / "intro"

    def _docs_dir(self) -> Path:
        """Whole companion documents (the Library guidance)."""
        return self.ref / "docs"

    # --- write -------------------------------------------------------------
    def write_all(self) -> Dict[str, int]:
        self._load_cache()
        manifest: List[Dict[str, Any]] = []

        # Whole documents (Library guidance, ...) come first: an agent should
        # read the working instruction before selecting patterns.
        for i, doc in enumerate(self.config.docs):
            if not doc.source.exists():
                print(f"  Warning: doc {doc.source} not found, skipping",
                      file=sys.stderr)
                continue
            key = f"{doc.slug}.md"
            self._put(self._docs_dir() / key, doc.source.read_text("utf-8"))
            manifest.append({
                "kind": "doc", "key": key, "order": i,
                "slug": doc.slug, "title": doc.title,
            })

        base_order = len(manifest)

        # Units and intro chunks, in document order per framework.
        all_chunks: List[Chunk] = []
        for fw in self.config.frameworks:
            parser = self.parsers[fw.key]
            all_chunks.extend(parser.chunks)
        all_chunks.sort(key=lambda c: (self._fw_index(c.framework_key), c.order))

        for i, chunk in enumerate(all_chunks):
            if chunk.kind == "intro":
                path = self._intro_dir(chunk.framework_key) / chunk.key
            else:
                path = self._unit_dir(chunk.framework_key) / chunk.key
            self._put(path, chunk.content)
            entry: Dict[str, Any] = {
                "kind": chunk.kind, "key": chunk.key, "order": base_order + i,
                "framework": chunk.framework_key,
            }
            if chunk.kind == "unit":
                entry.update(id=chunk.id, title=chunk.title, role=chunk.role)
            manifest.append(entry)

        write_text_lf(self._mpath, json.dumps(manifest, indent=2))

        toc_map = self._toc_map()
        self._sections = self._build_sections(all_chunks)
        self._gen_indexes(all_chunks, toc_map)
        self._gen_sections()
        self._gen_views(all_chunks)
        self._gen_derived(all_chunks, toc_map)
        self._gen_skill_md(all_chunks, toc_map)
        self._gen_readme(all_chunks)
        self._gen_roles()
        self._gen_marker()
        self._copy_scripts()
        if self.config.scripts:
            self._gen_init()

        self._prune()
        self._save_cache()
        return {"written": self._written, "skipped": self._skipped}

    def _prune(self) -> int:
        """Delete generated files that no longer belong to the skill.

        Unit IDs and roles change when a publication is revised; without this
        a renamed or merged unit would leave a stale file behind and the
        indexes would disagree with the directory listing.
        """
        keep = set(self._new)
        keep.add(self._hpath.name)
        keep.add(self._mpath.name)
        keep.add(f".{self.config.name}_build.json")
        keep.add("curated-routes.json")
        keep.add(skill_root.MARKER)
        removed = 0
        for path in sorted(self.output.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.output))
            if rel in keep:
                continue
            path.unlink()
            removed += 1
        for d in sorted(self.output.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        if removed:
            print(f"  Pruned {removed} stale file(s)", file=sys.stderr)
        return removed

    def _fw_index(self, key: str) -> int:
        for i, fw in enumerate(self.config.frameworks):
            if fw.key == key:
                return i
        return len(self.config.frameworks)

    def _toc_map(self) -> Dict[str, TOCEntry]:
        out: Dict[str, TOCEntry] = {}
        for parser in self.parsers.values():
            for e in parser.toc_entries:
                if e.pattern_id:
                    out.setdefault(e.pattern_id, e)
        return out

    # --- cache / write primitives -----------------------------------------
    def _put(self, path: Path, content: str) -> bool:
        h = sha256(content)
        rel = str(path.relative_to(self.output))
        self._new[rel] = h
        if self._old.get(rel) == h and path.is_file() and path.read_bytes() == content.encode("utf-8"):
            self._skipped += 1
            return False
        write_text_lf(path, content)
        self._written += 1
        return True

    def _put_bytes(self, path: Path, data: bytes) -> bool:
        h = sha256(data.decode("utf-8", errors="replace"))
        rel = str(path.relative_to(self.output))
        self._new[rel] = h
        if self._old.get(rel) == h and path.is_file() and path.read_bytes() == data:
            self._skipped += 1
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._written += 1
        return True

    def _load_cache(self):
        if self._hpath.exists():
            try:
                self._old = json.loads(self._hpath.read_text("utf-8"))
                if not isinstance(self._old, dict):
                    self._old = {}
            except Exception:
                self._old = {}

    def _save_cache(self):
        write_text_lf(self._hpath, json.dumps(self._new, indent=2))

    def _copy_scripts(self):
        """Copy the engine package into the skill, under ``scripts/skillmaker``.

        The copy has to be the *package*, not a pile of loose modules: every
        module imports ``skillmaker.*``, so the copied tree must present the
        same import names the repository does.  Copying it one directory down
        also makes the bootstrap in each module work unchanged -- the script's
        own directory is ``scripts/skillmaker/``, whose parent is ``scripts/``,
        which is where ``import skillmaker`` resolves from.

        A skill that ships the engine but not what the engine imports is not
        self-contained: the ``frameworks`` package and the ``templates`` the
        generator reads have to travel with it.
        """
        for name in self.config.scripts:
            src = self._maker_dir / name
            if not src.exists():
                print(f"  Warning: {src} not found, skipping", file=sys.stderr)
                continue
            if src.is_dir():
                for path in sorted(src.rglob("*")):
                    if path.is_dir() or "__pycache__" in path.parts:
                        continue
                    rel = path.relative_to(src)
                    self._put_bytes(self.scripts_dir / _PKG_NAME / name / rel,
                                    path.read_bytes())
                continue
            self._put_bytes(self.scripts_dir / _PKG_NAME / name,
                            src.read_bytes())

    # --- index helpers -----------------------------------------------------
    def _units(self, chunks: Iterable[Chunk], role: Optional[str] = None) -> List[Chunk]:
        out = [c for c in chunks if c.kind == "unit"]
        if role == "pattern":
            out = [c for c in out if c.role == "pattern"]
        elif role == "non-pattern":
            out = [c for c in out if c.role != "pattern"]
        return out

    def _domain_of(self, pid: str) -> str:
        for fw in self.config.frameworks:
            if re.match(r"^(" + fw.prefix_re + r")", pid):
                return fw.domain_of(pid)
        return pid[0]

    def _domain_descriptions(self) -> Dict[str, str]:
        merged: Dict[str, str] = {}
        for fw in self.config.frameworks:
            for k, v in fw.domains.items():
                merged.setdefault(k, v)
        return merged

    def _deps_map(self, toc: Dict[str, TOCEntry], pids: List[str]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for pid in pids:
            e = toc.get(pid)
            dep = ""
            if e and e.dependencies:
                m = re.search(r"Builds?\s+on:?\s*\*?\*?\s*(.+?)(?:\.\s*\*|\*|\.?\s*$)",
                              e.dependencies, re.I)
                if m:
                    dep = m.group(1).strip().rstrip(".")
                elif self.config.builds_on_fallback:
                    dep = self._extract_own_deps(e.dependencies, pid)
            out[pid] = dep
        return out

    def _extract_own_deps(self, deps: str, self_id: str) -> str:
        skill_re = build_skill_id_re(self.config)
        seen: List[str] = []
        for tok in re.findall(
                r"\b([A-Za-z][A-Za-z0-9]*(?:[.:][A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*)+)\b", deps):
            if not skill_re.match(tok) or tok == self_id:
                continue
            if unit_role(tok) != "pattern":
                continue
            if tok not in seen:
                seen.append(tok)
        return ", ".join(seen)

    # --- index generators --------------------------------------------------
    def _gen_indexes(self, chunks: List[Chunk], toc: Dict[str, TOCEntry]) -> None:
        units = self._units(chunks)
        patterns = [u for u in units if u.role == "pattern"]
        pids = [u.id for u in patterns]

        # Per-framework unit indexes.
        for fw in self.config.frameworks:
            own = [u for u in units if u.framework_key == fw.key]
            if not own:
                continue
            d = self._unit_dir(fw.key)
            d.mkdir(parents=True, exist_ok=True)
            self._put(d / "index.md", self._framework_index(fw, own, toc))

        self._gen_root_index(units)
        self._gen_agent_patterns(patterns, toc)
        self._gen_agent_references(units)
        if self.config.gen_keyword_index:
            self._gen_agent_keywords(toc, set(pids))
        if self.config.gen_query_index:
            self._gen_agent_queries(toc, set(pids))

    def _framework_index(self, fw: FrameworkSpec, units: List[Chunk],
                         toc: Dict[str, TOCEntry]) -> str:
        patterns = sorted([u for u in units if u.role == "pattern"],
                          key=lambda u: sort_key(u.id))
        refs = sorted([u for u in units if u.role != "pattern"],
                      key=lambda u: (u.role, sort_key(u.id)))
        lines = [f"# {fw.name} -- Unit Index", ""]
        if fw.docid:
            lines.append(f"**DocID:** `{fw.docid}`  ")
        lines.append(f"**Source:** `{fw.source.name}`  ")
        lines.append(f"**Patterns:** {len(patterns)}  ")
        lines.append(f"**Reference units:** {len(refs)}")
        lines.append("")
        lines += ["| ID | Title | Role | Status | File |",
                  "| :--- | :--- | :--- | :--- | :--- |"]
        for u in patterns + refs:
            e = toc.get(u.id)
            status = e.status if e and e.status else ""
            lines.append(f"| {u.id} | {u.title} | {u.role} | {status} | {u.key} |")
        return "\n".join(lines) + "\n"

    def _gen_root_index(self, units: List[Chunk]) -> None:
        lines = [f"# {self.config.title or self.config.name} -- Reference Index", ""]
        if self.config.frameworks:
            lines += ["| Framework | DocID | Patterns | Reference units | Directory |",
                      "| :--- | :--- | ---: | ---: | :--- |"]
            for fw in self.config.frameworks:
                own = [u for u in units if u.framework_key == fw.key]
                pats = sum(1 for u in own if u.role == "pattern")
                refs = sum(1 for u in own if u.role != "pattern")
                docid = f"`{fw.docid}`" if fw.docid else ""
                lines.append(f"| {fw.name} | {docid} | {pats} | {refs} | "
                             f"`reference/{fw.key}/` |")
        if self.config.docs:
            lines += ["", "## Reference documents", "",
                      "| Document | File | Purpose |",
                      "| :--- | :--- | :--- |"]
            for doc in self.config.docs:
                lines.append(f"| {doc.title} | `reference/docs/{doc.slug}.md` | "
                             f"{doc.description} |")
        self._put(self.ref / "index.md", "\n".join(lines) + "\n")

    def _budget_cells(self, unit_id: str) -> str:
        """Contract KB | all KB | section count, for the index row.

        A reader decides whether to open a 79 KB unit or read its 47 KB of
        working sections; that decision needs the numbers before the read, not
        after it.
        """
        info = self._sections.get(unit_id)
        if info is None or not info.sections:
            return "— | — | — |"
        contract_kb = max(1, round(info.tier_bytes("contract") / 1024))
        all_kb = max(1, round(info.bytes / 1024))
        return f"{contract_kb} KB | {all_kb} KB | {len(info.sections)} |"

    def _gen_agent_patterns(self, patterns: List[Chunk], toc: Dict[str, TOCEntry]) -> None:
        # An ADR set or a standards document has no pattern-role units, but its
        # units are still what a caller holds an ID for.  Indexing nothing would
        # make the first routing step in SKILL.md a dead end.
        fallback = not patterns
        if fallback:
            patterns = self._units(self._units_all(), role="non-pattern")
        if not patterns:
            return
        pids = [u.id for u in patterns]
        deps = self._deps_map(toc, pids)
        kernel = [p for p in sorted(deps, key=sort_key) if not deps[p]]
        multi = len(self.config.frameworks) > 1

        lines = [
            f"# {self.config.title or self.config.name} Pattern Index (Agent)", "",
            "## Range expansion", "",
            "En-dash `–` → enumerate: `C.17–C.19` → `C.17, C.18, C.19`.", "",
            ("## Units (no dependencies)" if fallback
             else "## Kernel patterns (no dependencies)"), "",
            (", ".join(f"`{k}`" for k in kernel[:40])
             + (f", ... ({len(kernel)} total)" if len(kernel) > 40 else ""))
            if kernel else "_(none -- every pattern names a dependency)_",
            "",
            "**Reading budget.** `Contract` is the working sections only "
            "(problem frame, solution, checklist, consequences, relations); "
            "`All` is the whole unit. Section anchors and line ranges are in "
            "`reference/sections.json`.", "",
            ("## All Units (this publication publishes no patterns)" if fallback
             else "## All Patterns"), "",
        ]
        header = "| ID | Title | Role |"
        sep = "| :--- | :--- | :--- |"
        if multi:
            header += " Framework |"
            sep += " :--- |"
        header += " Builds on | Contract | All | Sections | File |"
        sep += " :--- | ---: | ---: | ---: | :--- |"
        lines += [header, sep]
        for u in sorted(patterns, key=lambda u: sort_key(u.id)):
            row = f"| {u.id} | {u.title} | {u.role} |"
            if multi:
                row += f" {u.framework_key} |"
            row += f" {deps.get(u.id, '')} | {self._budget_cells(u.id)}" \
                   f" `reference/{u.framework_key}/{u.key}` |"
            lines.append(row)
        self._put(self.ref / "pattern-index.md", "\n".join(lines) + "\n")

    def _gen_agent_references(self, units: List[Chunk]) -> None:
        refs = sorted([u for u in units if u.role != "pattern"],
                      key=lambda u: (u.framework_key, u.role, sort_key(u.id)))
        lines = [
            f"# {self.config.title or self.config.name} Reference Units (Agent)", "",
            "Non-pattern units: Architectural References, worked applications and",
            "source notes. They explain how contributions connect; they are not",
            "normative pattern bodies.", "",
            "| Unit | Role | Title | File |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for u in refs:
            lines.append(f"| {u.id} | {u.role} | {u.title} | "
                         f"`reference/{u.framework_key}/{u.key}` |")
        if not refs:
            lines.append("| _(none)_ | | | |")
        self._put(self.ref / "reference-index.md", "\n".join(lines) + "\n")

    def _gen_agent_keywords(self, toc: Dict[str, TOCEntry], pids: Set[str]) -> None:
        kw: Dict[str, Set[str]] = {}
        for pid, e in toc.items():
            if pid not in pids or not e.keywords:
                continue
            for w in e.keywords.replace("*", "").split(","):
                w = w.strip().strip(".")
                if w and len(w) > 1:
                    kw.setdefault(w.lower(), set()).add(pid)
        lines = ["# Keyword Index", "", "| Keyword | Pattern IDs |",
                 "| :--- | :--- |"]
        for k in sorted(kw):
            lines.append(f"| {k} | {', '.join(sorted(kw[k], key=sort_key))} |")
        self._put(self.ref / "keyword-index.md", "\n".join(lines) + "\n")

    def _gen_agent_queries(self, toc: Dict[str, TOCEntry], pids: Set[str]) -> None:
        titles = {c.id: c.title for c in self._units_all()}
        lines = ["# Query Index", "", "| Query | Pattern ID |",
                 "| :--- | :--- |"]
        for pid in sorted(pids, key=sort_key):
            e = toc.get(pid)
            if e and e.search_queries:
                qs = re.findall(r'"([^"]+)"', e.search_queries)
                if not qs:
                    qs = [q.strip().strip('"\'')
                          for q in re.split(r"[?.]", e.search_queries)
                          if q.strip() and len(q.strip()) > 5]
                for q in qs:
                    q = q.strip().rstrip("?").strip()
                    if q:
                        lines.append(f"| {q}? | {pid} |")
            elif e and e.title:
                lines.append(f"| {e.title} | {pid} |")
            elif titles.get(pid):
                lines.append(f"| {titles[pid]} | {pid} |")
        self._put(self.ref / "query-index.md", "\n".join(lines) + "\n")

    def _build_sections(self, chunks: List[Chunk]) -> Dict[str, section_map.UnitSections]:
        """Section maps for every unit, keyed by unit ID.

        Built from the chunk content that was just written, so the offsets
        always describe the file a reader will open.
        """
        out: Dict[str, section_map.UnitSections] = {}
        for chunk in chunks:
            if chunk.kind != "unit" or not chunk.id:
                continue
            out[chunk.id] = section_map.analyse(chunk.id, chunk.content,
                                                chunk.key)
        return out

    def _gen_derived(self, chunks: List[Chunk],
                     toc: Dict[str, TOCEntry]) -> None:
        """Routes, entries, glossary and boot: the retrieval layer."""
        cfg = self.config
        units = self._units(chunks)
        if not units:
            self._put(self.output / "boot.md", derive.render_boot(
                cfg.name, cfg.title or cfg.name,
                cfg.kind_label or "Framework", cfg.genre, 0, 0,
                cfg.prefix_token or "1.1", self._rebuild_cmd(),
                bool(cfg.docs), bool(self._role_names())))
            return

        deps = self._deps_map(toc, [u.id for u in units])
        bodies = {c.id: c.content for c in chunks
                  if c.kind == "unit" and c.id}

        payload = derive.routes(units, deps, toc, self._sections)
        curated_path = self.output / "curated-routes.json"
        curated = None
        if curated_path.exists():
            try:
                curated = json.loads(curated_path.read_text("utf-8"))
                if (not isinstance(curated, dict) or not isinstance(curated.get("routes", []), list)
                        or any(not isinstance(route, dict) for route in curated.get("routes", []))):
                    raise ValueError("expected an object with a list of route objects")
            except (OSError, ValueError) as exc:
                # Silence here would drop hand-written routes without a word;
                # the file is the one place a user edits by hand, so a typo in
                # it has to be reported.
                print(f"  Warning: {curated_path.name} ignored ({exc})",
                      file=sys.stderr)
                curated = None
        payload = derive.merge_curated(payload, curated)
        self._put(self.ref / "routes.json",
                  json.dumps(payload, indent=1, ensure_ascii=False) + "\n")

        entry_data = derive.entries(units, toc, self._sections)
        self._put(self.ref / "entries.json",
                  json.dumps(entry_data, indent=1, ensure_ascii=False) + "\n")
        self._put(self.ref / "entries.md",
                  self._render_entries(entry_data["entries"]))

        rows = derive.glossary(units, bodies)
        if rows:
            self._put(self.ref / "glossary.md",
                      derive.render_glossary(rows, cfg.title or cfg.name))

        patterns = [u for u in units if u.role == "pattern"]
        self._put(self.output / "boot.md", derive.render_boot(
            cfg.name, cfg.title or cfg.name, cfg.kind_label or "Framework",
            cfg.genre, len(patterns), len(units),
            patterns[0].id if patterns else (cfg.prefix_token or "1.1"),
            self._rebuild_cmd(), bool(cfg.docs), bool(self._role_names())))

    def _render_entries(self, rows: List[Dict[str, object]]) -> str:
        #: A Markdown table is for reading, not for exhaustive lookup: past a
        #: few hundred rows nobody scans it, and the file grows to hundreds of
        #: kilobytes.  The cap is stated in the file rather than applied
        #: silently, and ``entries.json`` always holds every row.
        limit = 400
        lines = [f"# Entries -- {self.config.title or self.config.name}", "",
                 "Situation -> the unit to start with. Generated from each "
                 "unit's own stated queries.", ""]
        if not rows:
            lines.append("_(no stated queries in this publication)_")
            return "\n".join(lines) + "\n"
        lines += ["| If you need to... | Start with | Working size | Check |",
                  "| :--- | :--- | ---: | :--- |"]
        for row in rows[:limit]:
            size = row.get("contract_bytes") or 0
            check = f"`{row['acceptance']}`" if row.get("acceptance") else ""
            situation = str(row["situation"]).replace("|", "\\|")
            size_cell = (f"{max(1, round(size / 1024))} KB"
                         if row.get("has_sections") else "—")
            lines.append(f"| {situation} | `{row['start_with'][0]}` | "
                         f"{size_cell} | {check} |")
        if len(rows) > limit:
            lines += ["", f"Showing {limit} of {len(rows)} entries. "
                          f"`reference/entries.json` holds all of them, and the "
                          f"`entries` MCP tool pages through the same set."]
        lines.append("")
        return "\n".join(lines)

    def _role_names(self) -> List[str]:
        try:
            return list(genre_mod.by_value(self.config.genre).roles)
        except KeyError:
            return []

    def _gen_marker(self) -> None:
        """Write ``.skill.json``: the marker that makes the directory movable.

        Written through ``_put`` so the prune step knows it belongs to the
        skill.  A marker written directly would be deleted by the very next
        build.
        """
        cfg = self.config
        units = self._units_all()
        patterns = [u for u in units if u.role == "pattern"]
        payload = {
            "schema": 1,
            "name": cfg.name,
            "title": cfg.title or cfg.name,
            "kind": cfg.kind_label or "Framework",
            "genre": cfg.genre,
            "profile": cfg.profile_key or cfg.name,
            "source": cfg.source_path,
            "patterns": len(patterns),
            "units": len(units),
            "layout": "reference/{docs,intro,<docid>}",
        }
        self._put(self.output / skill_root.MARKER,
                  json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def _gen_roles(self) -> None:
        """Write ``roles/<name>.md`` for the skill's genre.

        A role is a division of work, not a separate agent: one agent may play
        all of them in sequence.  Skills whose genre needs no pipeline get no
        ``roles/`` directory at all, rather than an empty one.
        """
        try:
            spec = genre_mod.by_value(self.config.genre)
        except KeyError:
            print(f"  Warning: unknown genre {self.config.genre!r}, "
                  f"writing no roles", file=sys.stderr)
            return
        if not spec.roles:
            return

        values = self._template_values()
        lines = [f"# Roles -- {self.config.title or self.config.name}", "",
                 "A pipeline for this skill. The roles are a division of work, "
                 "not a requirement to run separate agents: one agent may play "
                 "all of them in sequence.", "",
                 "| Step | Role | Question |", "| ---: | :--- | :--- |"]
        for index, role in enumerate(spec.roles, 1):
            lines.append(f"| {index} | [{role}]({role}.md) | "
                         f"{ROLE_QUESTIONS.get(role, '')} |")
        lines.append("")
        self._put(self.output / "roles" / "README.md", "\n".join(lines))

        for role in spec.roles:
            template = self._templates_dir / "roles" / f"{role}.md"
            if not template.exists():
                print(f"  Warning: role template {role}.md not found",
                      file=sys.stderr)
                continue
            content = template.read_text("utf-8")
            for key, value in values.items():
                content = content.replace(key, value)
            self._put(self.output / "roles" / f"{role}.md", content)

    def _template_values(self) -> Dict[str, str]:
        """Every placeholder a template may use, filled from the config.

        One source of truth on purpose: SKILL.md, README.md and the role
        partials are rendered from separate templates, and a value that only
        one of the three rendering paths supplied used to reach a reader as a
        literal ``{{KIND}}``.
        """
        cfg = self.config
        units = self._units_all()
        patterns = [u for u in units if u.role == "pattern"]
        refs = [u for u in units if u.role != "pattern"]
        fw_count = len(cfg.frameworks)
        subject = " ".join(fw.description for fw in cfg.frameworks
                           if fw.role == "framework") or cfg.source_note or cfg.title or cfg.name
        if len(subject) > 700:
            # Suites carry many long descriptions. Names retain all constituent
            # subjects without breaking the 1024-character metadata budget.
            subject = "; ".join(fw.name for fw in cfg.frameworks if fw.role == "framework")
        if len(subject) > 700:
            subject = subject[:697].rsplit(" ", 1)[0] + "..."
        return {
            "{{SKILL_NAME}}": cfg.name,
            "{{TITLE}}": cfg.title or cfg.name,
            "{{SUBJECT_DESCRIPTION}}": subject,
            "{{KIND}}": cfg.kind_label or "Framework",
            "{{PROFILE}}": cfg.profile_key or cfg.name,
            "{{GENRE}}": cfg.genre,
            "{{PREFIX}}": cfg.prefix_token or cfg.name.upper(),
            "{{SOURCE_PATH}}": cfg.source_path or "",
            "{{SOURCE_NOTE}}": cfg.source_note or cfg.name,
            "{{PATTERN_COUNT}}": str(len(patterns)),
            "{{UNIT_COUNT}}": str(len(units)),
            "{{REFERENCE_COUNT}}": str(len(refs)),
            "{{FRAMEWORK_COUNT}}": str(fw_count),
            "{{FRAMEWORK_NOUN}}": ("framework document" if fw_count == 1
                                   else "framework documents"),
            "{{CONTRACT_NOTE}}": self._contract_note(),
            "{{REBUILD_CMD}}": self._rebuild_cmd(),
            "{{PREFIX_EXAMPLE}}": (patterns[0].id if patterns
                                   else (cfg.prefix_token or "1.1")),
            "{{ENTRY_PATTERN_PATH}}": (
                "reference/docs" if not cfg.frameworks
                else f"reference/{cfg.frameworks[0].key}"
                if cfg.layout == "flat" else "reference/<framework>"),
        }

    def _contract_note(self) -> str:
        """One measured sentence about the working sections' share of bytes.

        Measured per skill rather than written into the template: the share
        runs from about a third to about two thirds across this Library, so a
        fixed percentage would be wrong for most skills that print it.
        """
        total = sum(info.bytes for info in self._sections.values())
        if not total:
            return ("Reading only the working sections usually costs half the "
                    "bytes or less.")
        contract = sum(info.tier_bytes("contract")
                       for info in self._sections.values())
        share = max(1, round(100 * contract / total))
        return (f"On this skill the working sections are about {share}% of "
                f"the bytes.")

    def _genre_block(self) -> str:
        """The genre's middle section, for ``{{GENRE_BLOCK}}``.

        The partial is filled here, not by the caller: ``{{GENRE_BLOCK}}`` is
        inserted as a value, and a placeholder inside a value would only be
        replaced if it happened to come later in the caller's dict.
        """
        try:
            spec = genre_mod.by_value(self.config.genre)
        except KeyError:
            return ""
        partial = self._templates_dir / "genres" / spec.partial
        if not partial.exists():
            return ""
        text = partial.read_text("utf-8").rstrip() + "\n"
        for key, value in self._template_values().items():
            text = text.replace(key, value)
        return text

    def _gen_views(self, chunks: List[Chunk]) -> None:
        """Write the contract view of every unit, when the skill asks for it.

        The view is a selection of the unit's own lines, never a rewrite, so it
        cannot disagree with the source. Rebuilding a publication still reads
        the unit files: the views are derived and are not in the manifest.
        """
        if not self.config.emit_views:
            return
        written = 0
        for chunk in chunks:
            if chunk.kind != "unit" or not chunk.id:
                continue
            info = self._sections.get(chunk.id)
            if info is None or not info.of_tier("contract"):
                continue
            body = section_map.read_tier(chunk.id, chunk.content, "contract")
            target = (self._unit_dir(chunk.framework_key) / "contract"
                      / chunk.key)
            header = (f"<!-- contract view of {chunk.id} -- working sections "
                      f"only; the whole unit is {chunk.key} -->\n")
            self._put(target, header + body)
            written += 1
        if written:
            print(f"  Contract views: {written}", file=sys.stderr)

    def _gen_sections(self) -> None:
        """Write ``reference/sections.json``: anchors, tiers and byte offsets."""
        payload = {
            "unit": {uid: info.to_dict() for uid, info in sorted(self._sections.items())}
        }
        self._put(self.ref / "sections.json",
                  json.dumps(payload, indent=1, ensure_ascii=False) + "\n")

    def _units_all(self) -> List[Chunk]:
        out: List[Chunk] = []
        for p in self.parsers.values():
            out.extend(c for c in p.chunks if c.kind == "unit")
        return out

    # --- SKILL.md / README.md ---------------------------------------------
    def _gen_skill_md(self, chunks: List[Chunk], toc: Dict[str, TOCEntry]) -> None:
        cfg = self.config
        units = self._units(chunks)
        patterns = [u for u in units if u.role == "pattern"]
        refs = [u for u in units if u.role != "pattern"]
        desc_map = self._domain_descriptions()

        counts: Dict[str, int] = {}
        for u in patterns:
            key = self._domain_of(u.id)
            counts[key] = counts.get(key, 0) + 1
        domain_lines = []
        for key in sorted(counts):
            label = f"{cfg.domain_label_prefix}{key}"
            domain_lines.append(
                f"- **{label}** -- {desc_map.get(key, key)} ({counts[key]} patterns)")

        deps = self._deps_map(toc, [u.id for u in patterns])
        kernel = [p for p in sorted(deps, key=sort_key) if not deps[p]]
        kernel_str = ", ".join(f"`{k}`" for k in kernel[:20])
        if len(kernel) > 20:
            kernel_str += f", ... ({len(kernel)} total)"

        framework_lines = ["| Framework | DocID | Patterns | Reference units | Directory |",
                           "| :--- | :--- | ---: | ---: | :--- |"]
        for fw in cfg.frameworks:
            own = [u for u in units if u.framework_key == fw.key]
            framework_lines.append(
                f"| {fw.name} | `{fw.docid}` | "
                f"{sum(1 for u in own if u.role == 'pattern')} | "
                f"{sum(1 for u in own if u.role != 'pattern')} | "
                f"`reference/{fw.key}/` |")

        doc_lines = []
        for doc in cfg.docs:
            doc_lines.append(f"- [{doc.title}](reference/docs/{doc.slug}.md) -- {doc.description}")

        intro_lines = []
        for c in chunks:
            if c.kind == "intro":
                intro_lines.append(f"- `reference/intro/{c.key}`")
        if not intro_lines:
            intro_lines = ["_(none)_"]

        ref_lines = []
        by_role: Dict[str, int] = {}
        for u in refs:
            by_role[u.role] = by_role.get(u.role, 0) + 1
        for role in sorted(by_role):
            ref_lines.append(f"- **{role}** -- {by_role[role]} units")
        if refs:
            ref_lines.append("- Full list: `reference/reference-index.md`")
        if not ref_lines:
            ref_lines = ["_(none)_"]

        if not cfg.frameworks:
            # A whole-document skill: there are no unit files to point at.
            entry_dir = "reference/docs"
        elif cfg.layout == "flat":
            entry_dir = f"reference/{cfg.frameworks[0].key}"
        else:
            entry_dir = "reference/<framework>/"

        if cfg.frameworks:
            summary = f"{len(units)} addressable units"
            content_block = (
                f"Decomposed by the `{cfg.profile_key or cfg.name}` profile into "
                f"{len(units)} addressable units, one file each.")
        else:
            summary = "shipped in full"
            content_block = (
                f"Shipped as published: {len(cfg.docs)} document(s) under "
                f"`reference/docs/`. The document has no unit identifiers of its "
                f"own, so it is read whole rather than split.")

        # Shared values first, block values second: one dict of truth, so a
        # placeholder added to a template cannot be filled in one path and
        # left literal in another.
        replacements = dict(self._template_values())
        replacements.update({
            "{{KERNEL_PATTERNS}}": kernel_str or "_(none)_",
            "{{DOMAIN_BLOCK}}": "\n".join(domain_lines),
            "{{FRAMEWORK_BLOCK}}": "\n".join(framework_lines),
            "{{DOC_BLOCK}}": "\n".join(doc_lines),
            "{{DOC_SECTION}}": ("## Library documents\n\n"
                                + "\n".join(doc_lines) + "\n\n"
                                if doc_lines else ""),
            "{{REFERENCE_BLOCK}}": "\n".join(ref_lines),
            "{{INTRO_BLOCK}}": "\n".join(intro_lines),
            "{{SUMMARY}}": summary,
            "{{CONTENT_BLOCK}}": content_block,
            "{{GENRE_BLOCK}}": self._genre_block(),
            "{{ENTRY_PATTERN_PATH}}": entry_dir,
        })
        template = self._load_template(cfg.skill_template, "SKILL.md.template")
        content = template
        for key, val in replacements.items():
            content = content.replace(key, val)
        self._put(self.output / "SKILL.md", content)

    def _rebuild_cmd(self) -> str:
        if self.config.name == "fpf":
            return "python skill-maker/src/skillmaker/split_fpf_spec.py split"
        if self.config.kind_label == "DPF Suite":
            return "python skill-maker/src/skillmaker/split_dpf_spec.py split --all"
        return f"python skill-maker/src/skillmaker/split_dpf_spec.py split --framework {self.config.prefix_token}"

    def _structure_block(self) -> str:
        """The README's directory tree, generated from what this skill holds.

        A tree written into the template drifts as soon as a skill gains or
        loses a directory: a standalone DPF has no ``docs/`` and no
        ``scripts/``, and a reader sent to either finds nothing.  Generating
        it from the config keeps the picture and the directory identical.
        """
        cfg = self.config
        column = 30  # where the trailing comments start

        def row(prefix: str, name: str, note: str = "") -> str:
            text = prefix + name
            return f"{text:<{column}} # {note}" if note else text

        has_scripts = bool(cfg.scripts)
        has_roles = bool(self._role_names())
        has_intro = any(c.kind == "intro"
                        for p in self.parsers.values() for c in p.chunks)

        ref_children: List[tuple] = [
            ("index.md", "What is in this skill"),
            ("pattern-index.md", "ID → Title → Builds on → Contract/All → File"),
            ("query-index.md", "Question → unit ID"),
            ("keyword-index.md", "Keyword → unit IDs"),
            ("reference-index.md", "Non-pattern units (Reference, Applications, …)"),
            ("sections.json", "Section anchors, tiers, line ranges"),
            ("entries.md", "Situation → starting unit"),
            ("glossary.md", "Term → one-line meaning"),
        ]
        if has_intro:
            ref_children.append(("intro/", "Narrative sections of the publication"))
        if cfg.docs:
            ref_children.append(("docs/", "Whole documents, read as published"))

        lines = [f"skills/{cfg.name}/"]
        for name, note in (("SKILL.md", "Agent navigation hub (start here)"),
                           ("README.md", "This file"),
                           ("boot.md", "What a session reads first")):
            lines.append(row("├── ", name, note))

        # Anything that follows ``reference/`` at the top level.  Its presence
        # is what decides whether ``reference/`` is drawn as the last entry and
        # whether its children carry a vertical rule.
        after_ref: List[tuple] = []
        if has_roles:
            after_ref.append(("roles/", "Pipeline roles (one agent may play all)"))
        if has_scripts:
            after_ref.append(("scripts/", "Runtime tools (search, read, update)"))

        lines.append(row("└── " if not after_ref else "├── ", "reference/"))

        outer = "    " if not after_ref else "│   "
        children = list(ref_children) + [(f"{f.key}/", "") for f in cfg.frameworks]
        for index, (name, note) in enumerate(children):
            last = index == len(children) - 1
            if index == len(ref_children) and cfg.frameworks:
                note = "One file per unit, named by its ID"
            lines.append(row(outer + ("└── " if last else "├── "), name, note))
            if index == len(ref_children) and cfg.frameworks:
                inner = outer + ("    " if last else "│   ")
                detail = [("index.md", "Unit table"),
                          ("<ID>.md", "The whole unit"),
                          ("contract/<ID>.md", "Working sections only (--views)")]
                for sub, (dname, dnote) in enumerate(detail):
                    branch = "└── " if sub == len(detail) - 1 else "├── "
                    lines.append(row(inner + branch, dname, dnote))

        for index, (name, note) in enumerate(after_ref):
            last = index == len(after_ref) - 1
            lines.append(row("└── " if last else "├── ", name, note))

        return "\n".join(lines)

    def _gen_readme(self, chunks: List[Chunk]) -> None:
        cfg = self.config
        units = self._units(chunks)
        patterns = [u for u in units if u.role == "pattern"]
        doms = {self._domain_of(u.id) for u in patterns}
        replacements = dict(self._template_values())
        replacements.update({
            "{{DOMAIN_COUNT}}": str(len(doms)),
            "{{DOMAIN_NOUN}}": "domain" if len(doms) == 1 else "domains",
            "{{STRUCTURE_BLOCK}}": self._structure_block(),
        })
        template = self._load_template(cfg.readme_template, "README.md.template")
        content = template
        for key, val in replacements.items():
            content = content.replace(key, val)
        self._put(self.output / "README.md", content)

    def _load_template(self, path: Optional[Path], name: str) -> str:
        if path and path.exists():
            return path.read_text("utf-8")
        p = self._templates_dir / name
        if p.exists():
            return p.read_text("utf-8")
        print(f"  Warning: template {name} not found, using fallback", file=sys.stderr)
        return f"# {name}\n\nTemplate not found.\n"

    def _gen_init(self) -> None:
        """Re-export the runtime tools from ``scripts/`` itself.

        The engine now lives one level down in ``scripts/skillmaker/``, so
        this stays a convenience façade rather than the package's own
        ``__init__``: ``from scripts import fpf_read_pattern`` keeps
        working for anyone who imported it that way.
        """
        self._put(self.scripts_dir / "__init__.py",
                  "from .skillmaker.fpf_lookup import (fpf_search_index, "
                  "fpf_read_pattern, fpf_list_domain, fpf_read_intro, "
                  "fpf_read_doc)\n"
                  "__all__ = ['fpf_search_index', 'fpf_read_pattern', "
                  "'fpf_list_domain', 'fpf_read_intro', 'fpf_read_doc']\n")


# ---------------------------------------------------------------------------
# Rebuild / analyze
# ---------------------------------------------------------------------------

def rebuild_spec(config: SkillConfig, output: Path,
                 include_docs: bool = False) -> None:
    """Reassemble the framework text from a built skill directory."""
    mpath = config.output / f".{config.name}_manifest.json"
    if not mpath.exists():
        print(f"Error: manifest not found at {mpath}", file=sys.stderr)
        sys.exit(1)
    manifest = json.loads(mpath.read_text("utf-8"))
    if (not isinstance(manifest, list)
            or any(not isinstance(entry, dict) or type(entry.get("order")) is not int
                   for entry in manifest)):
        raise ValueError(f"invalid reconstruction manifest: {mpath}")
    manifest.sort(key=lambda x: x["order"])
    parts: List[str] = []
    for entry in manifest:
        kind = entry["kind"]
        path = manifest_entry_path(config.output, entry)
        if kind == "doc" and not include_docs:
            continue
        if not path.is_file():
            raise ValueError(f"cannot reconstruct publication: missing {path}")
        if path.resolve() == output.resolve():
            raise ValueError("rebuild output must not overwrite a manifest input")
        parts.append(path.read_text("utf-8"))
    rebuilt = "\n".join(parts)
    if rebuilt and not rebuilt.endswith("\n"):
        rebuilt += "\n"
    write_text_lf(output, rebuilt)
    print(f"Rebuilt: {output} ({len(rebuilt.encode('utf-8'))} bytes)")


def print_stats(configs) -> int:
    """Report built-skill counts from the manifests (no re-parsing)."""
    total_p = total_r = total_d = 0
    print(f"{'skill':34s} {'patterns':>9s} {'ref units':>10s} {'docs':>5s}")
    print("-" * 62)
    for name, cfg in configs:
        mpath = cfg.output / f".{cfg.name}_manifest.json"
        if not mpath.exists():
            print(f"{cfg.output.name:34s} {'(not built)':>9s}")
            continue
        entries = json.loads(mpath.read_text("utf-8"))
        pats = sum(1 for e in entries if e.get("role") == "pattern")
        refs = sum(1 for e in entries
                   if e.get("kind") == "unit" and e.get("role") != "pattern")
        docs = sum(1 for e in entries if e.get("kind") == "doc")
        total_p += pats
        total_r += refs
        total_d += docs
        print(f"{cfg.output.name:34s} {pats:9d} {refs:10d} {docs:5d}")
    print("-" * 62)
    print(f"{'total':34s} {total_p:9d} {total_r:10d} {total_d:5d}")
    return 0


def analyze(config: SkillConfig) -> None:
    print(f"=== Analysis ({config.name}) ===")
    total_intro = total_pat = total_ref = 0
    for fw in config.frameworks:
        p = SpecParser(config, fw)
        p.parse()
        intros = [c for c in p.chunks if c.kind == "intro"]
        units = [c for c in p.chunks if c.kind == "unit"]
        pats = [c for c in units if c.role == "pattern"]
        refs = [c for c in units if c.role != "pattern"]
        total_intro += len(intros)
        total_pat += len(pats)
        total_ref += len(refs)
        roles = sorted({c.role for c in refs})
        extra = f" ({', '.join(roles)})" if roles else ""
        print(f"  {fw.key}: {len(pats)} patterns, {len(refs)} reference units{extra}, "
              f"{len(intros)} intro, {len(p.toc_entries)} TOC entries")
    print(f"Total: {total_pat} patterns, {total_ref} reference units, "
          f"{total_intro} intro sections, {len(config.docs)} documents")


#: One-line question per role, used in ``roles/README.md``.
ROLE_QUESTIONS: Dict[str, str] = {
    "classifier": "Does this material apply, and how deep?",
    "retriever": "What is the minimum that answers it?",
    "reasoner": "What is the answer, in the asker's language?",
    "reviewer": "Is it grounded, specific and free of jargon?",
    "installer": "How does the client reach the service, and what changed?",
    "validator": "Which layer of the connection actually works?",
    "sync": "Is the derived artefact still in step with its source?",
}

#: Files whose contents decide what a build produces.  A change to any of them
#: invalidates every cached build, because the output would differ.
#:
#: This is every module the engine imports *and* every file it copies into the
#: skill: a bundled tool is an output like any other, so editing ``fpf_lookup``
#: has to refresh the copy under ``scripts/``.  ``test_derived`` asserts that
#: this list, plus ``_ENGINE_DIRS``, covers all of ``FPF_CONFIG.scripts``.
_ENGINE_FILES = (
    "__init__.py",
    "split_spec.py", "skill_config.py", "_fpf_common.py",
    "sections.py", "derive.py", "skill_root.py",
    "fpf_lookup.py", "split_fpf_spec.py", "fpf_update.py",
    "audit_fpf_patterns.py",
)

#: Directories whose every file is part of the engine.  Listed whole rather
#: than by hand: a new profile or a reworded role template changes the output
#: just as surely as a code change, and a hand-kept list goes stale silently.
_ENGINE_DIRS = ("frameworks", "templates")


def _engine_digest(config: SkillConfig) -> str:
    """Fingerprint of the engine and the config that built a skill.

    Without this, skipping an unchanged build would keep stale output after a
    template or index change -- the worst kind of cache.  It therefore covers
    every module the engine imports and every template it reads, not just the
    two entry-point templates.
    """
    h = hashlib.sha256()
    for rel in _ENGINE_FILES:
        path = _SCRIPT_DIR / rel
        if path.exists():
            h.update(rel.encode())
            h.update(path.read_bytes())
    for directory in _ENGINE_DIRS:
        base = _SCRIPT_DIR / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue
            if path.suffix == ".pyc":
                continue
            h.update(path.relative_to(_SCRIPT_DIR).as_posix().encode())
            h.update(path.read_bytes())
    for template in (config.skill_template, config.readme_template):
        if template and template.exists():
            h.update(template.name.encode())
            h.update(template.read_bytes())
    # Resolved paths: ``--source FPF-Spec.md`` and the config's absolute path
    # name the same file, and must produce the same digest, or the incremental
    # check silently never fires.
    from dataclasses import asdict

    def normalise(value):
        if isinstance(value, Path):
            return value.resolve().as_posix()
        if isinstance(value, dict):
            return {key: normalise(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [normalise(item) for item in value]
        return value

    settings = asdict(config)
    # The output location does not change generated content. Everything else,
    # including genre, grammar, views and framework order, does.
    settings.pop("output")
    h.update(json.dumps(normalise(settings), sort_keys=True,
                        ensure_ascii=False).encode("utf-8"))
    curated = config.output / "curated-routes.json"
    if curated.is_file():
        h.update(b"curated-routes\0" + curated.read_bytes())
    return h.hexdigest()[:32]


def _source_digest(config: SkillConfig) -> str:
    h = hashlib.sha256()
    for path in ([fw.source for fw in config.frameworks]
                 + [doc.source for doc in config.docs]):
        h.update(path.resolve().as_posix().encode("utf-8") + b"\0")
        if path.is_file():
            h.update(b"file\0" + hashlib.sha256(path.read_bytes()).digest())
        else:
            h.update(b"missing\0")
    return h.hexdigest()[:32]


def _stamp_path(config: SkillConfig) -> Path:
    return config.output / f".{config.name}_build.json"


def _is_up_to_date(config: SkillConfig) -> bool:
    """True when the last build used the same sources and the same engine.

    Parsing FPF Core means reading 17 MB; parsing every DPF means another 10.
    When nothing has changed that work is pure waste, so a rebuild that would
    reproduce the previous output is skipped -- but only after checking that
    every file the manifest names still exists.
    """
    stamp_path = _stamp_path(config)
    manifest_path = config.output / f".{config.name}_manifest.json"
    hash_path = config.output / f".{config.name}_hashes.json"
    # The hash cache is part of a complete build: without it the next real
    # build would rewrite every file, so a skill missing it is not "up to date".
    if not (stamp_path.exists() and manifest_path.exists() and hash_path.exists()):
        return False
    try:
        stamp = json.loads(stamp_path.read_text("utf-8"))
        if not isinstance(stamp, dict):
            return False
    except (OSError, ValueError):
        return False
    if stamp.get("engine") != _engine_digest(config):
        return False
    if stamp.get("sources") != _source_digest(config):
        return False
    try:
        if stamp.get("registry") != hashlib.sha256(hash_path.read_bytes()).hexdigest():
            return False
        outputs = json.loads(hash_path.read_text("utf-8"))
        if not isinstance(outputs, dict) or not outputs:
            return False
        for rel, expected in outputs.items():
            path = config.output / rel
            if (not path.resolve().is_relative_to(config.output.resolve())
                    or not path.is_file() or not isinstance(expected, str)
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
                return False
    except (OSError, ValueError, TypeError, RuntimeError):
        return False
    try:
        entries = json.loads(manifest_path.read_text("utf-8"))
        if stamp.get("manifest") != sha256(manifest_path.read_text("utf-8")):
            return False
        if not isinstance(entries, list):
            return False
        for entry in entries:
            kind = entry.get("kind")
            if kind == "doc":
                path = config.output / "reference" / "docs" / entry["key"]
            elif kind == "intro":
                path = config.output / "reference" / "intro" / entry["key"]
            elif kind == "unit":
                path = config.output / "reference" / entry["framework"] / entry["key"]
            else:
                return False
            if not path.is_file() or not path.resolve().is_relative_to(config.output.resolve()):
                return False
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False

    return True


def build_skill(config: SkillConfig, output: Optional[Path] = None,
                source_override: Optional[Path] = None,
                intro_split: Optional[str] = None,
                force: bool = False,
                emit_views: Optional[bool] = None) -> int:
    """Parse every framework of *config* and write the skill. 0 = success."""
    if output is not None:
        config.output = output
    if intro_split:
        config.intro_split = intro_split
    if source_override is not None:
        for fw in config.frameworks:
            fw.source = source_override
    if emit_views is not None:
        config.emit_views = emit_views

    target = config.output.resolve()
    protected = [fw.source for fw in config.frameworks] + [doc.source for doc in config.docs]
    protected += [path for path in (config.skill_template, config.readme_template) if path]
    if (any(path.resolve().is_relative_to(target) for path in protected)
            or _SCRIPT_DIR.resolve().is_relative_to(target)):
        print("Error: output must not contain source publications, templates or the engine", file=sys.stderr)
        return 1
    if config.output.is_dir() and any(path.is_symlink() for path in config.output.rglob("*")):
        print("Error: output contains symbolic links; use a dedicated generated directory", file=sys.stderr)
        return 1

    if not force and _is_up_to_date(config):
        # Report the same counts a full build would, from the manifest, so a
        # skipped build is still informative rather than silent.
        entries = json.loads(
            (config.output / f".{config.name}_manifest.json").read_text("utf-8"))
        pats = sum(1 for e in entries if e.get("role") == "pattern")
        refs = sum(1 for e in entries
                   if e.get("kind") == "unit" and e.get("role") != "pattern")
        intros = sum(1 for e in entries if e.get("kind") == "intro")
        print(f"{config.output.name}: up to date (sources and engine unchanged)")
        print(f"  {pats} patterns, {refs} reference units, "
              f"{intros} intro sections (from manifest)")
        print("  Written: 0, Skipped: all")
        return 0

    parsers: Dict[str, SpecParser] = {}
    for fw in config.frameworks:
        if not fw.source.exists():
            print(f"Error: {fw.source} not found", file=sys.stderr)
            return 1
        print(f"Parsing {fw.source}...")
        p = SpecParser(config, fw)
        p.parse()
        parsers[fw.key] = p
        pats = [c for c in p.chunks if c.kind == "unit" and c.role == "pattern"]
        refs = [c for c in p.chunks if c.kind == "unit" and c.role != "pattern"]
        intros = [c for c in p.chunks if c.kind == "intro"]
        print(f"  {len(pats)} patterns, {len(refs)} reference units, "
              f"{len(intros)} intro sections, {len(p.toc_entries)} TOC entries")
        if p._closed:
            print(f"  {len(p._closed)} end marker(s) kept with their block: "
                  f"{', '.join(p._closed[:4])}")
        if p._dropped:
            print(f"  {len(p._dropped)} empty section(s) dropped: "
                  f"{', '.join(p._dropped[:4])}")
    print(f"Writing {config.output}/...")
    w = FileWriter(config, parsers)
    stats = w.write_all()
    write_text_lf(_stamp_path(config), json.dumps({
        "engine": _engine_digest(config),
        "sources": _source_digest(config),
        "manifest": sha256((config.output / f".{config.name}_manifest.json").read_text("utf-8")),
        "registry": hashlib.sha256((config.output / f".{config.name}_hashes.json").read_bytes()).hexdigest(),
    }, indent=2))
    print(f"  Written: {stats['written']}, Skipped: {stats['skipped']}")
    return 0
