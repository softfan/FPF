#!/usr/bin/env python3
"""
test_build_generic.py -- tests for building skills from non-Library frameworks.

``fpf_frameworks.py plan`` says what a decomposition would produce.
``build_generic.py`` produces it.  These tests check that the second agrees
with the first, for the kinds the Library does not publish:

* an ADR set (``## ADR-0007 - Title``),
* a clause-numbered standard (``## 4.3.2 Title``),
* an Alexander-style pattern language (``## 12. Name``),
* plain Markdown with no identifiers at all.

Everything is built into a temporary directory, so the repository's ``skills/``
tree is never touched.

Usage from repo root::

    python skill-maker/tests/test_build_generic.py
    python skill-maker/tests/test_build_generic.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

_TESTS_DIR = Path(__file__).resolve().parent
_MAKER_DIR = _TESTS_DIR.parent                 # skill-maker/
_PKG_PARENT = _MAKER_DIR / "src"
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))
_SCRIPT_DIR = _PKG_PARENT / "skillmaker"        # the package: entry points, templates
_REPO_ROOT = _MAKER_DIR.parent                  # repository root
BUILDER = _SCRIPT_DIR / "build_generic.py"

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()


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


ADR = """# Payments service decisions

Architecture decisions for the payments service.

## ADR-0001 - Use an outbox table

Status: accepted. We write domain events to an outbox in the same transaction.

## ADR-0002 - Choose PostgreSQL

Status: accepted. The outbox needs transactional guarantees.

## ADR-0003 - Reject synchronous fan-out

Status: rejected. It couples availability to every consumer.
"""

STANDARD = """# Architecture description standard

## 1 Scope

This standard specifies requirements.

## 4.3.2 Architecture rationale

The rationale shall identify the decisions.

## 4.3.3 Conformance

An implementation shall demonstrate each requirement.
"""

PATTERNS = """# A small pattern language

## 1. THE GATE

Context: a boundary between two worlds.

Therefore: place a gate.

## 2. THE BENCH

Context: a place to pause.

Therefore: put a bench there.
"""

PLAIN = """# Release notes

## What changed

Everything.

## How to upgrade

Carefully.
"""


def run(*args: str) -> subprocess.CompletedProcess:
    # Explicit UTF-8: the builder writes UTF-8 and the Windows locale codec
    # cannot decode it.
    return subprocess.run([sys.executable, str(BUILDER), *args],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          cwd=str(_REPO_ROOT))


def _unit_files(directory: Path) -> List[str]:
    """Unit files only: the framework's own index.md is not a unit."""
    return sorted(p.name for p in directory.glob("*.md") if p.name != "index.md")


def write(tmp: Path, name: str, text: str) -> Path:
    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    return path


def build(tmp: Path, source: Path, skill: str,
          out: Path) -> subprocess.CompletedProcess:
    return run(str(source), "--skill", skill, "--output", str(out))


# ---------------------------------------------------------------------------

def test_adr(t: TestRunner, tmp: Path) -> None:
    print("\n[1] Architecture decision records")
    src = write(tmp, "docs/adr/adr-0001.md", ADR)
    out = tmp / "out-adr"

    plan = run(str(src), "--skill", "payments-adr", "--dry-run")
    t.check("dry-run exits 0", plan.returncode == 0, plan.stderr[-300:])
    t.check("dry-run names the kind", "ADR" in plan.stdout, plan.stdout[:200])
    t.check("dry-run writes nothing", not out.exists())

    r = build(tmp, src, "payments-adr", out)
    t.check("build exits 0", r.returncode == 0, r.stderr[-400:])
    t.check("SKILL.md written", (out / "SKILL.md").exists())
    t.check("README.md written", (out / "README.md").exists())

    units = _unit_files(out / "reference" / "payments-adr")
    t.equal("one file per decision", units,
            ["ADR-0001.md", "ADR-0002.md", "ADR-0003.md"])

    index = (out / "reference" / "pattern-index.md").read_text("utf-8")
    t.check("ID index lists every decision",
            all(f"ADR-000{i}" in index for i in (1, 2, 3)), index[:400])
    t.check("ID index names the file",
            "reference/payments-adr/ADR-0001.md" in index, index[:400])
    t.check("index explains there are no patterns", "no patterns" in index)

    skill_md = (out / "SKILL.md").read_text("utf-8")
    t.check("SKILL.md states the kind", "Architecture Decision Record" in skill_md)
    t.check("SKILL.md counts the units", "3 addressable units" in skill_md,
            skill_md[:400])
    t.check("no placeholder survives", "{{" not in skill_md, skill_md[:200])


