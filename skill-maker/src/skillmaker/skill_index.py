#!/usr/bin/env python3
"""
skill_index.py -- write the map of ``skills/``.

Fifteen directories with names like ``psda`` and ``nstd`` are not a map.  This
script writes two:

``skills/README.md``
    The human entry point: what each skill is, which DocIDs it answers for, how
    much is in it, and when to reach for it.

``skills/index.json``
    The machine entry point: the same facts, plus a DocID -> skill routing table
    so a caller holding ``PSDA.1`` can find the skill without knowing that it is
    called ``decision-design``.

Both are generated from the build configuration and the manifests the splitter
writes, so they cannot drift from what was actually built.

Usage::

    python skill-maker/src/skillmaker/skill_index.py            # write both
    python skill-maker/src/skillmaker/skill_index.py --check    # exit 1 if they are stale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

_SCRIPT_DIR = Path(__file__).resolve().parent
_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
_MAKER_DIR = _PKG_PARENT.parent           # skill-maker/
_REPO_ROOT = _MAKER_DIR.parent            # repository root
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import ensure_utf8_stdio, write_text_lf  # noqa: E402

ensure_utf8_stdio()

from skillmaker.skill_config import (  # noqa: E402
    DPF_SKILL_CONFIGS,
    FPF_CONFIG,
    SUITE_SKILL_CONFIGS,
    SUITES,
    SkillConfig,
)

SKILLS_ROOT = _REPO_ROOT / "skills"


# ---------------------------------------------------------------------------
# Collect
# ---------------------------------------------------------------------------

def _manifest(cfg: SkillConfig) -> List[Dict]:
    path = cfg.output / f".{cfg.name}_manifest.json"
    if not path.exists():
        return []
    return json.loads(path.read_text("utf-8"))


def _docids(cfg: SkillConfig) -> List[str]:
    """DocIDs this skill answers for."""
    out: List[str] = []
    for fw in cfg.frameworks:
        if fw.docid:
            out.append(fw.docid)
    for doc in cfg.docs:
        if doc.docid:
            out.append(doc.docid)
    return out


def _entry(cfg: SkillConfig, kind: str) -> Dict:
    entries = _manifest(cfg)
    patterns = sum(1 for e in entries if e.get("role") == "pattern")
    units = sum(1 for e in entries
                if e.get("kind") == "unit" and e.get("role") != "pattern")
    docs = sum(1 for e in entries if e.get("kind") == "doc")
    intros = sum(1 for e in entries if e.get("kind") == "intro")

    sources = [str(fw.source.relative_to(_REPO_ROOT)).replace("\\", "/")
               for fw in cfg.frameworks]

    return {
        "name": cfg.name,
        "kind": kind,
        "title": cfg.title or cfg.name,
        "docids": _docids(cfg),
        "frameworks": [fw.name for fw in cfg.frameworks],
        "patterns": patterns,
        "reference_units": units,
        "intro_sections": intros,
        "documents": docs,
        "path": f"skills/{cfg.name}",
        "sources": sources,
        "description": cfg.source_note or "",
        "built": bool(entries),
    }


#: An identifier-shaped token: DocID plus at least one dotted or sectioned
#: segment.  Deliberately loose -- the lookup against known IDs does the
#: filtering, which is far cheaper than one regex alternation over 1500 IDs.
_ID_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:[.:][A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*)+\b")


def _all_units(rows: List[Dict]) -> Dict[str, Dict]:
    """Every unit ID in the library, with the skill that owns it."""
    out: Dict[str, Dict] = {}
    for row in rows:
        if not row["built"]:
            continue
        for entry in _manifest_by_name(row["name"]):
            if entry.get("kind") == "unit" and entry.get("id"):
                out.setdefault(entry["id"], {
                    "skill": row["name"],
                    "framework": entry.get("framework", ""),
                    "key": entry.get("key", ""),
                    "title": entry.get("title", ""),
                })
    return out


def _manifest_by_name(name: str) -> List[Dict]:
    path = SKILLS_ROOT / name / f".{name}_manifest.json"
    if not path.exists():
        return []
    return json.loads(path.read_text("utf-8"))


def cross_references(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """IDs cited from inside one skill that another skill owns.

    A management pattern citing ``SYSE.24`` is a real dependency across a skill
    boundary.  Nothing inside the citing skill can resolve it, so the library
    has to say where it lives -- otherwise the reader follows a dead end.
    """
    units = _all_units(rows)
    out: Dict[str, List[Dict]] = {}
    for row in rows:
        if not row["built"]:
            continue
        found: Dict[str, Dict] = {}
        for entry in _manifest_by_name(row["name"]):
            if entry.get("kind") != "unit":
                continue
            path = (SKILLS_ROOT / row["name"] / "reference" / entry["framework"]
                    / entry["key"])
            if not path.exists():
                continue
            text = path.read_text("utf-8", errors="replace")
            for token in set(_ID_TOKEN_RE.findall(text)):
                owner = units.get(token)
                if owner is None or owner["skill"] == row["name"]:
                    continue
                found.setdefault(token, {
                    "id": token,
                    "title": owner["title"],
                    "skill": owner["skill"],
                    "file": f"skills/{owner['skill']}/reference/"
                            f"{owner['framework']}/{owner['key']}",
                })
        if found:
            out[row["name"]] = [found[k] for k in sorted(found)]
    return out


def collect() -> List[Dict]:
    """Every skill, in a deliberate order: Core, Suites, then frameworks."""
    rows: List[Dict] = [_entry(FPF_CONFIG, "FPF Core")]
    for slug in SUITES:
        cfg = SUITE_SKILL_CONFIGS[slug]
        row = _entry(cfg, "Suite")
        row["members"] = [m.title for m in SUITES[slug].members]
        rows.append(row)
    for cfg in sorted(DPF_SKILL_CONFIGS.values(), key=lambda c: c.name):
        rows.append(_entry(cfg, "Framework"))
    return rows


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

#: One line per skill saying when to reach for it.  Kept short on purpose: the
#: full description is one directory down, in the skill's own README.
WHEN = {
    "fpf": "Shared concepts, reasoning discipline and cross-domain methods. "
           "Start here when the difficulty is general rather than field-specific.",
    "engineering-suite": "Design, realize, change and sustain functioning "
                         "systems, including their access and meaning arrangements.",
    "management-suite": "Direction, commitments, operations, resources, "
                        "markets, communities and organizational change.",
    "foundational-thinking-suite": "Mathematical, physical, computational, "
                                   "modelling and notational constructions.",
    "human-capability-engineering-suite": "Help a person become able to do "
                                          "something, and keep it usable.",
    "decision-design": "Formulate a decision problem, construct alternatives, "
                       "and connect a recommendation to its use.",
    "research-methods": "Qualify a question, conduct a defensible inquiry and "
                        "return a warranted contribution.",
    "explanation-design": "Help a recipient recover and use a warranted "
                          "connection.",
    "narrativization": "Turn connected material into an account a reader can "
                       "follow and use.",
    "implementation-facilitation": "Put an evidence-informed practice to use "
                                   "under local conditions.",
    "economic-reasoning": "Connect plans and knowledge with scarce means "
                          "through calculation, exchange and commitments.",
    "financial-modeling": "Model financial positions, rights, obligations, "
                          "events and flows.",
    "defense-transmission": "Explain how practices persist and spread, and how "
                            "protective action changes that.",
    "embodied-rhythmics": "Recognize, shape, perform and learn rhythmic "
                          "relations.",
    "music-dance-practice": "Create, perform, transmit and develop music and "
                            "dance practices.",
}

HEADER = """\
# Skills

