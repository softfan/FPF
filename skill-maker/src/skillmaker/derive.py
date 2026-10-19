#!/usr/bin/env python3
"""
derive.py -- the artefacts a reader needs that the source does not contain.

A publication states its units and their dependencies.  It does not state:

* **routes** -- the ordered units needed before one of them can be applied;
* **entries** -- "I have this situation, where do I start?";
* **glossary** -- what a term means in one line, without the argument;
* **boot** -- the twelve lines a session should read first.

None of these can be copied from the source, because the source is organised for
reading, not for retrieval.  All of them can be *derived* from it, which is the
difference between generating them once and maintaining them by hand.

Every artefact here is marked derived.  A hand-written route that must survive a
rebuild lives in ``curated-routes.json``, which the builder never overwrites.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence

from skillmaker._fpf_common import clean, sort_key


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

def _split_ids(text: str, known: set) -> List[str]:
    """Pull unit IDs out of a prose dependency cell."""
    if not text:
        return []
    out: List[str] = []
    for token in re.findall(
            r"\b[A-Za-z][A-Za-z0-9]*(?:[.:][A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*)*\b",
            text):
        if token in known and token not in out:
            out.append(token)
    return out


def build_graph(units: Sequence, deps: Dict[str, str]) -> Dict[str, List[str]]:
    """``unit id -> ids it builds on``, restricted to units in this skill."""
    known = {u.id for u in units}
    graph: Dict[str, List[str]] = {}
    for unit in units:
        raw = deps.get(unit.id, "")
        graph[unit.id] = [d for d in _split_ids(raw, known) if d != unit.id]
    return graph


def _closure(start: str, graph: Dict[str, List[str]]) -> List[str]:
    """Every unit *start* depends on, in dependency order, excluding itself.

    The publications state dependencies as prose, so cycles exist (two units
    that cite each other).  A cycle is not an error here -- it is two units that
    belong together -- so the walk tolerates one rather than looping.
    """
    reachable: List[str] = []
    seen = {start}
    stack = list(graph.get(start, []))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        reachable.append(node)
        stack.extend(graph.get(node, []))

    # Topological order: a unit appears after everything it builds on.
    ordered: List[str] = []
    placed: set = set()

    def place(node: str, path: set) -> None:
        if node in placed or node in path:
            return
        for dep in graph.get(node, []):
            if dep in seen:
                place(dep, path | {node})
        if node not in placed and node != start:
            placed.add(node)
            ordered.append(node)

    for node in sorted(reachable, key=sort_key):
        place(node, set())
    return ordered


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def routes(units: Sequence, deps: Dict[str, str], toc: Dict[str, object],
           section_info: Dict[str, object],
           limit: int = 0) -> Dict[str, object]:
    """The ordered units needed before each unit can be applied.

    A route is derived, not curated: it is the transitive ``Builds on`` closure,
    in dependency order, with the unit itself last.  It answers one question --
    "what do I have to read before this one makes sense?" -- and it is honest
    about being a mechanical answer.

    The situation text comes from the unit's own first search query, which the
    publication already states as the question the unit answers.
    """
    graph = build_graph(units, deps)
    by_id = {u.id: u for u in units}
    out: List[Dict[str, object]] = []

    for unit in sorted(units, key=lambda u: sort_key(u.id)):
        chain = _closure(unit.id, graph)
        if not chain:
            continue
        entry = toc.get(unit.id)
        situation = ""
        if entry is not None:
            queries = getattr(entry, "search_queries", "") or ""
            # Same extraction the entries index uses: the publication writes
            # its queries as quoted phrases, and a plain split on "?" leaves
            # the quotes and the trailing prose glued to the first question.
            found = _queries_of(queries)
            situation = found[0] if found else ""
        info = section_info.get(unit.id)
        acceptance = ""
        budget = 0
        if info is not None and getattr(info, "sections", None):
            found = info.find("conformance")
            acceptance = found.anchor if found else ""
            budget = info.tier_bytes("contract")
        out.append({
            "id": unit.id,
            "title": unit.title,
            "situation": situation or unit.title,
            # Direct prerequisites first: for a dense dependency graph the full
            # closure can name half the publication, which is true but not a
            # useful reading order on its own.
            "direct": graph.get(unit.id, []),
            "chain": chain + [unit.id],
            "depth": len(chain),
            "acceptance": acceptance,
            "contract_bytes": budget,
        })

    if limit:
        out = out[:limit]
    return {"derived": True,
            "note": "Derived from the publication's Builds on column. "
                    "A curated route, if any, is in curated-routes.json.",
            "routes": out}


def merge_curated(derived: Dict[str, object],
                  curated: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Overlay hand-written routes on the derived ones.

    A curated route wins on its own id, so a reader who corrects a chain is not
    overwritten by the next build.
    """
    if not curated:
        return derived
    merged = dict(derived)
    by_id = {r["id"]: r for r in derived.get("routes", [])}
    for route in curated.get("routes", []):
        if route.get("id"):
            by_id[route["id"]] = {**by_id.get(route["id"], {}), **route,
                                  "derived": False}
    merged["routes"] = sorted(by_id.values(), key=lambda r: sort_key(r["id"]))
    merged["curated"] = len(curated.get("routes", []))
    return merged


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------