def test_standard(t: TestRunner, tmp: Path) -> None:
    print("\n[2] Clause-numbered standard")
    src = write(tmp, "standard/iso-42010.md", STANDARD)
    out = tmp / "out-standard"
    r = build(tmp, src, "arch-standard", out)
    t.check("build exits 0", r.returncode == 0, r.stderr[-400:])

    units = _unit_files(out / "reference" / "arch-standard")
    t.equal("one file per clause", units, ["1.md", "4.3.2.md", "4.3.3.md"])

    clause = (out / "reference" / "arch-standard" / "4.3.2.md").read_text("utf-8")
    t.check("clause keeps its heading", "## 4.3.2 Architecture rationale" in clause,
            clause[:120])
    t.check("clause keeps its body", "shall identify the decisions" in clause)


def test_pattern_language(t: TestRunner, tmp: Path) -> None:
    print("\n[3] Numbered pattern language")
    src = write(tmp, "book/patterns/01.md", PATTERNS)
    out = tmp / "out-patterns"
    r = build(tmp, src, "small-language", out)
    t.check("build exits 0", r.returncode == 0, r.stderr[-400:])

    units = _unit_files(out / "reference" / "small-language")
    t.equal("file names carry the pattern name", units,
            ["1_the_gate.md", "2_the_bench.md"])


def test_generic(t: TestRunner, tmp: Path) -> None:
    print("\n[4] Plain Markdown ships whole")
    src = write(tmp, "notes/release.md", PLAIN)
    out = tmp / "out-notes"
    r = build(tmp, src, "release-notes", out)
    t.check("build exits 0", r.returncode == 0, r.stderr[-400:])

    t.check("document copied whole",
            (out / "reference" / "docs" / "release-notes.md").exists())
    t.check("no unit directory invented",
            not (out / "reference" / "release-notes").exists())
    skill_md = (out / "SKILL.md").read_text("utf-8")
    t.check("SKILL.md says it ships in full", "shipped in full" in skill_md,
            skill_md[:300])
    t.check("SKILL.md points at docs/", "reference/docs" in skill_md, skill_md[:600])


def test_behaviour(t: TestRunner, tmp: Path) -> None:
    print("\n[5] Idempotency, overrides and errors")
    src = write(tmp, "docs/adr/adr-0001.md", ADR)
    out = tmp / "out-idem"

    build(tmp, src, "payments-adr", out)
    first = sorted(p.name for p in out.rglob("*") if p.is_file())

    r = build(tmp, src, "payments-adr", out)
    t.check("second build exits 0", r.returncode == 0, r.stderr[-300:])
    t.check("second build writes nothing", "Written: 0" in r.stdout, r.stdout[-300:])
    second = sorted(p.name for p in out.rglob("*") if p.is_file())
    t.equal("file set is stable", second, first)

    manifest = json.loads((out / ".payments-adr_manifest.json").read_text("utf-8"))
    t.equal("manifest lists every unit", sum(1 for e in manifest if e["kind"] == "unit"), 3)
    t.check("manifest preserves source order",
            [e["id"] for e in manifest if e["kind"] == "unit"]
            == ["ADR-0001", "ADR-0002", "ADR-0003"])

    forced = tmp / "out-forced"
    r = run(str(src), "--skill", "forced", "--profile", "generic",
            "--output", str(forced))
    t.check("--profile overrides detection", r.returncode == 0, r.stderr[-300:])
    t.check("forced profile changes the output",
            (forced / "reference" / "docs" / "forced.md").exists(),
            str(sorted(p.name for p in forced.rglob("*"))))

    r = run(str(tmp / "missing.md"), "--skill", "x", "--output", str(tmp / "out-x"))
    t.check("missing source is an error", r.returncode == 1, str(r.returncode))

    r = run(str(src), "--skill", "x", "--profile", "nope",
            "--output", str(tmp / "out-y"))
    t.check("unknown profile is an error", r.returncode == 1, str(r.returncode))