Generated from the publications in this repository. **Do not edit by hand** --
run the build (`skill-maker/build.sh`, `build.cmd` or `build.ps1`), or
`python skill-maker/src/skillmaker/skill_index.py` on its own.

Each directory is a self-contained skill: `SKILL.md` is the entry point an
agent loads first, `README.md` explains the directory, and `reference/` holds
the publication split into addressable files.

```
<skill>/
├── SKILL.md              entry point: what this skill is for, where to start
├── README.md             the same, for a human reader
└── reference/
    ├── index.md          what is in this skill
    ├── pattern-index.md  ID → title → builds on → file
    ├── query-index.md    question → ID
    ├── keyword-index.md  keyword → IDs
    ├── reference-index.md non-pattern units (Reference, Applications, Sources)
    ├── docs/             whole documents, read as published
    ├── intro/            narrative sections of the publication
    └── <docid>/          one file per pattern, named by its ID
```

## Which skill do I need?

If you have a **pattern ID** (`SYSE.24`, `PSDA.1`), the DocID names the skill:

{route_table}

If you have a **question**, start with `fpf` for general reasoning, or pick the
field below.

Publications cite each other across skill boundaries -- a management pattern
citing `SYSE.24`, a DPF citing FPF `A.1`. Those identifiers are listed in
[CROSS-REFERENCES.md](CROSS-REFERENCES.md), and the MCP server resolves them
without the table.

