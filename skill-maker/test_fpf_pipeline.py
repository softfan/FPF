#!/usr/bin/env python3
"""
test_fpf_pipeline.py — End-to-end tests for the FPF skill pipeline.

Verifies: split -> structure -> audit -> rebuild -> tools -> idempotency.

The FPF skill ships four publications:

    FPF-Spec.md                Core patterns + embedded Architectural Reference
    USING-FPF.md               Library working instruction
    FPF-LIBRARY-REFERENCE.md   Library Architectural Reference
    Readme.md                  Library landing page

Usage from repo root:
    python skill-maker/test_fpf_pipeline.py
    python skill-maker/test_fpf_pipeline.py -v

Exit codes: 0 = all passed, 1 = failures found.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

from _fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

SPEC_PATH = _REPO_ROOT / "FPF-Spec.md"
USING_PATH = _REPO_ROOT / "USING-FPF.md"
LIBRARY_PATH = _REPO_ROOT / "FPF-LIBRARY-REFERENCE.md"
README_PATH = _REPO_ROOT / "Readme.md"
SKILL_DIR = _REPO_ROOT / "skills" / "fpf"

EXPECTED_PATTERNS = 397


class TestRunner:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.passed: List[str] = []
        self.failed: List[Tuple[str, str]] = []
        self.skipped: List[Tuple[str, str]] = []

    def check(self, name: str, condition: bool, detail: str = ""):
        if condition:
            self.passed.append(name)
            if self.verbose:
                print(f"  \u2713 {name}")
        else:
            self.failed.append((name, detail))
            print(f"  \u2717 {name}: {detail}")

    def skip(self, name: str, reason: str):
        self.skipped.append((name, reason))
        if self.verbose:
            print(f"  \u25cb {name}: SKIP -- {reason}")

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed) + len(self.skipped)
        print(f"\n{'=' * 60}")
        print(f"Results: {len(self.passed)} passed, {len(self.failed)} failed, "
              f"{len(self.skipped)} skipped / {total} total")
        if self.failed:
            print("\nFailed tests:")
            for name, detail in self.failed:
                print(f"  \u2717 {name}: {detail}")
        print("=" * 60)
        return 0 if not self.failed else 1


def run_cmd(args: List[str], cwd: str = None) -> subprocess.CompletedProcess:
    # encoding is explicit: the child writes UTF-8 (it reconfigures its own
    # stdout), so decoding with the locale codec -- cp1251 on a Russian Windows,
    # cp437 on a default one -- fails on the first non-ASCII byte.
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          cwd=cwd or str(_REPO_ROOT))


def _err_detail(r: subprocess.CompletedProcess, max_len: int = 500) -> str:
    # A failed decode leaves stdout/stderr as None rather than raising here,
    # so the diagnostic itself must not be the thing that crashes.
    stdout = r.stdout or ""
    stderr = r.stderr or ""
    parts = []
    if r.returncode != 0:
        parts.append(f"exit={r.returncode}")
    if stderr.strip():
        parts.append(f"stderr: {stderr.strip()[:max_len]}")
    if not stdout.strip():
        parts.append("(empty stdout)")
    elif not parts:
        parts.append(f"stdout: {stdout.strip()[:max_len]}")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Test groups
# ---------------------------------------------------------------------------

def test_prerequisites(t: TestRunner):
    print("\n[Prerequisites]")
    t.check("FPF-Spec.md exists", SPEC_PATH.exists(), f"Expected at {SPEC_PATH}")
    t.check("FPF-Spec.md > 1MB",
            SPEC_PATH.exists() and SPEC_PATH.stat().st_size > 1_000_000,
            "File too small")
    for path, label in [(USING_PATH, "USING-FPF.md"),
                        (LIBRARY_PATH, "FPF-LIBRARY-REFERENCE.md"),
                        (README_PATH, "Readme.md")]:
        t.check(f"{label} exists", path.exists(), f"Expected at {path}")
    t.check("skill-maker/ scripts exist",
            all((_SCRIPT_DIR / f).exists() for f in
                ["split_fpf_spec.py", "split_spec.py", "skill_config.py",
                 "fpf_lookup.py", "fpf_update.py", "audit_fpf_patterns.py",
                 "_fpf_common.py"]),
            "Missing script files")


def test_split(t: TestRunner):
    print("\n[Split]")
    if not SPEC_PATH.exists():
        t.skip("split", "No FPF-Spec.md"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_fpf_spec.py"),
                 "split", "--source", str(SPEC_PATH), "--output", str(SKILL_DIR),
                 "--views"])
    t.check("split exit code 0", r.returncode == 0, _err_detail(r))
    m = re.search(r"(\d+) patterns", r.stdout)
    t.check(f"split reports {EXPECTED_PATTERNS} patterns",
            bool(m) and int(m.group(1)) == EXPECTED_PATTERNS,
            r.stdout.strip()[:200])


def test_structure(t: TestRunner):
    print("\n[Structure]")
    if not SKILL_DIR.exists():
        t.skip("structure", "skills/fpf/ not found"); return

    t.check("SKILL.md exists", (SKILL_DIR / "SKILL.md").exists())
    t.check("README.md exists", (SKILL_DIR / "README.md").exists())
    t.check(".fpf_manifest.json exists", (SKILL_DIR / ".fpf_manifest.json").exists())
    t.check(".fpf_hashes.json exists", (SKILL_DIR / ".fpf_hashes.json").exists())

    pdir = SKILL_DIR / "reference" / "fpf-patterns"
    t.check("fpf-patterns/ exists", pdir.exists())
    if pdir.exists():
        patterns = [f for f in pdir.glob("*.md") if f.name != "index.md"]
        t.check(f"{EXPECTED_PATTERNS} unit files",
                len(patterns) == EXPECTED_PATTERNS + 21,
                f"Found {len(patterns)}")
        t.check("index.md exists", (pdir / "index.md").exists())
        t.check("A.1.md exists", (pdir / "A.1.md").exists())
        t.check("no ':' in file names",
                not any(":" in f.name for f in patterns))

    ref = SKILL_DIR / "reference"
    t.check("reference/index.md", (ref / "index.md").exists())
    for idx in ("pattern-index.md", "keyword-index.md",
                "query-index.md", "reference-index.md"):
        t.check(f"reference/{idx}", (ref / idx).exists())

    for slug in ("using-fpf", "library-reference", "library-readme"):
        p = ref / "docs" / f"{slug}.md"
        t.check(f"docs/{slug}.md", p.exists())
        if p.exists():
            t.check(f"docs/{slug}.md non-trivial", p.stat().st_size > 2_000,
                    f"{p.stat().st_size} bytes")

    intros = list((ref / "intro").glob("*.md"))
    t.check("intro sections >= 10", len(intros) >= 10, f"Found {len(intros)}")
    t.check("intro/table_of_content.md",
            (ref / "intro" / "table_of_content.md").exists())
    t.check("intro/readme.md", (ref / "intro" / "readme.md").exists())

    scripts_dir = SKILL_DIR / "scripts"
    t.check("scripts/ exists", scripts_dir.exists())
    if scripts_dir.exists():
        for name in ("__init__.py", "fpf_lookup.py", "_fpf_common.py",
                     "split_spec.py", "skill_config.py", "fpf_update.py",
                     "split_fpf_spec.py", "audit_fpf_patterns.py"):
            t.check(f"scripts/{name}", (scripts_dir / name).exists())


def test_skill_md_quality(t: TestRunner):
    print("\n[SKILL.md quality]")
    skill_path = SKILL_DIR / "SKILL.md"
    if not skill_path.exists():
        t.skip("SKILL.md quality", "File not found"); return

    content = skill_path.read_text("utf-8")
    t.check("has YAML frontmatter", content.startswith("---"))
    t.check("frontmatter has name: fpf",
            bool(re.search(r"^name:\s*fpf", content, re.M)))
    t.check("frontmatter has description",
            bool(re.search(r"^description:", content, re.M)))
    t.check("has 'When to use' section", "when to use" in content.lower())
    t.check("has 'How to use' section", "how to use" in content.lower())
    t.check("has Core Terminology", "core terminology" in content.lower())
    t.check("has Canonical Reasoning",
            "canonical reasoning" in content.lower() or "b.5" in content.lower())
    t.check("has dependency resolution",
            "dependency" in content.lower() or "topological" in content.lower())
    t.check("has kernel patterns", "kernel pattern" in content.lower())
    t.check("has self-update reference",
            "fpf_update" in content.lower() or "self-update" in content.lower())
    t.check("points at the working instruction",
            "docs/using-fpf.md" in content)
    t.check("points at the Library reference",
            "docs/library-reference.md" in content)
    t.check("SKILL.md < 500 lines", len(content.splitlines()) < 500,
            f"Got {len(content.splitlines())} lines")
    t.check("no {{placeholders}} left", "{{" not in content,
            "Found unresolved placeholder in SKILL.md")


def test_manifest(t: TestRunner):
    print("\n[Manifest]")
    mpath = SKILL_DIR / ".fpf_manifest.json"
    if not mpath.exists():
        t.skip("manifest", "Not found"); return
    manifest = json.loads(mpath.read_text("utf-8"))
    t.check("manifest is list", isinstance(manifest, list))
    t.check("manifest not empty", len(manifest) > 0)
    if manifest:
        kinds = {e.get("kind") for e in manifest}
        t.check("has intro + unit + doc kinds",
                {"intro", "unit", "doc"} <= kinds, f"Found: {kinds}")
        roles = {e.get("role") for e in manifest if e.get("kind") == "unit"}
        t.check("has pattern + reference roles",
                {"pattern", "reference"} <= roles, f"Found: {roles}")
        missing = []
        for entry in manifest:
            if entry["kind"] == "doc":
                p = SKILL_DIR / "reference" / "docs" / entry["key"]
            elif entry["kind"] == "intro":
                p = SKILL_DIR / "reference" / "intro" / entry["key"]
            else:
                p = SKILL_DIR / "reference" / entry["framework"] / entry["key"]
            if not p.exists():
                missing.append(entry["key"])
        t.check("all manifest files exist", len(missing) == 0,
                f"Missing: {missing[:5]}")


def test_audit(t: TestRunner):
    print("\n[Audit]")
    if not SPEC_PATH.exists() or not SKILL_DIR.exists():
        t.skip("audit", "Missing prerequisites"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "audit_fpf_patterns.py"),
                 "--source", str(SPEC_PATH), "--skill-dir", str(SKILL_DIR), "--json"])
    t.check("audit exit code 0", r.returncode == 0, _err_detail(r))
    if r.returncode == 0 and r.stdout.strip():
        try:
            data = json.loads(r.stdout)
            t.check("audit healthy=true", data.get("healthy") is True)
            t.check("audit no missing", len(data.get("missing", [])) == 0,
                    f"Missing: {data.get('missing', [])[:5]}")
            gen = data.get("generated_count", 0)
            t.check(f"audit generated {EXPECTED_PATTERNS}",
                    gen == EXPECTED_PATTERNS, f"Got {gen}")
        except json.JSONDecodeError as e:
            t.check("audit JSON output", False, f"JSON parse error: {e}")


def test_rebuild(t: TestRunner):
    print("\n[Rebuild]")
    if not SPEC_PATH.exists() or not (SKILL_DIR / ".fpf_manifest.json").exists():
        t.skip("rebuild", "Missing prerequisites"); return

    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_fpf_spec.py"),
                     "rebuild", "--skill-dir", str(SKILL_DIR), "--output", str(tmp_path)])
        t.check("rebuild exit code 0", r.returncode == 0, _err_detail(r))
        if r.returncode == 0:
            orig = SPEC_PATH.read_bytes().replace(b"\r\n", b"\n")
            rebuilt = tmp_path.read_bytes().replace(b"\r\n", b"\n")
            t.check("rebuild size match (normalized)",
                    abs(len(orig) - len(rebuilt)) < 100,
                    f"orig={len(orig)}, rebuilt={len(rebuilt)}, "
                    f"delta={len(orig) - len(rebuilt)}")
            if orig != rebuilt:
                for i, (a, b) in enumerate(zip(orig, rebuilt)):
                    if a != b:
                        t.check("rebuild identical or trailing-newline only",
                                i >= len(orig) - 2,
                                f"First diff at byte {i}/{len(orig)}")
                        break
                else:
                    t.check("rebuild length diff <= 1",
                            abs(len(orig) - len(rebuilt)) <= 1)
    finally:
        tmp_path.unlink(missing_ok=True)


def _tool(t: TestRunner, *args) -> subprocess.CompletedProcess:
    return run_cmd([sys.executable, str(_SCRIPT_DIR / "fpf_lookup.py"),
                    "--skill-root", str(SKILL_DIR), *args])


def test_tools_search(t: TestRunner):
    print("\n[Tools: search]")
    if not SKILL_DIR.exists():
        t.skip("tools:search", "No skill dir"); return
    r = _tool(t, "search", "holon")
    t.check("search exit 0", r.returncode == 0, _err_detail(r))
    t.check("search finds results",
            "A.1" in r.stdout or "holon" in r.stdout.lower(), _err_detail(r))


def test_tools_read(t: TestRunner):
    print("\n[Tools: read]")
    if not SKILL_DIR.exists():
        t.skip("tools:read", "No skill dir"); return
    r = _tool(t, "read", "A.1")
    t.check("read A.1 exit 0", r.returncode == 0, _err_detail(r))
    t.check("read A.1 has content", len(r.stdout) > 100,
            f"Got {len(r.stdout)} bytes | {_err_detail(r)}")

    r2 = _tool(t, "read", "A.999")
    t.check("read A.999 suggests alternatives",
            "not found" in r2.stdout.lower() and "available" in r2.stdout.lower(),
            _err_detail(r2))

    r3 = _tool(t, "read", "FPF.Reference:1")
    t.check("read reference unit by ID", len(r3.stdout) > 100, _err_detail(r3))


def test_tools_list(t: TestRunner):
    print("\n[Tools: list]")
    if not SKILL_DIR.exists():
        t.skip("tools:list", "No skill dir"); return
    r = _tool(t, "list", "A")
    t.check("list A exit 0", r.returncode == 0, _err_detail(r))
    t.check("list A has patterns", "A.1" in r.stdout, _err_detail(r))


def test_tools_intro(t: TestRunner):
    print("\n[Tools: intro]")
    if not SKILL_DIR.exists():
        t.skip("tools:intro", "No skill dir"); return
    r = _tool(t, "intro", "table")
    t.check("intro 'table' exit 0", r.returncode == 0, _err_detail(r))
    t.check("intro finds table_of_content",
            "table" in r.stdout.lower() or "content" in r.stdout.lower(),
            _err_detail(r))

    r2 = _tool(t, "intro", "xyznonexistent")
    t.check("intro miss lists available",
            "not found" in r2.stdout.lower() or "available" in r2.stdout.lower(),
            _err_detail(r2))


def test_tools_docs(t: TestRunner):
    print("\n[Tools: docs]")
    if not SKILL_DIR.exists():
        t.skip("tools:docs", "No skill dir"); return
    r = _tool(t, "docs")
    t.check("docs exit 0", r.returncode == 0, _err_detail(r))
    t.check("docs lists using-fpf", "using-fpf" in r.stdout, _err_detail(r))
    t.check("docs lists library-reference", "library-reference" in r.stdout,
            _err_detail(r))

    r2 = _tool(t, "doc", "using-fpf")
    t.check("doc using-fpf exit 0", r2.returncode == 0, _err_detail(r2))
    t.check("doc using-fpf has the working instruction",
            "make the publications available" in r2.stdout.lower(),
            _err_detail(r2))

    r3 = _tool(t, "doc", "library-reference")
    t.check("doc library-reference has the catalogue",
            "Library.Reference:11.1" in r3.stdout, _err_detail(r3))


def test_idempotency(t: TestRunner):
    print("\n[Idempotency]")
    if not SPEC_PATH.exists():
        t.skip("idempotency", "No spec"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_fpf_spec.py"),
                 "split", "--source", str(SPEC_PATH), "--output", str(SKILL_DIR),
                 "--views"])
    t.check("idempotent run exit 0", r.returncode == 0, _err_detail(r))
    m = re.search(r"Written:\s*(\d+)", r.stdout)
    if m:
        written = int(m.group(1))
        t.check("idempotent run writes 0 files", written == 0,
                f"Wrote {written} files on second run")
    else:
        t.check("idempotent output parseable", False, r.stdout[:200])


def test_pattern_content_quality(t: TestRunner):
    print("\n[Pattern content]")
    pdir = SKILL_DIR / "reference" / "fpf-patterns"
    if not pdir.exists():
        t.skip("pattern content", "No patterns dir"); return

    b5 = pdir / "B.5.md"
    if b5.exists():
        content = b5.read_text("utf-8")
        t.check("B.5 has reasoning content",
                "reasoning" in content.lower() or "abduct" in content.lower())
        t.check("B.5 starts with ## heading", content.strip().startswith("##"))
    else:
        t.skip("B.5 content", "B.5.md not found")

    a1 = pdir / "A.1.md"
    if a1.exists():
        t.check("A.1 has holon", "holon" in a1.read_text("utf-8").lower())
    else:
        t.skip("A.1 content", "A.1.md not found")

    core = pdir / "G.Core.md"
    t.check("G.Core parsed as a pattern", core.exists())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    print("=" * 60)
    print("FPF Pipeline -- End-to-End Tests")
    print("=" * 60)

    t = TestRunner(verbose=verbose)

    test_prerequisites(t)
    test_split(t)
    test_structure(t)
    test_skill_md_quality(t)
    test_manifest(t)
    test_audit(t)
    test_rebuild(t)
    test_tools_search(t)
    test_tools_read(t)
    test_tools_list(t)
    test_tools_intro(t)
    test_tools_docs(t)
    test_idempotency(t)
    test_pattern_content_quality(t)

    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