def test_plan_matches_build(t: TestRunner, tmp: Path) -> None:
    print("\n[6] The plan matches what is built")
    src = write(tmp, "docs/adr/adr-0001.md", ADR)
    out = tmp / "out-plan"

    plan = run(str(src), "--skill", "payments-adr", "--dry-run")
    planned = {line.strip() for line in plan.stdout.splitlines()
               if line.strip().startswith("payments-adr/")}

    build(tmp, src, "payments-adr", out)
    # as_posix(), not str(): the plan prints forward slashes, and str() on a
    # WindowsPath renders backslashes -- so every planned file would look
    # missing on Windows while the build is byte-identical.
    built = {"payments-adr/" + p.relative_to(out).as_posix() for p in out.rglob("*")
             if p.is_file() and not p.name.startswith(".")}

    # Directories are planned but not files; compare only file paths.
    planned_files = {p for p in planned if "." in p.rsplit("/", 1)[-1]}
    missing = planned_files - built
    t.check("every planned file exists", not missing, str(sorted(missing)[:5]))


# ---------------------------------------------------------------------------

def test_genre_shapes(t: TestRunner, tmp: Path) -> None:
    """A genre decides what the skill *contains*, not only how it reads.

    ``apply`` ships a roles pipeline; ``lookup`` ships none.  A hand-written
    structure block in the template used to describe a ``roles/`` directory
    that only some genres have, so the README is checked against the disk.
    """
    print("\n[7] Genre shapes the skill, not just its wording")
    src = write(tmp, "docs/adr/adr-0001.md", ADR)

    apply_out = tmp / "out-apply"
    r = subprocess.run([sys.executable, str(BUILDER), str(src),
                        "--skill", "payments-adr", "--genre", "apply",
                        "--output", str(apply_out)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(_REPO_ROOT))
    t.check("apply build exits 0", r.returncode == 0, r.stderr[-400:])
    t.check("apply ships roles/", (apply_out / "roles").is_dir())
    for role in ("classifier.md", "retriever.md", "reasoner.md", "reviewer.md"):
        t.check(f"apply ships roles/{role}", (apply_out / "roles" / role).exists())

    readme = (apply_out / "README.md").read_text("utf-8")
    t.check("the README tree shows roles/", "roles/" in readme, readme[:600])
    t.check("no placeholder survives in the apply README",
            "{{" not in readme, readme[:300])

    for name in ("SKILL.md", "README.md", "boot.md"):
        path = apply_out / name
        t.check(f"apply: no placeholder in {name}",
                path.exists() and "{{" not in path.read_text("utf-8"))

    lookup_out = tmp / "out-lookup"
    r = subprocess.run([sys.executable, str(BUILDER), str(src),
                        "--skill", "payments-adr", "--genre", "lookup",
                        "--output", str(lookup_out)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(_REPO_ROOT))
    t.check("lookup build exits 0", r.returncode == 0, r.stderr[-400:])
    t.check("lookup ships no roles/", not (lookup_out / "roles").exists())
    lookup_readme = (lookup_out / "README.md").read_text("utf-8")
    t.check("the lookup README tree omits roles/", "roles/" not in lookup_readme,
            lookup_readme[:600])

def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    print("=" * 60)
    print("Generic Skill Builder -- Tests")
    print("=" * 60)

    t = TestRunner(verbose=verbose)
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_adr(t, tmp)
        test_standard(t, tmp)
        test_pattern_language(t, tmp)
        test_generic(t, tmp)
        test_behaviour(t, tmp)
        test_plan_matches_build(t, tmp)
        test_genre_shapes(t, tmp)
    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