## All skills
"""


def _route_table(rows: List[Dict]) -> str:
    lines = ["| DocID | Skill |", "| :--- | :--- |"]
    pairs = []
    for row in rows:
        for docid in row["docids"]:
            pairs.append((docid, row["name"]))
    for docid, name in sorted(pairs, key=lambda p: p[0].lower()):
        lines.append(f"| `{docid}` | [{name}]({name}/) |")
    return "\n".join(lines)


def _table(rows: List[Dict]) -> str:
    lines = [
        "| Skill | Kind | DocIDs | Patterns | Other units | Covers |",
        "| :--- | :--- | :--- | ---: | ---: | :--- |",
    ]
    for row in rows:
        docids = ", ".join(f"`{d}`" for d in row["docids"])
        when = WHEN.get(row["name"], "")
        lines.append(
            f"| [{row['name']}]({row['name']}/) | {row['kind']} | {docids} | "
            f"{row['patterns']} | {row['reference_units']} | {when} |")
    return "\n".join(lines)


def render(rows: List[Dict]) -> str:
    total_p = sum(r["patterns"] for r in rows)
    total_u = sum(r["reference_units"] for r in rows)
    total_d = sum(r["documents"] for r in rows)
    parts = [
        HEADER.format(route_table=_route_table(rows)),
        "",
        _table(rows),
        "",
        "---",
        "",
        f"{len(rows)} skills · {total_p} patterns · {total_u} other units · "
        f"{total_d} whole documents.",
        "",
        "A Suite skill bundles several frameworks; a Framework skill holds one. "
        "The `-suite` suffix marks the difference.",
        "",
    ]
    return "\n".join(parts)


def render_cross(rows: List[Dict], cross: Dict[str, List[Dict]]) -> str:
    total = sum(len(v) for v in cross.values())
    lines = [
        "# Cross-skill references",
        "",
        "Generated. **Do not edit by hand.**",
        "",
        f"{total} identifiers are cited from inside one skill and owned by "
        f"another. A skill's own indexes cannot resolve these, so a reader "
        f"following one has to know where it lives. The MCP server resolves "
        f"them automatically; `read_pattern` takes the ID and finds the skill.",
        "",
        "| Cited from | ID | Lives in | Title |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for source in sorted(cross):
        for ref in cross[source]:
            lines.append(f"| {source} | `{ref['id']}` | "
                         f"[{ref['skill']}](../{ref['skill']}/) | "
                         f"{ref['title']} |")
    if not total:
        lines.append("| _(none)_ | | | |")
    lines.append("")
    return "\n".join(lines)


def render_connect(rows: List[Dict]) -> str:
    """The connection guide, from the same facts as the index."""
    template = _SCRIPT_DIR / "templates" / "CONNECT.md.template"
    if not template.exists():
        return ""
    text = template.read_text("utf-8")
    totals = {
        "{{SKILL_COUNT}}": str(len(rows)),
        "{{PATTERN_COUNT}}": str(sum(r["patterns"] for r in rows)),
        "{{UNIT_COUNT}}": str(sum(r["patterns"] + r["reference_units"] for r in rows)),
        "{{TOOL_COUNT}}": str(_tool_count()),
        "{{MAKER_DIR}}": "skill-maker",
        "{{SKILLS_DIR}}": "skills",
        "{{ENTRY_EXAMPLE}}": _entry_example(rows),
    }
    for key, value in totals.items():
        text = text.replace(key, value)
    return text


def _tool_count() -> int:
    try:
        from skillmaker import mcp_server
        return len(mcp_server.TOOLS)
    except Exception:
        return 0


def _entry_example(rows: List[Dict]) -> str:
    for row in rows:
        if row["patterns"] and row["docids"]:
            return f"{row['docids'][0]}.1"
    return "A.1"


def payload(rows: List[Dict]) -> Dict:
    routing: Dict[str, str] = {}
    for row in rows:
        for docid in row["docids"]:
            routing[docid] = row["name"]
    return {
        "schema": 1,
        "skills_root": "skills",
        "totals": {
            "skills": len(rows),
            "patterns": sum(r["patterns"] for r in rows),
            "reference_units": sum(r["reference_units"] for r in rows),
            "documents": sum(r["documents"] for r in rows),
        },
        "docid_to_skill": dict(sorted(routing.items())),
        "skills": rows,
    }


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(prog="skill_index")
    ap.add_argument("--check", action="store_true",
                    help="fail if the index is out of date")
    ap.add_argument("--json", action="store_true", help="print index.json only")
    args = ap.parse_args()

    rows = collect()
    cross = cross_references(rows)
    readme = render(rows)
    cross_doc = render_cross(rows, cross)
    body = payload(rows)
    body["cross_skill"] = cross
    data = json.dumps(body, indent=2) + "\n"

    readme_path = SKILLS_ROOT / "README.md"
    json_path = SKILLS_ROOT / "index.json"
    cross_path = SKILLS_ROOT / "CROSS-REFERENCES.md"
    connect_doc = render_connect(rows)
    connect_path = SKILLS_ROOT / "CONNECT.md"

    if args.check:
        stale = []
        for path, content in ((readme_path, readme), (json_path, data),
                              (cross_path, cross_doc), (connect_path, connect_doc)):
            if not path.exists() or path.read_text("utf-8") != content:
                stale.append(path.name)
        if stale:
            print(f"Stale skill index: {', '.join(stale)}. "
                  f"Run: python skill-maker/src/skillmaker/skill_index.py", file=sys.stderr)
            return 1
        print("Skill index is up to date.")
        return 0

    if args.json:
        print(data, end="")
        return 0

    SKILLS_ROOT.mkdir(parents=True, exist_ok=True)
    write_text_lf(readme_path, readme)
    write_text_lf(json_path, data)
    write_text_lf(cross_path, cross_doc)
    if connect_doc:
        write_text_lf(connect_path, connect_doc)

    missing = [r["name"] for r in rows if not r["built"]]
    if missing:
        print(f"Warning: no manifest for {', '.join(missing)} "
              f"(not built yet)", file=sys.stderr)
    links = sum(len(v) for v in cross.values())
    print(f"Wrote skills/README.md, index.json, CROSS-REFERENCES.md"
          + (", CONNECT.md" if connect_doc else "")
          + f": {len(rows)} skills, "
          f"{sum(r['patterns'] for r in rows)} patterns, "
          f"{links} cross-skill references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