def _queries_of(cell: str) -> List[str]:
    """The questions in one ``Queries`` cell.

    Two shapes occur: quoted phrases (``"Which model applies?" "What reopens
    the cut?"``) and a plain list separated by question marks.  Both are the
    publication's own wording, so neither needs rewriting.
    """
    quoted = [q.strip() for q in re.findall(r'"([^"]{12,})"', cell)]
    if quoted:
        return quoted
    text = clean(cell)
    parts = [p.strip(" .*\u2014-") for p in text.split("?")]
    return [p + "?" for p in parts if len(p) >= 12]


def entries(units: Sequence, toc: Dict[str, object],
            section_info: Dict[str, object]) -> Dict[str, object]:
    """Situation -> the unit to start with.

    The publication states each unit's queries as the questions it answers.
    Turning them around gives an entry point: the situation in the asker's
    words, the unit that answers it, what a good result looks like, and how much
    it costs to read.
    """
    out: List[Dict[str, object]] = []
    for unit in sorted(units, key=lambda u: sort_key(u.id)):
        entry = toc.get(unit.id)
        if entry is None:
            continue
        queries = getattr(entry, "search_queries", "") or ""
        found = _queries_of(queries)
        if not found:
            continue
        info = section_info.get(unit.id)
        acceptance = ""
        if info is not None and getattr(info, "sections", None):
            section = info.find("conformance")
            acceptance = section.anchor if section else ""
        for situation in found[:2]:
            out.append({
                "situation": situation.strip().rstrip("?"),
                "start_with": [unit.id],
                "title": unit.title,
                "acceptance": acceptance,
                "contract_bytes": (info.tier_bytes("contract")
                                   if info is not None else 0),
                # A unit written without section headings has no tier at all;
                # "0 KB of working sections" would read as "free to read".
                "has_sections": bool(getattr(info, "sections", None)),
            })
    return {"derived": True, "entries": out}


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------

#: Lead-ins that carry no meaning in a glossary line.  Stripping them turns
#: "Use this pattern when one wording is becoming naturalized" into a statement
#: about the situation, which is what a glossary row is for.  The same formula
#: appears with "method", "section", "unit" and "framework" as the noun.
_LEAD_INS = (
    "use this pattern when", "use this pattern if", "use this when",
    "use this method when", "use this method if", "use this method to",
    "use this method for", "use this section when", "use this unit when",
    "this pattern applies when", "this pattern applies if",
    "this pattern is used when", "this method applies when",
    "this method applies if", "this method is used when",
    "apply this pattern when", "apply this method when",
    "this unit applies when", "this pattern helps when", "use it when",
)

#: A definition may not begin with these: they restate the heading instead of
#: saying what the unit is for.
_WEAK_OPENERS = (
    "this pattern", "this section", "this unit", "the pattern", "in this",
    "this document", "the following", "here we", "this chapter",
)

#: A body may open with a list.  "1." is not a definition, and a numbered
#: requirement is not a summary of what the unit is for.
_LIST_ITEM_RE = re.compile(r"^(?:\(?\d+[.)]|\(?[a-zA-Z][.)]|[-*•+])\s")

#: The general form of the fixed lead-ins above: "Use U.WorkPlan when ...",
#: "Use this pattern to ...".  The noun phrase is kept short on purpose, so an
#: ordinary sentence beginning "Use of the method requires ..." is untouched.
#: Only ``when``/``if``/``to`` are stripped: a temporal lead-in ("while the team
#: is still forming, and stop when it settles") is part of the sentence's
#: structure, and removing it leaves a fragment.
_LEAD_IN_RE = re.compile(
    r"^(?:use|apply)\s+[\w.'’\-]+(?:\s+[\w.'’\-]+){0,4}\s+(?:when|if|to)\s+",
    re.IGNORECASE,
)


