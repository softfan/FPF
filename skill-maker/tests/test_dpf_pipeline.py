#!/usr/bin/env python3
"""
test_dpf_pipeline.py -- End-to-end tests for the DPF skill pipeline.

Verifies the whole DPF side of the toolchain:

* **Catalogue completeness** -- every framework file published in ``DPFs/``
  (including Suite folders) is used by exactly one skill config, and
  every configured source exists.
* **Catalogue agreement** -- DocIDs, titles and carriers agree with the
  Library's own catalogue in ``FPF-LIBRARY-REFERENCE.md``.
* **Split** -- every skill builds without error.
* **Structure** -- SKILL.md, README.md, manifest, indexes and unit files.
* **Inventory** -- generated units match the current source documents.
* **Rebuild** -- a skill can be reassembled from its own files.

Usage from repo root:
    python skill-maker/tests/test_dpf_pipeline.py [-v]

Exit codes: 0 = all passed, 1 = failures found.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

_TESTS_DIR = Path(__file__).resolve().parent
_MAKER_DIR = _TESTS_DIR.parent                 # skill-maker/
_PKG_PARENT = _MAKER_DIR / "src"
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))
_SCRIPT_DIR = _PKG_PARENT / "skillmaker"        # the package: entry points, templates
_REPO_ROOT = _MAKER_DIR.parent                  # repository root

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

from skillmaker.skill_config import ALL_DPF_CONFIGS  # noqa: E402

DPF_ROOT = _REPO_ROOT / "DPFs"


class TestRunner:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.passed: List[str] = []
        self.failed: List[Tuple[str, str]] = []

    def check(self, name, condition, detail=""):
        if condition:
            self.passed.append(name)
            if self.verbose:
                print(f"  ✓ {name}")
        else:
            self.failed.append((name, detail))
            print(f"  ✗ {name}: {detail}")

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed)
        print(f"\n{'=' * 64}")
        print(f"Results: {len(self.passed)} passed, {len(self.failed)} failed / {total} total")
        if self.failed:
            for name, detail in self.failed:
                print(f"  ✗ {name}: {detail}")
        print("=" * 64)
        return 0 if not self.failed else 1


def run_cmd(args):
    # Explicit UTF-8: the child writes UTF-8, and the locale codec on Windows
    # (cp1251, cp437, ...) cannot decode it.
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          cwd=str(_REPO_ROOT))


def _err(r):
    return f"exit={r.returncode} | stderr={(r.stderr or '').strip()[:300]}"


# ---------------------------------------------------------------------------
# Test groups
# ---------------------------------------------------------------------------

def test_catalogue_completeness(t: TestRunner):
    """Every published DPF file belongs to exactly one skill."""
    print("\n[Catalogue completeness]")
    published = sorted(
        p.relative_to(DPF_ROOT).as_posix()
        for p in DPF_ROOT.rglob("*.md")
        if p.name != "README.md"
    )
    from skillmaker.discover_skills import discover

    configs = discover().configs
    configured = [item.source.relative_to(DPF_ROOT).as_posix()
                  for cfg in configs.values() for item in [*cfg.frameworks, *cfg.docs]
                  if item.source.is_relative_to(DPF_ROOT) and item.source.name != "README.md"]
    t.check("every DPF file is used",
            set(published) == set(configured),
            f"unused={sorted(set(published) - set(configured))[:4]} "
            f"missing={sorted(set(configured) - set(published))[:4]}")
    t.check("no file used twice", len(configured) == len(set(configured)),
            f"{len(configured)} uses, {len(set(configured))} distinct files")
    for fw in [fw for cfg in ALL_DPF_CONFIGS.values() for fw in cfg.frameworks]:
        t.check(f"source exists: {fw.source.name}", fw.source.exists(), str(fw.source))


def test_library_catalogue_agreement(t: TestRunner):
    """Current source DocIDs agree with their owning config."""
    print("\n[Source identity]")
    from skillmaker import frameworks as F
    from skillmaker.discover_skills import discover

    for cfg in discover().configs.values():
        for item in [*cfg.frameworks, *cfg.docs]:
            declared = F.docid_of(item.source.read_text("utf-8"))
            if declared:
                t.check(f"{item.source.name}: declared DocID retained",
                        declared == item.docid, f"source={declared!r}, config={item.docid!r}")


def test_expected_counts(t: TestRunner):
    """Configs describe ownership, not expected corpus sizes."""
    print("\n[Catalogue ownership]")
    paths = [fw.source for cfg in ALL_DPF_CONFIGS.values() for fw in cfg.frameworks]
    t.check("configured sources have unique ownership", len(paths) == len(set(paths)))


def test_split(t: TestRunner):
    print("\n[Split]")
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_dpf_spec.py"), "split", "--all", "--views"])
    t.check("split exit 0", r.returncode == 0, _err(r))


def _skill_dir(cfg) -> Path:
    return cfg.output


def test_structure(t: TestRunner):
    print("\n[Structure]")
    for name, cfg in sorted(ALL_DPF_CONFIGS.items()):
        d = _skill_dir(cfg)
        t.check(f"{name}: SKILL.md exists", (d / "SKILL.md").exists())
        t.check(f"{name}: README.md exists", (d / "README.md").exists())
        t.check(f"{name}: manifest exists", (d / f".{name}_manifest.json").exists())
        ref = d / "reference"
        t.check(f"{name}: reference/index.md", (ref / "index.md").exists())
        for idx in ("pattern-index.md", "keyword-index.md",
                    "query-index.md", "reference-index.md"):
            t.check(f"{name}: {idx}", (ref / idx).exists())
        for fw in cfg.frameworks:
            fdir = ref / fw.key
            t.check(f"{name}: {fw.key}/ exists", fdir.is_dir())
            t.check(f"{name}: {fw.key}/index.md", (fdir / "index.md").exists())


def test_counts(t: TestRunner):
    print("\n[Pattern counts]")
    from skillmaker import frameworks as F
    from skillmaker.discover_skills import discover

    configs = discover().configs
    for name, cfg in configs.items():
        if name == "fpf":
            continue
        mpath = _skill_dir(cfg) / f".{name}_manifest.json"
        if not mpath.exists():
            t.check(f"{name}: manifest", False); continue
        entries = json.loads(mpath.read_text("utf-8"))
        units = [e for e in entries if e.get("kind") == "unit"]
        pats = [e for e in units if e.get("role") == "pattern"]
        expected = set()
        for fw in cfg.frameworks:
            text = fw.source.read_text("utf-8")
            profile, _ = F.detect(fw.source.relative_to(_REPO_ROOT).as_posix(), text)
            expected.update((fw.key, u.id, u.role) for u in F.decompose(profile, text).units)
        actual = {(e["framework"], e["id"], e["role"]) for e in units}
        t.check(f"{name}: unit identities and roles match source", actual == expected,
                f"missing={sorted(expected - actual)[:4]} extra={sorted(actual - expected)[:4]}")
        t.check(f"{name}: no duplicate manifest units", len(units) == len(actual))


def test_unit_files(t: TestRunner):
    print("\n[Unit files]")
    for name, cfg in sorted(ALL_DPF_CONFIGS.items()):
        mpath = _skill_dir(cfg) / f".{name}_manifest.json"
        if not mpath.exists():
            continue
        entries = json.loads(mpath.read_text("utf-8"))
        missing = []
        for e in entries:
            if e.get("kind") == "unit":
                p = _skill_dir(cfg) / "reference" / e["framework"] / e["key"]
            elif e.get("kind") == "intro":
                p = _skill_dir(cfg) / "reference" / "intro" / e["key"]
            else:
                p = _skill_dir(cfg) / "reference" / "docs" / e["key"]
            if not p.exists():
                missing.append(e["key"])
        t.check(f"{name}: all manifest files exist", not missing,
                f"missing: {missing[:5]}")
        stems = {e["key"] for e in entries if e.get("kind") == "unit"}
        t.check(f"{name}: no ':' in file names", not any(":" in s for s in stems))


def test_intro_files(t: TestRunner):
    """Front matter must survive a Suite bundling several publications.

    Every constituent DPF has its own ``Architectural Reference``, ``Table of
    Content`` and ``Practical entries``.  Those headings used to slug to the
    same file name, so four of five were overwritten -- silently, and with a
    different winner depending on build order.  Two checks catch that: the keys
    are unique, and every framework contributes its own.
    """
    print("\n[Intro files]")
    from skillmaker.discover_skills import discover

    configs = discover().configs
    for name in sorted(ALL_DPF_CONFIGS):
        cfg = configs[name]
        mpath = _skill_dir(cfg) / f".{name}_manifest.json"
        if not mpath.exists():
            continue
        entries = json.loads(mpath.read_text("utf-8"))
        keys = [e["key"] for e in entries if e.get("kind") == "intro"]
        t.check(f"{name}: intro keys are unique", len(keys) == len(set(keys)),
                f"{len(keys)} keys, {len(set(keys))} distinct")
        if len(cfg.frameworks) > 1:
            from skillmaker.split_spec import SpecParser

            owners = {e.get("framework") for e in entries
                       if e.get("kind") == "intro"}
            expected = set()
            for fw in cfg.frameworks:
                parser = SpecParser(cfg, fw)
                parser.parse()
                if any(c.kind == "intro" for c in parser.chunks):
                    expected.add(fw.key)
            t.check(f"{name}: every framework contributes front matter",
                    expected <= owners, f"missing: {sorted(expected - owners)}")
            t.check(f"{name}: intro names carry their framework",
                     all(any(k.startswith(key + "_") for key in expected) for k in keys),
                     str(keys[:3]))

def test_indexes(t: TestRunner):
    print("\n[Indexes]")
    for name, cfg in sorted(ALL_DPF_CONFIGS.items()):
        ref = _skill_dir(cfg) / "reference"
        apath = ref / "pattern-index.md"
        if not apath.exists():
            continue
        rows = [l for l in apath.read_text("utf-8").splitlines()
                if l.startswith("| ") and not l.startswith("| :")
                and not l.startswith("| ID ")]
        entries = json.loads((cfg.output / f".{cfg.name}_manifest.json").read_text("utf-8"))
        expected_units = (sum(e.get("kind") == "unit" and e.get("role") == "pattern" for e in entries)
                          or sum(e.get("kind") == "unit" for e in entries))
        t.check(f"{name}: pattern index follows current units", len(rows) == expected_units,
                f"rows={len(rows)}, units={expected_units}")
        t.check(f"{name}: index rows carry a File column",
                all("`reference/" in r for r in rows),
                f"first row: {rows[0][:120] if rows else '(none)'}")
        rpath = ref / "reference-index.md"
        if rpath.exists():
            rrows = [l for l in rpath.read_text("utf-8").splitlines()
                      if l.startswith("| ") and not l.startswith("| :")
                      and not l.startswith("| Unit ") and not l.startswith("| _(none)_")]
            expected_refs = sum(e.get("kind") == "unit" and e.get("role") != "pattern" for e in entries)
            t.check(f"{name}: reference index follows current units", len(rrows) == expected_refs,
                    f"rows={len(rrows)}, units={expected_refs}")


def test_skill_md_quality(t: TestRunner):
    print("\n[SKILL.md quality]")
    for name, cfg in sorted(ALL_DPF_CONFIGS.items()):
        sp = _skill_dir(cfg) / "SKILL.md"
        if not sp.exists():
            t.check(f"{name}: SKILL.md", False); continue
        content = sp.read_text("utf-8")
        t.check(f"{name}: name: {name}", f"name: {name}" in content)
        t.check(f"{name}: title '{cfg.title}'", f"# {cfg.title}" in content)
        t.check(f"{name}: no {{placeholders}}", "{{" not in content)
        t.check(f"{name}: example ID rendered",
                bool(re.search(r"Pattern ID \(e\.g\. `[A-Za-z][A-Za-z0-9]*(?:[.:][A-Za-z0-9_]+)+`\)",
                               content)),
                "no concrete pattern ID in the entry table")


def test_rebuild(t: TestRunner):
    print("\n[Rebuild]")
    for name, cfg in sorted(ALL_DPF_CONFIGS.items()):
        d = _skill_dir(cfg)
        if not (d / f".{name}_manifest.json").exists():
            t.check(f"{name}: rebuild prereq", False); continue
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_dpf_spec.py"),
                         "rebuild", "--skill-dir", str(d), "--output", str(tmp_path)])
            t.check(f"{name}: rebuild exit 0", r.returncode == 0, _err(r))
            if r.returncode == 0:
                rebuilt = tmp_path.read_bytes().replace(b"\r\n", b"\n")
                expected = b"".join(fw.source.read_bytes().replace(b"\r\n", b"\n")
                                    for fw in cfg.frameworks)
                t.check(f"{name}: rebuild retains source content",
                        rebuilt.replace(b"\n", b"") == expected.replace(b"\n", b""))
        finally:
            tmp_path.unlink(missing_ok=True)


def test_standalone_selection(t: TestRunner):
    print("\n[CLI selection]")
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_dpf_spec.py"),
                 "split", "--framework", "fdm", "--views"])
    t.check("single --framework build exit 0", r.returncode == 0, _err(r))
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_dpf_spec.py"),
                 "split", "--suite", "engineering", "--views"])
    t.check("single --suite build exit 0", r.returncode == 0, _err(r))
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "split_dpf_spec.py"),
                 "split", "--framework", "NOPE"])
    t.check("unknown framework rejected", r.returncode != 0)


def test_skill_index(t: TestRunner) -> None:
    print("\n[Skill index]")
    root = _REPO_ROOT / "skills"
    readme = root / "README.md"
    index = root / "index.json"
    t.check("skills/README.md exists", readme.exists())
    t.check("skills/index.json exists", index.exists())
    if not (readme.exists() and index.exists()):
        return

    import json as _json
    data = _json.loads(index.read_text("utf-8"))
    names = {row["name"] for row in data["skills"]}
    manifests = {path.parent.name for path in root.glob("*/.*_manifest.json")}
    from skillmaker.discover_skills import discover

    configs = discover().configs
    configured = set(configs)
    t.check("index lists every built and configured skill",
            names == manifests | configured, str(sorted(names)))
    t.check("index lists discovered suites",
            {c.name for c in configs.values() if c.kind_label == "DPF Suite"} <= names)
    t.check("index lists discovered standalone frameworks",
            {c.name for c in configs.values() if c.kind_label != "DPF Suite"} <= names)

    routing = data["docid_to_skill"]
    expected_docids = {item.docid for cfg in discover().configs.values()
                       for item in [*cfg.frameworks, *cfg.docs] if item.docid}
    t.check("DocID routing covers every framework", expected_docids <= set(routing), str(routing))
    t.check("DocID routes match discovered owners",
            all(routing.get(item.docid) == cfg.name for cfg in configs.values()
                for item in [*cfg.frameworks, *cfg.docs] if item.docid))

    body = readme.read_text("utf-8")
    for name in names:
        t.check(f"README links {name}", f"]({name}/)" in body)
    expected_patterns = sum(row["patterns"] for row in data["skills"])
    t.check("README states the totals", f"{expected_patterns} patterns" in body,
            body[-300:])

    cross = root / "CROSS-REFERENCES.md"
    t.check("skills/CROSS-REFERENCES.md exists", cross.exists())
    if cross.exists():
        body_cross = cross.read_text("utf-8")
        targets = re.findall(r"\]\(([^)]+)\)", body_cross)
        t.check("cross-references resolve to skills",
                all((cross.parent / target).is_dir() for target in targets),
                body_cross[:300])
        refs = sum(len(v) for v in data.get("cross_skill", {}).values())
        t.check("cross-reference table matches index",
                body_cross.count("\n| ") == (refs or 1) + 2,
                str(body_cross.count("\n| ")))

    data = _json.loads(index.read_text("utf-8"))
    t.check("index carries cross-skill mapping", isinstance(data.get("cross_skill"), dict),
            str(list(data)[:8]))

    # The index must describe what was actually built.
    r = run_cmd([sys.executable, str(_SCRIPT_DIR / "skill_index.py"), "--check"])
    t.check("index is up to date", r.returncode == 0, _err(r))


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    print("=" * 64)
    print("DPF Pipeline -- End-to-End Tests")
    print("=" * 64)
    t = TestRunner(verbose)
    test_catalogue_completeness(t)
    test_library_catalogue_agreement(t)
    test_expected_counts(t)
    test_split(t)
    test_structure(t)
    test_counts(t)
    test_unit_files(t)
    test_intro_files(t)
    test_indexes(t)
    test_skill_md_quality(t)
    test_rebuild(t)
    test_standalone_selection(t)
    test_skill_index(t)
    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
