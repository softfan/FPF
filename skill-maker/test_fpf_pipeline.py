#!/usr/bin/env python3
"""
test_fpf_pipeline.py — End-to-end tests for FPF skill pipeline.

Verifies: split -> structure -> audit -> rebuild -> diff -> tools.
Requires FPF-Spec.md in repo root.

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

# Ensure UTF-8 stdout for cp1251 consoles (Unicode characters like ✗)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

SPEC_PATH = _REPO_ROOT / "FPF-Spec.md"
SKILL_DIR = _REPO_ROOT / "skills" / "fpf"


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
            print(f"\nFailed tests:")
            for name, detail in self.failed:
                print(f"  \u2717 {name}: {detail}")
        print("=" * 60)
        return 0 if not self.failed else 1


def run_cmd(args: List[str], cwd: str = None) -> subprocess.CompletedProcess:
    """Run command and capture both stdout and stderr."""
    return subprocess.run(
        args, capture_output=True, text=True,
        cwd=cwd or str(_REPO_ROOT),
    )


def _err_detail(r: subprocess.CompletedProcess, max_len: int = 500) -> str:
    """Format error detail from a subprocess result."""
    parts = []
    if r.returncode != 0:
        parts.append(f"exit={r.returncode}")
    if r.stderr and r.stderr.strip():
        parts.append(f"stderr: {r.stderr.strip()[:max_len]}")
    if not r.stdout.strip():
        parts.append("(empty stdout)")
    elif len(parts) == 0:
        parts.append(f"stdout: {r.stdout.strip()[:max_len]}")
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
    t.check("skill-maker/ scripts exist",
            all((_SCRIPT_DIR / f).exists()
                for f in ["split_fpf_spec.py", "fpf_tools.py", "fpf_update.py", "split_fpf_spec.py",
                           "audit_fpf_patterns.py", "_fpf_common.py"]),
            "Missing script files")


def test_split(t: TestRunner):
    print("\n[Split]")
    if not SPEC_PATH.exists():
        t.skip("split", "No FPF-Spec.md"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_fpf_spec.py"),
                 "split", "--source", str(SPEC_PATH), "--output", str(SKILL_DIR)])
    t.check("split exit code 0", r.returncode == 0, _err_detail(r))


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
        t.check("patterns >= 150", len(patterns) >= 150, f"Found {len(patterns)}")
        t.check("index.md exists", (pdir / "index.md").exists())

    ref = SKILL_DIR / "reference"
    t.check("agent_index_patterns.md", (ref / "agent_index_patterns.md").exists())
    t.check("agent_index_keywords.md", (ref / "agent_index_keywords.md").exists())
    t.check("agent_index_queries.md", (ref / "agent_index_queries.md").exists())

    intros = list(ref.glob("intro_*.md"))
    t.check("intro sections >= 1", len(intros) >= 1, f"Found {len(intros)}")

    scripts_dir = SKILL_DIR / "scripts"
    t.check("scripts/ exists", scripts_dir.exists())
    if scripts_dir.exists():
        t.check("scripts/__init__.py", (scripts_dir / "__init__.py").exists())
        t.check("scripts/fpf_tools.py", (scripts_dir / "fpf_tools.py").exists())
        t.check("scripts/_fpf_common.py", (scripts_dir / "_fpf_common.py").exists())
        t.check("scripts/fpf_update.py", (scripts_dir / "fpf_update.py").exists())
        t.check("scripts/split_fpf_spec.py", (scripts_dir / "split_fpf_spec.py").exists())
        t.check("scripts/audit_fpf_patterns.py", (scripts_dir / "audit_fpf_patterns.py").exists())


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
    t.check("has Canonical Reasoning", "canonical reasoning" in content.lower() or "b.5" in content.lower())
    t.check("has dependency resolution", "dependency" in content.lower() or "topological" in content.lower())
    t.check("has kernel patterns", "kernel pattern" in content.lower())
    t.check("has self-update reference", "fpf_update" in content.lower() or "self-update" in content.lower())
    t.check("SKILL.md < 500 lines", len(content.splitlines()) < 500,
            f"Got {len(content.splitlines())} lines")
    # Check no unresolved template placeholders
    t.check("no {{placeholders}} left",
            "{{" not in content,
            f"Found unresolved placeholder in SKILL.md")


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
        t.check("has intro + pattern kinds", {"intro", "pattern"} <= kinds, f"Found: {kinds}")
        missing = []
        for entry in manifest:
            if entry["kind"] == "intro":
                p = SKILL_DIR / "reference" / entry["key"]
            else:
                p = SKILL_DIR / "reference" / "fpf-patterns" / entry["key"]
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
            t.check("audit generated >= 150", gen >= 150, f"Got {gen}")
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
            orig = SPEC_PATH.read_bytes()
            rebuilt = tmp_path.read_bytes()
            # Normalize line endings (CRLF→LF) for cross-platform comparison.
            # On WSL, git may check out FPF-Spec.md with CRLF endings, but
            # Python's text-mode write produces LF-only output, so the rebuilt
            # file has LF while the original has CRLF.  Stripping \r before
            # comparing gives us a pure content comparison.
            orig_nl = orig.replace(b"\r\n", b"\n")
            rebuilt_nl = rebuilt.replace(b"\r\n", b"\n")
            t.check("rebuild size match (normalized)",
                    abs(len(orig_nl) - len(rebuilt_nl)) < 100,
                    f"orig={len(orig_nl)}, rebuilt={len(rebuilt_nl)}, delta={len(orig_nl) - len(rebuilt_nl)}")
            if orig_nl != rebuilt_nl:
                for i, (a, b) in enumerate(zip(orig_nl, rebuilt_nl)):
                    if a != b:
                        t.check("rebuild byte-identical or trailing-newline only",
                                i >= len(orig_nl) - 2,
                                f"First diff at byte {i}/{len(orig_nl)}")
                        break
                else:
                    t.check("rebuild length diff <= 1", abs(len(orig_nl) - len(rebuilt_nl)) <= 1)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_tools_search(t: TestRunner):
    print("\n[Tools: search]")
    if not SKILL_DIR.exists():
        t.skip("tools:search", "No skill dir"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "fpf_tools.py"),
                 "--skill-root", str(SKILL_DIR), "search", "holon"])
    t.check("search exit 0", r.returncode == 0, _err_detail(r))
    t.check("search finds results",
            "A.1" in r.stdout or "holon" in r.stdout.lower(),
            _err_detail(r))


def test_tools_read(t: TestRunner):
    print("\n[Tools: read]")
    if not SKILL_DIR.exists():
        t.skip("tools:read", "No skill dir"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "fpf_tools.py"),
                 "--skill-root", str(SKILL_DIR), "read", "A.1"])
    t.check("read A.1 exit 0", r.returncode == 0, _err_detail(r))
    t.check("read A.1 has content", len(r.stdout) > 100,
            f"Got {len(r.stdout)} bytes | {_err_detail(r)}")

    r2 = run_cmd([sys.executable, str(_SCRIPT_DIR / "fpf_tools.py"),
                  "--skill-root", str(SKILL_DIR), "read", "A.999"])
    t.check("read A.999 suggests alternatives",
            "not found" in r2.stdout.lower() and "available" in r2.stdout.lower(),
            _err_detail(r2))


def test_tools_list(t: TestRunner):
    print("\n[Tools: list]")
    if not SKILL_DIR.exists():
        t.skip("tools:list", "No skill dir"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "fpf_tools.py"),
                 "--skill-root", str(SKILL_DIR), "list", "A"])
    t.check("list A exit 0", r.returncode == 0, _err_detail(r))
    t.check("list A has patterns", "A.1" in r.stdout, _err_detail(r))


def test_tools_intro(t: TestRunner):
    print("\n[Tools: intro]")
    if not SKILL_DIR.exists():
        t.skip("tools:intro", "No skill dir"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "fpf_tools.py"),
                 "--skill-root", str(SKILL_DIR), "intro", "table"])
    t.check("intro 'table' exit 0", r.returncode == 0, _err_detail(r))
    t.check("intro finds table_of_content",
            "table" in r.stdout.lower() or "content" in r.stdout.lower(),
            _err_detail(r))

    r2 = run_cmd([sys.executable, str(_SCRIPT_DIR / "fpf_tools.py"),
                  "--skill-root", str(SKILL_DIR), "intro", "xyznonexistent"])
    t.check("intro miss lists available",
            "not found" in r2.stdout.lower() or "available" in r2.stdout.lower(),
            _err_detail(r2))


def test_idempotency(t: TestRunner):
    print("\n[Idempotency]")
    if not SPEC_PATH.exists():
        t.skip("idempotency", "No spec"); return
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_fpf_spec.py"),
                 "split", "--source", str(SPEC_PATH), "--output", str(SKILL_DIR)])
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
        content = a1.read_text("utf-8")
        t.check("A.1 has holon", "holon" in content.lower())
    else:
        t.skip("A.1 content", "A.1.md not found")


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
    test_idempotency(t)
    test_pattern_content_quality(t)

    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
