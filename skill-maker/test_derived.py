#!/usr/bin/env python3
"""
test_derived.py -- tests for the retrieval layer.

Four modules are covered, each answering one question the source cannot:

``sections``  where the working sections of a unit are, and what they cost
``derive``    routes, entries and glossary, derived from the source
``genre``     what a skill is for, which decides its shape and its roles
``skill_root`` how a copied skill finds itself

The tests check the claims those modules make, not just that they run: that
section offsets account for every byte, that a route is a valid order, that a
glossary line is quoted rather than invented, and that a moved skill still
resolves.

Usage from repo root::

    python skill-maker/test_derived.py
    python skill-maker/test_derived.py -v
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

import derive  # noqa: E402
import sections  # noqa: E402
import skill_root  # noqa: E402
from frameworks import genre as genre_mod  # noqa: E402

SKILLS = _REPO_ROOT / "skills"


class TestRunner:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.passed: List[str] = []
        self.failed: List[Tuple[str, str]] = []

    def check(self, name: str, condition: bool, detail: str = ""):
        if condition:
            self.passed.append(name)
            if self.verbose:
                print(f"  \u2713 {name}")
        else:
            self.failed.append((name, detail))
            print(f"  \u2717 {name}: {detail}")

    def equal(self, name: str, actual, expected):
        self.check(name, actual == expected, f"expected {expected!r}, got {actual!r}")

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed)
        print(f"\n{'=' * 60}")
        print(f"Results: {len(self.passed)} passed, {len(self.failed)} failed / {total} total")
        if self.failed:
            print("\nFailed tests:")
            for name, detail in self.failed:
                print(f"  \u2717 {name}: {detail}")
        print("=" * 60)
        return 0 if not self.failed else 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE = """## DEMO.7 - A Sample Unit

### DEMO.7:1 - Problem Frame

Why this applies.

### DEMO.7:2 - Problem

What goes wrong.

### DEMO.7:3 - Forces

What pulls apart.

### DEMO.7:4 - Solution

#### DEMO.7:4.1 - First move

Do the first thing.

### DEMO.7:5 - Archetypal Grounding (Worked Cases)

A long case that nobody needs on the first read.

### DEMO.7:6 - Conformance Checklist

- [ ] The result holds.

### DEMO.7:7 - Rationale

Why the design is this way.