def _strip_lead_in(sentence: str) -> str:
    low = sentence.lower()
    for lead in _LEAD_INS:
        if low.startswith(lead):
            rest = sentence[len(lead):].lstrip(" ,:—-")
            if rest:
                return rest[0].upper() + rest[1:]
    match = _LEAD_IN_RE.match(sentence)
    if match:
        rest = sentence[match.end():].lstrip(" ,:—-")
        if rest:
            return rest[0].upper() + rest[1:]
    return sentence


def _first_sentence(text: str, limit: int = 160) -> str:
    """The first real sentence of a unit body, as a definition.

    "Real" excludes the shapes that only look like prose: a metadata block, a
    heading, a table row, a list item, and a short bold label such as
    "**Intent.**" that a line begins with before the sentence that says
    anything.
    """
    body = text.split("\n", 1)[1] if "\n" in text else ""
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "|", ">", "<!--")):
            continue
        if _LIST_ITEM_RE.match(line):
            continue
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"[*_`]", "", line)
        line = clean(line)
        for candidate in re.split(r"(?<=[.!?])\s+", line):
            sentence = _strip_lead_in(candidate).strip()
            # A label ("Intent.") or a fragment carries no meaning here; the
            # next sentence in the same line usually does.
            if len(sentence) < 25:
                continue
            if sentence.lower().startswith(_WEAK_OPENERS):
                continue
            if len(sentence) > limit:
                sentence = sentence[:limit].rsplit(" ", 1)[0] + "…"
            return sentence
    return ""


def glossary(units: Sequence, bodies: Dict[str, str],
             patterns_only: bool = True) -> List[Dict[str, str]]:
    """Term -> one-line meaning -> canonical ID.

    The line is quoted from the unit, not invented: a generated definition that
    paraphrases freely is a claim the source does not make.
    """
    out: List[Dict[str, str]] = []
    for unit in sorted(units, key=lambda u: sort_key(u.id)):
        if patterns_only and unit.role != "pattern":
            continue
        text = bodies.get(unit.id, "")
        meaning = _first_sentence(text)
        if not meaning:
            continue
        out.append({"term": unit.title, "meaning": meaning, "id": unit.id})
    return out


def render_glossary(rows: Iterable[Dict[str, str]], title: str) -> str:
    rows = list(rows)
    lines = [f"# Glossary -- {title}", "",
             "Generated from the publication. Each line is taken from the "
             "unit's own opening, with a lead-in such as \"Use this pattern "
             "when\" removed, so it says what the source says and no more. "
             "Follow the ID for the full account.", "",
             "| Term | What it is for | Unit |", "| :--- | :--- | :--- |"]
    for row in rows:
        meaning = row["meaning"].replace("|", "\\|")
        term = row["term"].replace("|", "\\|")
        lines.append(f"| {term} | {meaning} | `{row['id']}` |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

def render_boot(cfg_name: str, title: str, kind: str, genre: str,
                pattern_count: int, unit_count: int,
                entry_example: str, rebuild_cmd: str,
                has_docs: bool, has_roles: bool) -> str:
    """A dozen lines a session reads before anything else."""
    lines = [
        f"# {title}",
        "",
        f"{kind} · {unit_count} addressable units"
        + (f" ({pattern_count} patterns)" if pattern_count else "")
        + f" · genre `{genre}`",
        "",
        "1. Read `reference/index.md` to see what is here.",
        "2. Find a unit by ID (`reference/pattern-index.md`), by question "
        "(`reference/query-index.md`) or by keyword (`reference/keyword-index.md`).",
        "3. Read the working sections first: `tier=\"contract\"` or "
        "`contract/<ID>.md`. Open the depth sections only when the working "
        "sections leave a real question.",
        f"4. Cite the unit ID and its section anchor, e.g. `{entry_example}`.",
    ]
    if has_docs:
        lines.append("5. Read `reference/docs/` as published; those documents "
                     "are not split.")
    if has_roles:
        lines.append("6. `roles/` holds the pipeline: classify, retrieve, "
                     "answer, review.")
    lines += [
        "",
        f"Rebuild: `{rebuild_cmd}`",
        "",
        "This file is generated. Edit the source publication, not this skill.",
        "",
    ]
    return "\n".join(lines)
