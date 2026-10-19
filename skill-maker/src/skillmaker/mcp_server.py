#!/usr/bin/env python3
"""
mcp_server.py -- serve a built ``skills/`` tree over the Model Context Protocol.

This serves a skill tree built by ``skill-maker``: the publications of a
Library, plus any framework the same profiles can decompose -- a private
framework, an ADR set, a standards document.  Four additional tools expose the
skill-maker itself (``plan_decomposition``, ``probe_document``, ...).

The seven reading tools follow one small contract, stated in
:data:`READING_TOOLS`: an ID in, Markdown out, with paging and a snapshot guard
so a continuation cannot silently cross editions.  Any client that speaks MCP
can use them; nothing here depends on a particular host or vendor.

Transport: stdio, newline-delimited JSON-RPC 2.0 (the MCP spec requires
messages to be newline-delimited and to contain no embedded newlines).  No
third-party packages: the whole toolchain is stdlib-only and stays that way.

Usage::

    python skill-maker/src/skillmaker/mcp_server.py                     # serve ./skills
    python skill-maker/src/skillmaker/mcp_server.py --skills-root DIR   # serve another tree
    python skill-maker/src/skillmaker/mcp_server.py --selftest          # no client needed

Register it with any MCP client as a stdio server whose command is
``python /path/to/skill-maker/src/skillmaker/mcp_server.py``; the client's own documentation
describes how to declare one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
_MAKER_DIR = _PKG_PARENT.parent           # skill-maker/
_REPO_ROOT = _MAKER_DIR.parent            # repository root
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

from skillmaker import sections as section_map  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "fpf-local-skills"
SERVER_VERSION = "1.0.0"

#: Continuation page size when a caller does not ask for one.
DEFAULT_PAGE = 20


# ---------------------------------------------------------------------------
# Library model
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """One built skill directory."""

    name: str
    path: Path
    kind: str = ""
    title: str = ""
    docids: Tuple[str, ...] = ()
    units: List[Dict[str, Any]] = field(default_factory=list)
    """Manifest unit entries (``id``, ``title``, ``role``, ``framework``, ``key``)."""
    intros: List[str] = field(default_factory=list)
    docs: List[str] = field(default_factory=list)

    @property
    def reference(self) -> Path:
        return self.path / "reference"

    def unit_path(self, entry: Dict[str, Any]) -> Path:
        return self.reference / entry["framework"] / entry["key"]

    def hub_path(self) -> Path:
        return self.path / "SKILL.md"


class Library:
    """An index over every skill under one ``skills/`` root."""

    def __init__(self, skills_root: Path):
        self.root = skills_root
        self.skills: Dict[str, Skill] = {}
        self.by_id: Dict[str, Tuple[Skill, Dict[str, Any]]] = {}
        self.snapshot: str = ""
        self._body_cache: Dict[Path, str] = {}
        self.load()

    # --- loading ----------------------------------------------------------
    def load(self) -> None:
        if not self.root.is_dir():
            raise SystemExit(f"skills root not found: {self.root}")
        index = self.root / "index.json"
        self.snapshot = f"local-{_digest(index)}" if index.exists() else "local-unknown"

        for skill_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            manifest = skill_dir / f".{skill_dir.name}_manifest.json"
            if not manifest.exists():
                continue
            entries = json.loads(manifest.read_text("utf-8"))
            skill = Skill(name=skill_dir.name, path=skill_dir)
            for entry in entries:
                kind = entry.get("kind")
                if kind == "unit":
                    skill.units.append(entry)
                    self.by_id.setdefault(entry["id"], (skill, entry))
                elif kind == "intro":
                    skill.intros.append(entry["key"])
                elif kind == "doc":
                    skill.docs.append(entry["key"])
            self.skills[skill.name] = skill

        self._load_metadata()

    def _load_metadata(self) -> None:
        index = self.root / "index.json"
        if not index.exists():
            return
        payload = json.loads(index.read_text("utf-8"))
        for row in payload.get("skills", []):
            skill = self.skills.get(row["name"])
            if skill is None:
                continue
            skill.kind = row.get("kind", "")
            skill.title = row.get("title", "")
            skill.docids = tuple(row.get("docids", ()))

    # --- lookup -----------------------------------------------------------
    def resolve_publication(self, value: str) -> Optional[Skill]:
        """Accept a skill name (``decision-design``) or a DocID (``PSDA``)."""
        if not value:
            return None
        key = value.strip()
        if key in self.skills:
            return self.skills[key]
        lowered = key.lower()
        for skill in self.skills.values():
            if skill.name.lower() == lowered:
                return skill
            if any(d.lower() == lowered for d in skill.docids):
                return skill
        return None

    #: Catalogue kind values mapped onto the labels used by skills/index.json.
    KIND_ALIASES = {
        "fpf": "fpf core", "dpf": "framework", "reference": "reference",
        "guide": "guide", "suite": "suite", "framework": "framework",
        "fpf core": "fpf core",
    }

    def filter_skills(self, kind: str = "", suite: str = "") -> List[Skill]:
        """Best-effort filtering over the local model.

        A local build groups the Library differently from the website: four
        Suite skills bundle their constituent frameworks, and guides ship as
        documents inside ``fpf``.  The filters therefore accept both
        vocabularies rather than pretending the models are identical.
        """
        out = list(self.skills.values())
        if kind:
            wanted = self.KIND_ALIASES.get(kind.strip().lower(), kind.strip().lower())
            out = [s for s in out if (s.kind or "").lower() == wanted]
        if suite:
            needle = suite.strip().lower()
            if not needle.endswith("-suite"):
                needle += "-suite"
            out = [s for s in out if s.name.lower() == needle]
        return out

    def publication_of(self, skill: Skill) -> Dict[str, Any]:
        return {
            "id": skill.name,
            "title": skill.title or skill.name,
            "kind": skill.kind,
            "docids": list(skill.docids),
            "patterns": sum(1 for u in skill.units if u.get("role") == "pattern"),
            "units": len(skill.units),
            "path": f"skills/{skill.name}",
        }

    def body(self, path: Path) -> str:
        cached = self._body_cache.get(path)
        if cached is None:
            cached = path.read_text("utf-8", errors="replace")
            self._body_cache[path] = cached
        return cached

    # --- queries ----------------------------------------------------------
    def search(self, q: str, publication: str = "", limit: int = DEFAULT_PAGE,
               offset: int = 0, kind: str = "", suite: str = "") -> Dict[str, Any]:
        """Rank units by how well their ID and title match the query."""
        terms = [t for t in re.split(r"[^\w.-]+", q.lower()) if t]
        if not terms:
            return {"results": [], "total": 0, "next_offset": None}

        pool: Iterable[Skill]
        if publication:
            skill = self.resolve_publication(publication)
            if skill is None:
                raise ValueError(f"unknown publication {publication!r}")
            pool = [skill]
        else:
            pool = self.filter_skills(str(kind or ""), str(suite or ""))

        hits: List[Tuple[int, Skill, Dict[str, Any]]] = []
        for skill in pool:
            for entry in skill.units:
                title = (entry.get("title") or "").lower()
                uid = (entry.get("id") or "").lower()
                score = 0
                for term in terms:
                    if term in uid:
                        score += 10
                    if term in title:
                        score += 6
                    elif any(w.startswith(term) for w in title.split()):
                        score += 3
                if score:
                    hits.append((score, skill, entry))

        hits.sort(key=lambda h: (-h[0], h[2].get("id", "")))
        page = hits[offset:offset + limit]
        return {
            "results": [
                {
                    "publication": skill.name,
                    "pattern_id": entry.get("id", ""),
                    "section": entry.get("id", ""),
                    "title": entry.get("title", ""),
                    "role": entry.get("role", ""),
                    "file": f"reference/{entry['framework']}/{entry['key']}",
                    "score": score,
                }
                for score, skill, entry in page
            ],
            "total": len(hits),
            "next_offset": offset + limit if offset + limit < len(hits) else None,
        }

    def read_pattern(self, pattern_id: str, tier: str = "all",
                     section: str = "") -> Dict[str, Any]:
        """Read a unit whole, one tier of it, or one named section of it.

        ``tier="contract"`` returns the working sections only -- measured on
        the built tree, about 54% of the bytes overall, from 36% for the
        sparsest publication to 60% for FPF Core.  ``section="solution"``
        returns just that section with its subsections.
        """
        found = self.by_id.get(pattern_id.strip())
        if found is None:
            near = self._near(pattern_id)
            raise ValueError(
                f"unknown unit {pattern_id!r}" + (f"; did you mean {near}?" if near else "")
            )
        skill, entry = found
        path = skill.unit_path(entry)
        if not path.exists():
            raise ValueError(f"file missing for {pattern_id}: {path}")
        text = self.body(path)
        info = section_map.analyse(entry["id"], text, entry["key"])

        payload: Dict[str, Any] = {
            "publication": skill.name,
            "pattern_id": entry.get("id"),
            "title": entry.get("title"),
            "role": entry.get("role"),
            "file": f"skills/{skill.name}/reference/{entry['framework']}/{entry['key']}",
            "budget": info.budget(),
            "sections": [
                {"anchor": s.anchor, "title": s.title, "tier": s.tier,
                 "line": s.line, "bytes": s.bytes}
                for s in info.sections
            ],
        }

        if section:
            body = section_map.read_section(entry["id"], text, section)
            if body is None:
                known = ", ".join(s.anchor for s in info.sections[:8]) or "(none)"
                raise ValueError(
                    f"unknown section {section!r} in {entry['id']}; try one of: {known}")
            payload["section"] = section
            payload["markdown"] = body
            payload["returned_bytes"] = len(body.encode("utf-8"))
            return payload

        if tier not in ("all", "contract", "source"):
            raise ValueError(
                f"unknown tier {tier!r}; use 'all', 'contract' or 'source'")
        body = section_map.read_tier(entry["id"], text, tier)
        payload["tier"] = tier
        payload["markdown"] = body
        payload["returned_bytes"] = len(body.encode("utf-8"))
        return payload

    def _near(self, pattern_id: str) -> str:
        stem = pattern_id.split(".")[0].lower()
        for uid in self.by_id:
            if uid.lower().startswith(stem + "."):
                return uid
        return ""

    def table_of_contents(self, publication: str, patterns_only: bool = False,
                          limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        skill = self.resolve_publication(publication)
        if skill is None:
            raise ValueError(f"unknown publication {publication!r}")
        sections: List[Dict[str, Any]] = []
        if not patterns_only:
            for slug in skill.intros:
                sections.append({"key": f"intro:{slug}", "title": slug, "kind": "intro"})
            for slug in skill.docs:
                sections.append({"key": f"doc:{slug}", "title": slug, "kind": "doc"})
        for entry in skill.units:
            if patterns_only and entry.get("role") != "pattern":
                continue
            sections.append({
                "key": entry.get("id", ""),
                "title": entry.get("title", ""),
                "kind": entry.get("role", ""),
            })
        page = sections[offset:offset + limit]
        return {
            "publication": skill.name,
            "sections": page,
            "total": len(sections),
            "next_offset": offset + limit if offset + limit < len(sections) else None,
        }

    def read_range(self, publication: str, start: str, through: str) -> Dict[str, Any]:
        """Read an inclusive range of units, in manifest order.

        The last section and its subsections are included, so ``PSDA.1``..
        ``PSDA.3`` returns three whole units.
        """
        skill = self.resolve_publication(publication)
        if skill is None:
            raise ValueError(f"unknown publication {publication!r}")
        order = [u.get("id") for u in skill.units]
        if start not in order:
            raise ValueError(f"unknown section {start!r} in {skill.name!r}")
        if through not in order:
            raise ValueError(f"unknown section {through!r} in {skill.name!r}")
        first, last = order.index(start), order.index(through)
        if last < first:
            raise ValueError(f"through {through!r} precedes section {start!r}")
        chunks = [self.body(skill.unit_path(skill.units[i]))
                  for i in range(first, last + 1)]
        return {
            "publication": skill.name,
            "section": start,
            "through": through,
            "units": order[first:last + 1],
            "markdown": "\n".join(chunks),
        }

    def read_section(self, publication: str, section: str = "") -> Dict[str, Any]:
        skill = self.resolve_publication(publication)
        if skill is None:
            raise ValueError(f"unknown publication {publication!r}")

        if not section:
            path = skill.hub_path()
            return {"publication": skill.name, "section": "", "file": f"skills/{skill.name}/SKILL.md",
                    "markdown": self.body(path)}

        if section.startswith("intro:") or section.startswith("doc:"):
            kind, slug = section.split(":", 1)
            return self.read_section(publication, slug)

        # ``SYSE.24#solution`` addresses one section of one unit.
        if "#" in section:
            unit_part, anchor = section.split("#", 1)
            found = self.by_id.get(unit_part.strip())
            if found is None or found[0] is not skill:
                raise ValueError(f"unknown unit {unit_part!r} in {skill.name!r}")
            return self.read_pattern(unit_part.strip(), section=anchor)

        for slug in skill.intros:
            if slug == f"{section}.md" or slug == section:
                path = skill.reference / "intro" / slug
                return {"publication": skill.name, "section": section,
                        "file": f"skills/{skill.name}/reference/intro/{slug}",
                        "markdown": self.body(path)}
        for slug in skill.docs:
            if slug == f"{section}.md" or slug == section:
                path = skill.reference / "docs" / slug
                return {"publication": skill.name, "section": section,
                        "file": f"skills/{skill.name}/reference/docs/{slug}",
                        "markdown": self.body(path)}

        found = self.by_id.get(section.strip())
        if found is not None and found[0] is skill:
            data = self.read_pattern(section)
            return {"publication": skill.name, "section": section,
                    "file": data["file"], "markdown": data["markdown"]}

        raise ValueError(f"unknown section {section!r} in {skill.name!r}")

    def backlinks(self, pattern_id: str, limit: int = DEFAULT_PAGE,
                  offset: int = 0) -> Dict[str, Any]:
        target = pattern_id.strip()
        needle = re.compile(r"(?<![\w.])" + re.escape(target) + r"(?![\w.])")
        hits: List[Dict[str, Any]] = []
        for skill in self.skills.values():
            for entry in skill.units:
                if entry.get("id") == target:
                    continue
                path = skill.unit_path(entry)
                if not path.exists():
                    continue
                text = self.body(path)
                if needle.search(text):
                    hits.append({
                        "publication": skill.name,
                        "pattern_id": entry.get("id", ""),
                        "title": entry.get("title", ""),
                        "file": f"reference/{entry['framework']}/{entry['key']}",
                    })
        page = hits[offset:offset + limit]
        return {
            "pattern_id": target,
            "results": page,
            "total": len(hits),
            "next_offset": offset + limit if offset + limit < len(hits) else None,
        }

    # --- derived artefacts -------------------------------------------------
    def _json(self, skill: Skill, name: str) -> Dict[str, Any]:
        path = skill.reference / name
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception:
            return {}

    def route(self, unit_id: str) -> Dict[str, Any]:
        """What to read before a unit, and what a good result looks like."""
        found = self.by_id.get(unit_id.strip())
        if found is None:
            raise ValueError(f"unknown unit {unit_id!r}")
        skill, entry = found
        data = self._json(skill, "routes.json")
        for route in data.get("routes", []):
            if route.get("id") == unit_id.strip():
                return {"publication": skill.name, **route}
        raise ValueError(f"no route for {unit_id!r} in {skill.name!r}")

    def entries(self, q: str = "", publication: str = "",
                limit: int = DEFAULT_PAGE, offset: int = 0) -> Dict[str, Any]:
        """Situations stated in the publications, matched against a phrase."""
        terms = [t for t in re.split(r"[^\w.-]+", q.lower()) if t]
        pool = ([self.resolve_publication(publication)] if publication
                else list(self.skills.values()))
        hits: List[Dict[str, Any]] = []
        for skill in pool:
            if skill is None:
                raise ValueError(f"unknown publication {publication!r}")
            for row in self._json(skill, "entries.json").get("entries", []):
                text = (str(row.get("situation", "")) + " "
                        + str(row.get("title", ""))).lower()
                score = sum(1 for term in terms if term in text) if terms else 1
                if score:
                    hits.append({"publication": skill.name, "score": score, **row})
        hits.sort(key=lambda h: (-h["score"], h.get("start_with", [""])[0]))
        page = hits[offset:offset + limit]
        return {"entries": page, "total": len(hits),
                "next_offset": offset + limit if offset + limit < len(hits) else None}

    def glossary(self, q: str = "", publication: str = "",
                 limit: int = DEFAULT_PAGE, offset: int = 0) -> Dict[str, Any]:
        """One-line meanings, quoted from the units."""
        needle = q.strip().lower()
        pool = ([self.resolve_publication(publication)] if publication
                else list(self.skills.values()))
        rows: List[Dict[str, Any]] = []
        for skill in pool:
            if skill is None:
                raise ValueError(f"unknown publication {publication!r}")
            path = skill.reference / "glossary.md"
            if not path.exists():
                continue
            for line in path.read_text("utf-8").splitlines():
                if not line.startswith("| ") or line.startswith("| :") or "Term" in line:
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 3:
                    continue
                term, meaning, uid = cells[0], cells[1], cells[2].strip("` ")
                if needle and needle not in term.lower() and needle not in meaning.lower():
                    continue
                rows.append({"publication": skill.name, "term": term,
                             "meaning": meaning, "id": uid})
        page = rows[offset:offset + limit]
        return {"terms": page, "total": len(rows),
                "next_offset": offset + limit if offset + limit < len(rows) else None}

    def status(self) -> Dict[str, Any]:
        patterns = sum(1 for s in self.skills.values()
                       for u in s.units if u.get("role") == "pattern")
        return {
            "snapshot": self.snapshot,
            "skills_root": str(self.root),
            "skills": len(self.skills),
            "publications": len(self.skills),
            "patterns": patterns,
            "units": len(self.by_id),
            "kinds": _count_kinds(self.skills.values()),
            "tools": len(TOOLS),
        }


def _count_kinds(skills: Iterable[Skill]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for skill in skills:
        out[skill.kind or "?"] = out.get(skill.kind or "?", 0) + 1
    return dict(sorted(out.items()))


def _digest(path: Path) -> str:
    import hashlib
    if not path.exists():
        return "none"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

#: The seven reading tools and the arguments each accepts.  This is the
#: server's own contract: the tests assert it exactly, so an argument cannot
#: appear or vanish without a deliberate edit here.
READING_TOOLS: Dict[str, Tuple[str, ...]] = {
    "get_corpus_status": (),
    "list_publications": ("limit", "offset", "kind", "suite", "expected_snapshot"),
    "search": ("q", "publication", "kind", "suite", "limit", "offset",
               "expected_snapshot"),
    "get_table_of_contents": ("publication", "patterns_only", "limit", "offset",
                              "expected_snapshot"),
    "read_pattern": ("pattern_id", "publication", "tier", "section",
                     "limit", "offset", "expected_snapshot"),
    "read_section": ("publication", "section", "through", "limit", "offset",
                     "expected_snapshot"),
    "backlinks": ("pattern_id", "limit", "offset", "expected_snapshot"),
}

#: Retrieval tools that read the derived artefacts rather than the units.
DERIVED_TOOLS: Tuple[str, ...] = ("route", "entries", "glossary")

#: Tools that exist because this server is also a skill-maker front end.
MAKER_TOOLS: Tuple[str, ...] = (
    "list_profiles", "probe_document", "plan_decomposition", "verify_catalogue",
)


def _schema(properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


_PUBLICATION = {
    "type": "string",
    "description": "Skill name (decision-design) or DocID (PSDA). "
                   "Copy from list_publications.",
}
_LIMIT = {"type": "integer", "minimum": 1, "maximum": 200,
          "description": f"Page size; default {DEFAULT_PAGE}."}
_OFFSET = {"type": "integer", "minimum": 0,
           "description": "Results to skip; copy next_offset here to continue."}
_EXPECTED_SNAPSHOT = {
    "type": ["string", "null"],
    "description": "Copy the previous response's snapshot. Omit for a fresh "
                   "call. If the local build changed, the call fails and "
                   "discovery restarts.",
}
_KIND = {"type": "string",
         "description": "Filter by publication kind: FPF, DPF, Reference, Guide "
                        "(or the local labels FPF Core, Suite, Framework)."}
_SUITE = {"type": "string",
          "description": "Filter to one Suite, by slug (engineering) or skill "
                         "name (engineering-suite)."}
_TEXT_LIMIT = {"type": "integer", "minimum": 1,
               "description": "Truncate the returned Markdown to this many characters."}
_TEXT_OFFSET = {"type": "integer", "minimum": 0,
                "description": "Start the returned Markdown at this character."}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_corpus_status",
        "description": "Report what this server serves: skills root, snapshot, "
                       "skill and pattern counts. Call with {}.",
        "inputSchema": _schema({}, []),
    },
    {
        "name": "list_publications",
        "description": "List the skills available here, with their DocIDs and "
                       "pattern counts. Copy a skill name into 'publication'.",
        "inputSchema": _schema({"limit": _LIMIT, "offset": _OFFSET,
                                "kind": _KIND, "suite": _SUITE,
                                "expected_snapshot": _EXPECTED_SNAPSHOT}, []),
    },
    {
        "name": "search",
        "description": "Find units by ID or title words across every skill, or "
                       "within one publication. Words match loosely; a known ID "
                       "matches exactly.",
        "inputSchema": _schema({
            "q": {"type": "string", "description": "Words or a pattern ID."},
            "publication": _PUBLICATION,
            "kind": _KIND,
            "suite": _SUITE,
            "limit": _LIMIT,
            "offset": _OFFSET,
            "expected_snapshot": _EXPECTED_SNAPSHOT,
        }, ["q"]),
    },
    {
        "name": "get_table_of_contents",
        "description": "List the sections of one publication: its narrative "
                       "sections, whole documents and every addressable unit.",
        "inputSchema": _schema({
            "publication": _PUBLICATION,
            "patterns_only": {"type": "boolean",
                              "description": "Show pattern units only."},
            "limit": _LIMIT,
            "offset": _OFFSET,
            "expected_snapshot": _EXPECTED_SNAPSHOT,
        }, ["publication"]),
    },
    {
        "name": "read_pattern",
        "description": "Read one unit by its ID (SYSE.24, A.1). Returns the "
                       "source Markdown whole, or one tier of it, or one "
                       "named section. Prefer tier='contract' unless the "
                       "rationale or worked cases are needed.",
        "inputSchema": _schema({
            "pattern_id": {"type": "string",
                           "description": "Whole unit ID, e.g. SYSE.24."},
            "tier": {"type": "string", "enum": ["all", "contract", "source"],
                     "description": "Which sections to return. 'contract' is "
                                    "the working sections only -- typically "
                                    "40-65% of the bytes."},
            "section": {"type": "string",
                        "description": "One section by anchor, e.g. 'solution' "
                                       "or 'conformance-checklist'."},
            "publication": _PUBLICATION,
            "limit": _TEXT_LIMIT,
            "offset": _TEXT_OFFSET,
            "expected_snapshot": _EXPECTED_SNAPSHOT,
        }, ["pattern_id"]),
    },
    {
        "name": "read_section",
        "description": "Read a skill's entry point (omit section), one of its "
                       "narrative sections or documents, or a unit it contains.",
        "inputSchema": _schema({
            "publication": _PUBLICATION,
            "section": {"type": "string",
                        "description": "Section slug, 'intro:<slug>', 'doc:<slug>' "
                                       "or a unit ID. Omit for SKILL.md."},
            "through": {"type": "string",
                        "description": "End of an inclusive range; requires section."},
            "limit": _TEXT_LIMIT,
            "offset": _TEXT_OFFSET,
            "expected_snapshot": _EXPECTED_SNAPSHOT,
        }, ["publication"]),
    },
    {
        "name": "backlinks",
        "description": "Find units that mention a given ID literally. Read each "
                       "hit to judge the relation; a mention is not a dependency.",
        "inputSchema": _schema({
            "pattern_id": {"type": "string"},
            "limit": _LIMIT,
            "offset": _OFFSET,
            "expected_snapshot": _EXPECTED_SNAPSHOT,
        }, ["pattern_id"]),
    },
    {
        "name": "route",
        "description": "What to read before a unit can be applied: its direct "
                       "prerequisites, the full chain, and the section that "
                       "checks a result.",
        "inputSchema": _schema({
            "pattern_id": {"type": "string", "description": "Whole unit ID."},
        }, ["pattern_id"]),
    },
    {
        "name": "entries",
        "description": "Find a starting unit by the situation you are in, "
                       "using the questions the publications state for each "
                       "unit.",
        "inputSchema": _schema({
            "q": {"type": "string", "description": "Words describing the situation."},
            "publication": _PUBLICATION,
            "limit": _LIMIT,
            "offset": _OFFSET,
        }, []),
    },
    {
        "name": "glossary",
        "description": "One-line meanings of terms, quoted from the units "
                       "that define them.",
        "inputSchema": _schema({
            "q": {"type": "string", "description": "Filter by term or meaning."},
            "publication": _PUBLICATION,
            "limit": _LIMIT,
            "offset": _OFFSET,
        }, []),
    },
    {
        "name": "list_profiles",
        "description": "List the decomposition profiles: which kinds of "
                       "framework document this toolchain can split, and how.",
        "inputSchema": _schema({}, []),
    },
    {
        "name": "probe_document",
        "description": "Classify a Markdown document: its kind, the profile "
                       "that claims it, the evidence, and its unit count.",
        "inputSchema": _schema({
            "path": {"type": "string",
                     "description": "Path relative to the repository root."},
        }, ["path"]),
    },
    {
        "name": "plan_decomposition",
        "description": "Show the artefacts a decomposition of a document would "
                       "produce, without writing anything.",
        "inputSchema": _schema({
            "path": {"type": "string"},
            "skill": {"type": "string", "description": "Skill directory name."},
        }, ["path"]),
    },
    {
        "name": "verify_catalogue",
        "description": "Compare the publications in this repository with the "
                       "publisher's catalogue.",
        "inputSchema": _schema({
            "offline": {"type": "boolean",
                        "description": "Use the saved snapshot, not the network."},
        }, []),
    },
]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

class Server:
    def __init__(self, skills_root: Path):
        self.library = Library(skills_root)
        self.skills_root = skills_root

    # --- reading tools ----------------------------------------------------
    def call(self, name: str, args: Dict[str, Any]) -> Any:
        lib = self.library
        self._check_snapshot(args.get("expected_snapshot"))
        if name == "get_corpus_status":
            return lib.status()

        if name == "list_publications":
            rows = sorted((lib.publication_of(s)
                           for s in lib.filter_skills(str(args.get("kind") or ""),
                                                      str(args.get("suite") or ""))),
                          key=lambda r: (r["kind"], r["id"]))
            limit = int(args.get("limit") or DEFAULT_PAGE)
            offset = int(args.get("offset") or 0)
            return {
                "snapshot": lib.snapshot,
                "publications": rows[offset:offset + limit],
                "total": len(rows),
                "next_offset": offset + limit if offset + limit < len(rows) else None,
            }

        if name == "search":
            return lib.search(str(args.get("q", "")),
                              str(args.get("publication") or ""),
                              int(args.get("limit") or DEFAULT_PAGE),
                              int(args.get("offset") or 0),
                              str(args.get("kind") or ""),
                              str(args.get("suite") or ""))

        if name == "get_table_of_contents":
            return lib.table_of_contents(
                str(args["publication"]),
                bool(args.get("patterns_only")),
                int(args.get("limit") or 100),
                int(args.get("offset") or 0))

        if name == "read_pattern":
            data = lib.read_pattern(str(args["pattern_id"]),
                                    str(args.get("tier") or "all"),
                                    str(args.get("section") or ""))
            hint = str(args.get("publication") or "")
            if hint:
                skill = lib.resolve_publication(hint)
                if skill is not None and skill.name != data["publication"]:
                    raise ValueError(
                        f"{args['pattern_id']} belongs to {data['publication']!r}, "
                        f"not {hint!r}")
            return _truncate(data, args.get("limit"), args.get("offset"))

        if name == "read_section":
            publication = str(args["publication"])
            section = str(args.get("section") or "")
            through = str(args.get("through") or "")
            if through:
                if not section:
                    raise ValueError("through requires a starting section")
                data = lib.read_range(publication, section, through)
            else:
                data = lib.read_section(publication, section)
            return _truncate(data, args.get("limit"), args.get("offset"))

        if name == "backlinks":
            return lib.backlinks(str(args["pattern_id"]),
                                 int(args.get("limit") or DEFAULT_PAGE),
                                 int(args.get("offset") or 0))

        # --- skill-maker tools -------------------------------------------
        if name == "route":
            return lib.route(str(args["pattern_id"]))

        if name == "entries":
            return lib.entries(str(args.get("q") or ""),
                               str(args.get("publication") or ""),
                               int(args.get("limit") or DEFAULT_PAGE),
                               int(args.get("offset") or 0))

        if name == "glossary":
            return lib.glossary(str(args.get("q") or ""),
                                str(args.get("publication") or ""),
                                int(args.get("limit") or DEFAULT_PAGE),
                                int(args.get("offset") or 0))

        if name == "list_profiles":
            from skillmaker import frameworks as F
            return {
                "profiles": [
                    {"key": p.key, "kind": p.kind.value, "name": p.name,
                     "layout": p.shape.layout.value, "description": p.description}
                    for p in F.all_profiles()
                ],
            }

        if name == "probe_document":
            from skillmaker import frameworks as F
            path = (self.skills_root.parent / str(args["path"])).resolve()
            if not path.exists():
                raise ValueError(f"not found: {args['path']}")
            text = path.read_text("utf-8", errors="replace")
            profile, detection = F.detect(str(args["path"]), text)
            tree = F.decompose(profile, text, str(args["path"]))
            return {
                "path": str(args["path"]),
                "kind": profile.kind.value,
                "profile": profile.key,
                "evidence": list(detection.reasons),
                "score": detection.score,
                "units": len(tree.units),
                "patterns": len(tree.patterns),
                "roles": tree.by_role(),
            }

        if name == "plan_decomposition":
            from skillmaker import frameworks as F
            path = (self.skills_root.parent / str(args["path"])).resolve()
            if not path.exists():
                raise ValueError(f"not found: {args['path']}")
            text = path.read_text("utf-8", errors="replace")
            profile, _ = F.detect(str(args["path"]), text)
            tree = F.decompose(profile, text, str(args["path"]))
            skill = str(args.get("skill") or profile.key)
            return {
                "kind": profile.kind.value,
                "profile": profile.key,
                "shape": profile.shape.describe(),
                "units": len(tree.units),
                "artefacts": profile.shape.outputs(
                    skill, [skill], tree.filenames()),
            }

        if name == "verify_catalogue":
            from skillmaker import frameworks as F
            local = F.load_local(self.skills_root.parent, classify=F.classify)
            if args.get("offline"):
                snapshot = _SCRIPT_DIR / "catalogue.snapshot.json"
                remote, meta = F.load_snapshot(snapshot)
            else:
                remote, meta = F.load_remote()
            issues = F.verify(local, remote)
            return {
                "publisher_snapshot": meta.get("snapshot", ""),
                "publications": len(local),
                "issues": [i.describe() for i in issues],
                "ok": not issues,
            }

        raise ValueError(f"unknown tool {name!r}")

    def _check_snapshot(self, expected: Any) -> None:
        """Fail loudly when a caller continues against a changed build.

        A continuation pinned to an old snapshot is refused rather than
        silently answered from a different edition.
        """
        if not expected:
            return
        current = self.library.snapshot
        if str(expected) != current:
            raise ValueError(
                f"snapshot changed (expected {expected}, serving {current}); "
                f"restart discovery with offset 0 and omit expected_snapshot")

    # --- json-rpc ---------------------------------------------------------
    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}

        if method == "initialize":
            return _result(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION,
                               "title": "FPF local skills"},
                "instructions": (
                    "Local skill library built by skill-maker. Reading tools "
                    "follow one contract: search, read_pattern, "
                    "read_section, get_table_of_contents, list_publications, "
                    "get_corpus_status, backlinks. Publication IDs are skill "
                    "names or DocIDs from list_publications. Read source "
                    "passages before applying them."
                ),
            })

        if method in ("notifications/initialized", "notifications/cancelled"):
            return None

        if method == "ping":
            return _result(msg_id, {})

        if method == "tools/list":
            return _result(msg_id, {"tools": TOOLS})

        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            try:
                payload = self.call(name, args)
                return _result(msg_id, {
                    "content": [{"type": "text",
                                 "text": json.dumps(payload, indent=2, ensure_ascii=False)}],
                    "isError": False,
                })
            except Exception as exc:  # noqa: BLE001 - reported to the client
                return _result(msg_id, {
                    "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                    "isError": True,
                })

        if msg_id is None:
            return None
        return _error(msg_id, -32601, f"method not found: {method}")


def _truncate(data: Dict[str, Any], limit: Any, offset: Any) -> Dict[str, Any]:
    """Apply character-based limit/offset to a Markdown payload."""
    if not limit and not offset:
        return data
    text = data.get("markdown", "")
    start = int(offset or 0)
    end = start + int(limit) if limit else len(text)
    out = dict(data)
    out["markdown"] = text[start:end]
    out["truncated"] = end < len(text) or start > 0
    out["next_offset"] = end if end < len(text) else None
    return out


def _result(msg_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------

def serve(server: Server, stdin=None, stdout=None) -> int:
    """Read newline-delimited JSON-RPC on stdin, write responses to stdout."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error(None, -32700, f"parse error: {exc}")
        else:
            try:
                response = server.handle(message)
            except Exception:  # noqa: BLE001 - never kill the transport
                traceback.print_exc(file=sys.stderr)
                response = _error(message.get("id"), -32603, "internal error")
        if response is not None:
            # MCP stdio messages must not contain embedded newlines.
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def selftest(skills_root: Path) -> int:
    """Exercise the server without a client, so it can be checked in CI."""
    server = Server(skills_root)
    ok = True

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal ok
        if not condition:
            ok = False
            print(f"  \u2717 {label}: {detail}")
        else:
            print(f"  \u2713 {label}")

    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {}})
    check("initialize", init["result"]["protocolVersion"] == PROTOCOL_VERSION)
    tools = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                           "params": {}})
    check("tools/list", len(tools["result"]["tools"]) == len(TOOLS))

    status = server.call("get_corpus_status", {})
    check("status counts skills", status["skills"] >= 15, str(status["skills"]))
    check("status counts patterns", status["patterns"] == 885, str(status["patterns"]))

    pubs = server.call("list_publications", {"limit": 100})
    check("lists publications", pubs["total"] >= 15, str(pubs["total"]))

    hit = server.call("search", {"q": "decision", "limit": 3})
    check("search returns results", hit["total"] > 0)

    unit = server.call("read_pattern", {"pattern_id": "PSDA.1"})
    check("read_pattern", "PSDA" in unit["markdown"])

    section = server.call("read_section", {"publication": "PSDA"})
    check("read_section defaults to SKILL.md", "---" in section["markdown"])

    toc = server.call("get_table_of_contents", {"publication": "PSDA", "limit": 5})
    check("table of contents", toc["total"] > 0)

    back = server.call("backlinks", {"pattern_id": "PSDA.1", "limit": 3})
    check("backlinks", "total" in back)

    profiles = server.call("list_profiles", {})
    check("list_profiles", len(profiles["profiles"]) == 8)

    probe = server.call("probe_document", {"path": "DPFs/README.md"})
    check("probe_document", probe["kind"] == "Guide", probe["kind"])

    plan = server.call("plan_decomposition", {"path": "DPFs/README.md", "skill": "guide"})
    check("plan_decomposition", len(plan["artefacts"]) > 0)

    err = server.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                         "params": {"name": "read_pattern",
                                    "arguments": {"pattern_id": "NOPE.99"}}})
    check("unknown unit is an error", err["result"]["isError"] is True)

    print("selftest:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="mcp_server.py",
        description="Serve a built skills/ tree over the Model Context Protocol.")
    ap.add_argument("--skills-root", type=Path, default=_REPO_ROOT / "skills")
    ap.add_argument("--http", nargs="?", const="127.0.0.1:8765", default="",
                    metavar="HOST:PORT",
                    help="serve Streamable HTTP instead of stdio "
                         "(default 127.0.0.1:8765)")
    ap.add_argument("--selftest", action="store_true",
                    help="run built-in checks instead of serving")
    ap.add_argument("--list-tools", action="store_true",
                    help="print the tool list and exit")
    args = ap.parse_args()

    root = args.skills_root.resolve()
    if args.list_tools:
        print(json.dumps(TOOLS, indent=2, ensure_ascii=False))
        return 0
    if args.selftest:
        return selftest(root)

    server = Server(root)
    print(f"{SERVER_NAME} {SERVER_VERSION}: serving {len(server.library.skills)} "
          f"skills from {root}", file=sys.stderr)

    if args.http:
        from skillmaker import http_transport
        host, _, port = args.http.partition(":")
        try:
            port_number = int(port or 8765)
        except ValueError:
            print(f"Error: bad --http value {args.http!r}; use HOST:PORT",
                  file=sys.stderr)
            return 2
        return http_transport.serve(
            server, host or "127.0.0.1", port_number,
            connect_page=_connect_page(root))

    return serve(server)


def _connect_page(skills_root: Path):
    """The page served at ``/``: the skill tree's own connection guide.

    Only a *built* guide is served.  The template is deliberately not a
    candidate: it carries ``{{...}}`` placeholders, and a browser showing
    ``{{TOOL_COUNT}} tools`` is worse than the short built-in text below.
    """
    candidates = [
        skills_root / "CONNECT.md",
        skills_root.parent / "CONNECT.md",
    ]

    def page() -> str:
        for path in candidates:
            if path.exists():
                return path.read_text("utf-8")
        return ("# MCP endpoint\n\n"
                "POST JSON-RPC to `/mcp`. Send `initialize` first; the response "
                "carries `Mcp-Session-Id`, which every later request must "
                "repeat. `GET /mcp` returns 405: this server opens no streams.\n")

    return page


if __name__ == "__main__":
    sys.exit(main())