### DEMO.7:End
"""


def unit_files(limit: int = 40) -> List[Tuple[str, str, str]]:
    """(skill, unit id, text) for a sample of built units."""
    out: List[Tuple[str, str, str]] = []
    if not SKILLS.exists():
        return out
    for manifest in sorted(SKILLS.glob("*/. *_manifest.json".replace(" ", ""))):
        skill = manifest.parent.name
        try:
            entries = json.loads(manifest.read_text("utf-8"))
        except Exception:
            continue
        for entry in entries:
            if entry.get("kind") != "unit":
                continue
            path = (SKILLS / skill / "reference" / entry["framework"]
                    / entry["key"])
            if path.exists():
                out.append((skill, entry["id"], path.read_text("utf-8")))
                if len(out) >= limit:
                    return out
    return out


# ---------------------------------------------------------------------------
# 1. Sections
# ---------------------------------------------------------------------------

def test_sections(t: TestRunner) -> None:
    print("\n[1] Section map")
    info = sections.analyse("DEMO.7", SAMPLE)
    t.equal("finds every section", len(info.sections), 7)
    t.equal("numbers are read", [s.n for s in info.sections],
            ["1", "2", "3", "4", "5", "6", "7"])
    t.equal("end marker is not a section",
            [s.anchor for s in info.sections].count("end"), 0)

    t.equal("problem frame is contract", info.sections[0].tier, "contract")
    t.equal("worked cases are source", info.sections[4].tier, "source")
    t.equal("rationale is source", info.sections[6].tier, "source")
    t.equal("checklist is contract", info.sections[5].tier, "contract")

    t.check("bytes account for the file",
            sum(s.bytes for s in info.sections) <= info.bytes,
            f"{sum(s.bytes for s in info.sections)} > {info.bytes}")
    t.check("sections do not overlap",
            all(info.sections[i].end_line <= info.sections[i + 1].line
                for i in range(len(info.sections) - 1)))
    t.check("line ranges are contiguous",
            all(info.sections[i].end_line == info.sections[i + 1].line
                for i in range(len(info.sections) - 1)))

    contract = sections.read_tier("DEMO.7", SAMPLE, "contract")
    t.check("contract keeps the solution", "First move" in contract)
    t.check("contract keeps the checklist", "The result holds" in contract)
    t.check("contract drops the worked case",
            "nobody needs on the first read" not in contract)
    t.check("contract is smaller than the whole",
            len(contract) < len(SAMPLE), f"{len(contract)} vs {len(SAMPLE)}")
    t.check("source tier is the complement",
            "nobody needs on the first read" in sections.read_tier(
                "DEMO.7", SAMPLE, "source"))
    t.equal("tier=all returns everything",
            sections.read_tier("DEMO.7", SAMPLE, "all"), SAMPLE)

    one = sections.read_section("DEMO.7", SAMPLE, "solution")
    t.check("one section by anchor", one is not None and "First move" in one,
            str(one)[:80])
    t.check("section includes its subsections",
            one is not None and "DEMO.7:4.1" in one)
    t.check("unknown section is None",
            sections.read_section("DEMO.7", SAMPLE, "nope") is None)

    t.equal("anchor normalisation",
            sections.anchor_for("Conformance Checklist (normative)"),
            "conformance-checklist-normative")
    t.equal("tier prefix matching",
            sections.tier_for("Conformance Checklist (normative)"), "contract")
    t.equal("unknown title is source", sections.tier_for("SoTA-Echoing"), "source")


def test_sections_real(t: TestRunner) -> None:
    print("\n[2] Section map on built units")
    files = unit_files(40)
    if not files:
        t.check("skills built", False, "run build.sh first")
        return

    bad_overflow = []
    bad_overlap = []
    no_contract = []
    patterns = 0
    for _skill, uid, text in files:
        info = sections.analyse(uid, text)
        if sum(s.bytes for s in info.sections) > info.bytes:
            bad_overflow.append(uid)
        for i in range(len(info.sections) - 1):
            if info.sections[i].end_line > info.sections[i + 1].line:
                bad_overlap.append(uid)
        # A reference unit legitimately has no problem-frame sections; only a
        # pattern is expected to carry the working tier.
        if ":" not in uid:
            patterns += 1
            if not info.of_tier("contract"):
                no_contract.append(uid)

    t.check("no section overflows its file", not bad_overflow, str(bad_overflow[:5]))
    t.check("no overlapping sections", not bad_overlap, str(bad_overlap[:5]))
    t.check("patterns carry working sections",
            patterns > 0 and not no_contract, str(no_contract[:5]))

    # The saving that motivates the whole layer.
    shares = []
    for _skill, uid, text in files:
        info = sections.analyse(uid, text)
        if info.bytes and info.sections:
            shares.append(info.tier_bytes("contract") / info.bytes)
    if shares:
        mean = sum(shares) / len(shares)
        t.check("contract is a real saving", mean < 0.9, f"mean share {mean:.0%}")
        t.check("contract is not degenerate", mean > 0.1, f"mean share {mean:.0%}")


# ---------------------------------------------------------------------------
# 3. Derived artefacts
# ---------------------------------------------------------------------------

class FakeUnit:
    def __init__(self, uid: str, title: str, role: str = "pattern"):
        self.id = uid
        self.title = title
        self.role = role


class FakeTOC:
    def __init__(self, queries: str):
        self.search_queries = queries


def test_derive(t: TestRunner) -> None:
    print("\n[3] Derived artefacts")
    units = [FakeUnit("D.1", "First"), FakeUnit("D.2", "Second"),
             FakeUnit("D.3", "Third")]
    deps = {"D.1": "", "D.2": "**Builds on:** D.1.", "D.3": "Builds on: D.2, D.1"}
    toc = {u.id: FakeTOC(f'"What does {u.title.lower()} need?"') for u in units}
    infos = {u.id: sections.analyse(u.id, f"## {u.id} - {u.title}\n\nBody.\n")
             for u in units}

    data = derive.routes(units, deps, toc, infos)
    t.check("routes are marked derived", data["derived"] is True)
    by_id = {r["id"]: r for r in data["routes"]}
    t.equal("only units with dependencies get a route",
            sorted(by_id), ["D.2", "D.3"])
    t.equal("a direct prerequisite is recorded", by_id["D.2"]["direct"], ["D.1"])
    t.check("the chain ends with the unit itself",
            by_id["D.3"]["chain"][-1] == "D.3", str(by_id["D.3"]["chain"]))
    t.check("prerequisites come before dependants",
            by_id["D.3"]["chain"].index("D.1") < by_id["D.3"]["chain"].index("D.2"),
            str(by_id["D.3"]["chain"]))
    t.check("the situation is the unit's own question",
            by_id["D.2"]["situation"].endswith("?"), by_id["D.2"]["situation"])

    # A cycle must not hang or duplicate.
    cyc = derive.routes([FakeUnit("C.1", "One"), FakeUnit("C.2", "Two")],
                        {"C.1": "C.2", "C.2": "C.1"},
                        {u: FakeTOC('"What?"') for u in ("C.1", "C.2")}, {})
    chains = [r["chain"] for r in cyc["routes"]]
    t.check("a cycle terminates", all(len(c) <= 2 for c in chains), str(chains))
    t.check("a cycle does not repeat a unit",
            all(len(c) == len(set(c)) for c in chains), str(chains))

    curated = {"routes": [{"id": "D.2", "situation": "Hand written."}]}
    merged = derive.merge_curated(data, curated)
    hand = next(r for r in merged["routes"] if r["id"] == "D.2")
    t.equal("a curated route wins", hand["situation"], "Hand written.")
    t.check("a curated route is marked", hand["derived"] is False)
    t.equal("curated count is reported", merged["curated"], 1)


def test_entries_glossary(t: TestRunner) -> None:
    print("\n[4] Entries and glossary")
    units = [FakeUnit("D.1", "First"), FakeUnit("D.2", "Second")]
    toc = {"D.1": FakeTOC('"Which formulations change what to investigate?"'),
           "D.2": FakeTOC("What must the inquiry include? What reopens the cut?")}
    data = derive.entries(units, toc, {})
    t.check("entries are marked derived", data["derived"] is True)
    situations = [e["situation"] for e in data["entries"]]
    t.check("quoted queries are read", any("formulations" in s for s in situations),
            str(situations))
    t.check("plain queries are split on the question mark",
            any("inquiry include" in s for s in situations), str(situations))
    t.check("every entry names a starting unit",
            all(e["start_with"] for e in data["entries"]))

    bodies = {
        "D.1": "## D.1 - First\n\nUse this pattern when one wording has become "
               "naturalized even though other accounts would change the result.\n",
        "D.2": "## D.2 - Second\n\nThis pattern applies when the boundary has "
               "to be reopened.\n",
    }
    rows = derive.glossary(units, bodies)
    t.equal("one glossary row per unit", len(rows), 2)
    t.check("the lead-in is stripped",
            rows[0]["meaning"].startswith("One wording"),
            rows[0]["meaning"][:60])
    t.check("a meaning is quoted, not invented",
            "naturalized" in rows[0]["meaning"], rows[0]["meaning"][:80])
    t.check("every row names its unit",
            all(r["id"].startswith("D.") for r in rows))

    text = derive.render_glossary(rows, "Demo")
    t.check("glossary renders a table", "| Term |" in text and "`D.1`" in text)
    t.check("a pipe in a meaning is escaped",
            "\\|" in derive.render_glossary(
                [{"term": "a|b", "meaning": "c|d", "id": "X.1"}], "T"),
            "escape missing")


# ---------------------------------------------------------------------------
# 5. Genres
# ---------------------------------------------------------------------------

def test_genres(t: TestRunner) -> None:
    print("\n[5] Genres")
    t.equal("four genres", len(list(genre_mod.Genre)), 4)
    lookup = genre_mod.by_value("lookup")
    t.equal("lookup ships no roles", lookup.roles, ())
    apply_spec = genre_mod.by_value("apply")
    t.equal("apply ships a four-step pipeline", len(apply_spec.roles), 4)
    t.check("apply roles are in pipeline order",
            apply_spec.roles == ("classifier", "retriever", "reasoner", "reviewer"),
            str(apply_spec.roles))
    setup = genre_mod.by_value("setup")
    t.check("setup ships installer and validator",
            set(setup.roles) == {"installer", "validator"}, str(setup.roles))
    t.check("maintain ships sync", "sync" in genre_mod.by_value("maintain").roles)

    try:
        genre_mod.by_value("nope")
        t.check("unknown genre raises", False, "no exception")
    except KeyError as exc:
        t.check("unknown genre raises", "known genres" in str(exc), str(exc))

    for spec in genre_mod.GENRES.values():
        partial = _SCRIPT_DIR / "templates" / "genres" / spec.partial
        t.check(f"genre {spec.genre.value} has a partial", partial.exists(),
                str(partial))
        for role in spec.roles:
            t.check(f"role {role} has a template",
                    (_SCRIPT_DIR / "templates" / "roles" / f"{role}.md").exists())

    # Every role a genre names must have a question for the roles README.
    import split_spec
    for spec in genre_mod.GENRES.values():
        for role in spec.roles:
            t.check(f"role {role} has a one-line question",
                    role in split_spec.ROLE_QUESTIONS, role)


# ---------------------------------------------------------------------------
# 6. Movable skills
# ---------------------------------------------------------------------------

def test_skill_root(t: TestRunner) -> None:
    print("\n[6] Skill root resolution")
    built = skill_root.discover(SKILLS) if SKILLS.exists() else []
    t.check("every built skill carries a marker", len(built) >= 15, str(len(built)))

    if not built:
        return
    sample = built[0]
    marker = skill_root.read_marker(sample)
    t.check("the marker parses", isinstance(marker, dict), str(marker))
    t.check("the marker names the skill", bool(marker.get("name")))
    t.check("the marker records the kind", bool(marker.get("kind")))
    t.check("the marker records the genre", bool(marker.get("genre")))

    deep = sample / "reference"
    t.equal("a path inside the skill resolves to its root",
            skill_root.find_root(deep), sample)

    # A copied skill must still resolve, which is the point of the marker.
    with tempfile.TemporaryDirectory() as raw:
        copy = Path(raw) / "moved"
        shutil.copytree(sample, copy)
        t.equal("a copied skill resolves from its own root",
                skill_root.find_root(copy), copy)
        t.equal("a copied skill resolves from a nested path",
                skill_root.find_root(copy / "reference"), copy)

    t.check("a directory without a marker returns None",
            skill_root.find_root(Path(tempfile.gettempdir())) is None)
    t.equal("resolve falls back to the given path",
            skill_root.resolve(Path(tempfile.gettempdir())),
            Path(tempfile.gettempdir()))


# ---------------------------------------------------------------------------
# 7. What the build actually produced
# ---------------------------------------------------------------------------

def test_built_artefacts(t: TestRunner) -> None:
    print("\n[7] Built artefacts")
    if not SKILLS.exists():
        t.check("skills built", False, "run build.sh first")
        return

    skills = skill_root.discover(SKILLS)
    t.check("fifteen skills", len(skills) == 15, str(len(skills)))

    for skill in skills:
        name = skill.name
        t.check(f"{name}: boot.md", (skill / "boot.md").exists())
        ref = skill / "reference"
        t.check(f"{name}: sections.json", (ref / "sections.json").exists())
        t.check(f"{name}: routes.json", (ref / "routes.json").exists())
        t.check(f"{name}: entries.json", (ref / "entries.json").exists())

    # sections.json must describe the files that are actually there.
    mismatches = []
    for skill in skills:
        path = skill / "reference" / "sections.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text("utf-8"))["unit"]
        for uid, info in list(data.items())[:20]:
            target = None
            for candidate in (skill / "reference").rglob(info["file"]):
                target = candidate
                break
            if target is None:
                mismatches.append(f"{skill.name}:{uid}")
            elif target.stat().st_size != info["bytes"]:
                mismatches.append(f"{skill.name}:{uid} size")
    t.check("sections.json matches the files", not mismatches, str(mismatches[:5]))

    # routes.json must reference real units only.
    dangling = []
    for skill in skills:
        path = skill / "reference" / "routes.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text("utf-8"))
        manifest = json.loads(
            (skill / f".{skill.name}_manifest.json").read_text("utf-8"))
        known = {e["id"] for e in manifest if e.get("kind") == "unit"}
        for route in data.get("routes", [])[:40]:
            for uid in route.get("chain", []):
                if uid not in known:
                    dangling.append(f"{skill.name}:{uid}")
    t.check("routes reference existing units", not dangling, str(dangling[:5]))

    # A glossary line must not be empty, and must name its unit.
    empty = []
    for skill in skills:
        path = skill / "reference" / "glossary.md"
        if not path.exists():
            continue
        for line in path.read_text("utf-8").splitlines():
            if line.startswith("| ") and not line.startswith("| :"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if cells and cells[0].lower() in ("term", "id", "unit"):
                    continue
                if len(cells) >= 3 and (not cells[1] or not cells[2].startswith("`")):
                    empty.append(f"{skill.name}:{cells[0][:20]}")
    t.check("glossary rows are complete", not empty, str(empty[:5]))


# ---------------------------------------------------------------------------

def test_engine_digest(t: TestRunner) -> None:
    """The build stamp must react to every input, not only to code.

    A template or a profile that the digest ignores is a stale-output bug: the
    build says "up to date" while the next build would produce something else.

    The probe round-trips three *tracked* files, so it moves bytes, not text.
    ``read_text`` normalises CRLF to LF and ``write_text`` translates LF back to
    ``os.linesep``: on Windows that pair silently rewrites an LF file as CRLF, so
    the "restore" changed the very bytes the digest hashes and every later
    assertion in the suite inherited a corrupted file.  Bytes in, bytes out.
    """
    print("\n[8] The build stamp covers every input")
    from skill_config import FPF_CONFIG
    from split_spec import _engine_digest

    before = _engine_digest(FPF_CONFIG)
    t.check("digest is stable", _engine_digest(FPF_CONFIG) == before)

    for rel in ("templates/genres/lookup.md",
                "templates/roles/reviewer.md",
                "frameworks/profiles/dpf_framework.py"):
        path = _SCRIPT_DIR / rel
        if not path.exists():
            t.check(f"{rel} exists", False)
            continue
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"\n<!-- digest probe -->\n")
            changed = _engine_digest(FPF_CONFIG)
        finally:
            path.write_bytes(original)
        t.check(f"editing {rel} invalidates the stamp", changed != before,
                "digest unchanged")
        t.check(f"restoring {rel} restores the stamp",
                _engine_digest(FPF_CONFIG) == before)
        t.check(f"the probe left {rel} byte-identical",
                path.read_bytes() == original)

# ---------------------------------------------------------------------------

def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    print("=" * 60)
    print("Derived Retrieval Layer -- Tests")
    print("=" * 60)

    t = TestRunner(verbose=verbose)
    test_sections(t)
    test_sections_real(t)
    test_derive(t)
    test_entries_glossary(t)
    test_genres(t)
    test_skill_root(t)
    test_built_artefacts(t)
    test_engine_digest(t)
    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
