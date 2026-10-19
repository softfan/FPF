#!/usr/bin/env python3
"""Offline discovery regressions, using isolated miniature publication trees."""
from __future__ import annotations

import contextlib
import copy
import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "skill-maker" / "src"))

from skillmaker._fpf_common import ensure_utf8_stdio
from skillmaker import discover_skills as D, frameworks as F, skill_index, split_dpf_spec, fpf_frameworks
from skillmaker.split_spec import build_skill

ensure_utf8_stdio()


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, name, condition):
        if condition:
            self.passed += 1
            if "-v" in sys.argv:
                print(f"  PASS {name}")
        else:
            self.failed += 1
            print(f"  FAIL {name}")

    def rejects(self, name, action, expected):
        try:
            action()
        except (ValueError, OSError) as exc:
            self.check(name, expected in str(exc))
            if expected not in str(exc):
                print(f"    expected error containing {expected!r}, got {type(exc).__name__}: {exc}")
        else:
            self.check(name, False)
            print(f"    expected error containing {expected!r}, but operation succeeded")


def put(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def dpf(docid="DEMO", title="Example framework"):
    return (f"# {title}\n\n**DocID:** `{docid}` within **FPF Library**.\n\n"
            f"## {docid}.1 - First method\n\nA useful method.\n\n"
            f"## {docid}.Reference:1 - Scope\n\nReference body.\n\n"
            f"## {docid}.Reference:End\n")


def discover(root, **kwargs):
    return D.discover(root, configured=[], **kwargs)


def quiet_build(cfg):
    with contextlib.redirect_stdout(io.StringIO()):
        return build_skill(cfg)


def test_standalone(t, root):
    path = put(root, "DPFs/EXAMPLE-DPF.md", dpf())
    plan = discover(root)
    t.check("new DPF discovered without config entry", set(plan.configs) == {"demo"})
    cfg = plan.configs["demo"]
    t.check("DocID gives stable skill name", cfg.name == "demo" and cfg.prefix_token == "DEMO")
    t.check("DPF classified", cfg.profile_key == "dpf-framework")
    t.check("source is repository-relative", cfg.source_path == "DPFs/EXAMPLE-DPF.md")
    t.check("discovery writes nothing", not (root / "skills").exists())
    t.check("new publication reported", plan.added == ["DPFs/EXAMPLE-DPF.md"])
    D.validate_outputs(plan)
    t.check("new skill builds", quiet_build(cfg) == 0)
    manifest = json.loads((cfg.output / ".demo_manifest.json").read_text("utf-8"))
    t.check("pattern and reference emitted", {e["id"] for e in manifest if e["kind"] == "unit"}
            == {"DEMO.1", "DEMO.Reference:1"})
    t.check("Windows-safe unit filenames", (cfg.output / "reference/demo/DEMO.Reference-1.md").is_file())
    before = {p.relative_to(cfg.output): p.stat().st_mtime_ns
              for p in cfg.output.rglob("*") if p.is_file()}
    D.validate_outputs(discover(root))
    t.check("second build succeeds", quiet_build(discover(root).configs["demo"]) == 0)
    after = {p.relative_to(cfg.output): p.stat().st_mtime_ns
             for p in cfg.output.rglob("*") if p.is_file()}
    t.check("unchanged discovery build writes nothing", before == after)
    put(root, "DPFs/RENAMED-DPF.md", path.read_text("utf-8"))
    path.unlink()
    renamed = discover(root)
    t.check("renaming source keeps DocID skill name", set(renamed.configs) == {"demo"})
    t.rejects("changed source cannot silently take over output",
              lambda: D.validate_outputs(renamed), "another skill/source")


def test_suite(t, root):
    folder = "DPFs/Future DPF Suite/"
    put(root, folder + "FIRST-DPF.md", dpf("FUT", "Future methods"))
    put(root, folder + "FUTURE-SUITE-REFERENCE.md",
        "# Future Suite Architectural Reference\n\n**DocID:** `Future`\n\n"
        "## Future.Reference:1 - Composition\n\nConnected disciplines.\n")
    put(root, folder + "README.md", "# Future DPF Suite\n\n## Purpose\n\nA connected suite.\n")
    plan = discover(root)
    t.check("new suite becomes one skill", set(plan.configs) == {"future-suite"})
    cfg = plan.configs["future-suite"]
    t.check("new suite has frameworks layout", cfg.layout == "frameworks")
    t.check("suite bundles member and reference", {f.docid for f in cfg.frameworks} == {"FUT", "Future"})
    t.check("suite keeps README whole", len(cfg.docs) == 1 and cfg.docs[0].source.name == "README.md")
    t.check("reference role retained", next(f for f in cfg.frameworks if f.docid == "Future").role == "reference")
    t.check("new suite builds", quiet_build(cfg) == 0)
    original = copy.deepcopy(cfg)
    original.output = root / "different-output" / cfg.name
    put(root, folder + "SECOND-DPF.md", dpf("NEXT"))
    extended = D.discover(root, configured=[original])
    t.check("new member joins existing suite", set(extended.configs) == {"future-suite"}
            and {f.docid for f in extended.configs["future-suite"].frameworks} == {"FUT", "NEXT", "Future"})
    t.check("curated config not mutated", len(original.frameworks) == 2)
    t.check("new member reported", extended.added == [folder + "SECOND-DPF.md"])


def test_profiles(t, root):
    put(root, "frameworks/decisions/adr-payments.md",
        "# Payments decisions\n\n## ADR-0001 - Use transactions\n\nBody.\n")
    put(root, "frameworks/iso-demo.md",
        "# A standard\n\n## 1 Scope\n\nBody.\n## 2 Rules\n\nBody.\n## 3 Evidence\n\nBody.\n")
    put(root, "frameworks/book/patterns/design.md", "# A pattern language\n\n## 12. THE GATE\n\nBody.\n")
    put(root, "frameworks/notes.md", "# Notes\n\n## How to use\n\nSome plain prose.\n")
    put(root, "frameworks/USING-EXAMPLE.md", "# A guide\n\n## Start here\n\nInstructions.\n")
    plan = discover(root)
    profiles = {c.profile_key for c in plan.configs.values()}
    t.check("registered extension profiles discovered", profiles == {"adr", "standards", "pattern-language", "generic", "guide"})
    t.check("five independent documents", len(plan.configs) == 5)
    for cfg in plan.configs.values():
        t.check(f"discovered {cfg.profile_key} builds", quiet_build(cfg) == 0)
    put(root, "ignored/other.md", "# Ignore me\n")
    t.check("only designated roots scanned", "other" not in discover(root).configs)
    explicit = discover(root, source_roots=[Path("ignored")])
    t.check("explicit roots replace defaults", set(explicit.configs) == {"other"})


def test_conflicts(t, root):
    first = put(root, "DPFs/ONE-DPF.md", dpf("ZZ"))
    second = put(root, "DPFs/TWO-DPF.md", dpf("ZZ"))
    t.rejects("duplicate DocIDs rejected", lambda: discover(root), "duplicate DocID")
    second.write_bytes(dpf("zz").encode())
    t.rejects("case-only DocIDs rejected", lambda: discover(root), "duplicate DocID")
    second.unlink()
    cfg = discover(root).configs["zz"]
    cfg.name = "curated-name"
    cfg.output = root / "skills/curated-name"
    plan = D.discover(root, configured=[cfg])
    t.check("curated name wins over automatic naming", set(plan.configs) == {"curated-name"} and not plan.added)
    first.unlink()
    t.rejects("missing curated source is an error", lambda: D.discover(root, configured=[cfg]), "configured source missing")
    put(root, "frameworks/a-b.md", "# One\n")
    put(root, "frameworks/a_b.md", "# Two\n")
    t.rejects("normalised skill-name collision rejected", lambda: discover(root), "skill name collision")
    (root / "frameworks/a_b.md").unlink()
    # Never create NUL.md/CON.md on Windows: extensions do not stop those names
    # resolving as devices. Exercise the pure naming boundary on every OS.
    for device in sorted(D._RESERVED):
        t.rejects(f"Windows device skill name rejected: {device}",
                  lambda device=device: D._name(device.upper()), "portable skill name")
    put(root, "DPFs/DEVICE-DPF.md", dpf("NUL"))
    t.rejects("reserved DocID rejected through discovery", lambda: discover(root), "portable skill name")
    with patch.object(D.os, "walk", return_value=[(str(root / "frameworks"), [], ["NUL.md"])]):
        t.rejects("device source name rejected before I/O", lambda: list(D._markdown(root / "frameworks")),
                  "reserved Windows device")


def test_malformed(t, root):
    path = put(root, "DPFs/DEMO-DPF.md", "")
    t.rejects("empty publication rejected", lambda: discover(root), "empty publication")
    path.write_bytes(b"# Empty DPF\n\n**DocID:** `DEMO`\n")
    t.rejects("DPF without unit bodies rejected", lambda: discover(root), "no addressable units")
    path.write_bytes((dpf() + "\n## DEMO.1 - Duplicate\n\nOther body.\n").encode())
    t.rejects("duplicate unit ID rejected", lambda: discover(root), "duplicate unit IDs")
    path.write_bytes((dpf() + "\n## DEMO.Reference-1 - Colliding file\n\nOther body.\n").encode())
    t.rejects("normalised unit filenames collide", lambda: discover(root), "duplicate unit filenames")
    path.write_bytes((dpf() + "\n## OTHER.1 - Wrong prefix\n\nOther body.\n").encode())
    t.rejects("foreign heading cannot disappear silently", lambda: discover(root), "foreign unit ID")
    path.write_bytes(dpf("../../evil").encode())
    t.rejects("unsafe DocID rejected", lambda: discover(root), "DocID")
    path.write_bytes(dpf().replace("**DocID:** `DEMO` within **FPF Library**.\n", "").encode())
    inferred = discover(root)
    t.check("single heading prefix inferred", set(inferred.configs) == {"demo"})
    t.check("inferred-prefix skill builds", quiet_build(inferred.configs["demo"]) == 0)
    path.write_bytes((dpf() + "\n```markdown\n## OTHER.1 - Example only\n```\n").encode())
    t.check("foreign heading inside fence ignored", set(discover(root).configs) == {"demo"})
    path.unlink()
    put(root, "DPFs/Incomplete DPF Suite/ONE-DPF.md", dpf())
    t.rejects("incomplete suite rejected", lambda: discover(root), "exactly one Suite Reference")


def test_safety(t, root):
    put(root, "DPFs/ONE-DPF.md", dpf())
    plan = discover(root)
    output = root / "skills/demo"
    note = put(root, "skills/demo/notes.txt", "user work")
    t.rejects("nonempty unowned output rejected", lambda: D.validate_outputs(plan), "no skill marker")
    t.check("preflight preserves user file", note.read_bytes() == b"user work")
    marker = put(root, "skills/demo/.skill.json", '{"name":"other","source":"DPFs/ONE-DPF.md"}')
    t.rejects("output marker ownership checked", lambda: D.validate_outputs(plan), "another skill/source")
    marker.write_bytes(b'[]')
    t.rejects("malformed output marker rejected", lambda: D.validate_outputs(plan), "another skill/source")
    t.rejects("output cannot contain repo", lambda: discover(root, output_root=root), "must not contain")
    t.rejects("source cannot overlap output", lambda: discover(root, output_root=root / "DPFs"), "overlaps")
    t.rejects("outside source root rejected", lambda: discover(root, source_roots=[root.parent]), "inside the repository")
    t.rejects("explicit missing root is an error", lambda: discover(root, source_roots=[Path("typo")]), "not found")
    try:
        (root / "DPFs/LINK.md").symlink_to(note)
    except (OSError, NotImplementedError):
        print("  SKIP symlink checks (not supported)")
    else:
        t.rejects("linked publication rejected", lambda: discover(root), "symbolic links")
        (root / "DPFs/LINK.md").unlink()
        (output / "nested").symlink_to(root / "DPFs", target_is_directory=True)
        marker.write_bytes(b'{"name":"demo","source":"DPFs/ONE-DPF.md"}')
        t.rejects("nested output link rejected", lambda: D.validate_outputs(plan), "symbolic links")
    if hasattr(os, "mkfifo"):
        os.mkfifo(root / "DPFs/pipe.md")
        t.rejects("special file rejected without reading", lambda: discover(root), "regular publication")
        os.mkfifo(output / "pipe")
        # Remove only the fixture link so the special-file check is reached.
        if (output / "nested").is_symlink():
            (output / "nested").unlink()
        marker.write_bytes(b'{"name":"demo","source":"DPFs/ONE-DPF.md"}')
        t.rejects("output special file rejected", lambda: D.validate_outputs(plan), "special file")


def test_preflight_and_selection(t, root):
    put(root, "DPFs/ONE-DPF.md", dpf("ONE"))
    put(root, "DPFs/TWO-DPF.md", dpf("TWO"))
    plan = discover(root)
    put(root, "skills/two/user.txt", "not generated")
    t.rejects("whole plan preflight rejects later unsafe output", lambda: D.validate_outputs(plan), "no skill marker")
    t.check("earlier output remains unwritten", not (root / "skills/one").exists())
    with patch.object(split_dpf_spec, "_configs", return_value=plan.configs):
        t.check("new standalone selectable by DocID", split_dpf_spec._framework_by_name("ONE").name == "one")
        t.check("new standalone selectable by skill name", split_dpf_spec._framework_by_name("two").name == "two")
        suite = copy.deepcopy(plan.configs["one"])
        suite.name, suite.kind_label = "automatic-suite", "DPF Suite"
        plan.configs[suite.name] = suite
        t.check("new suite selectable with suffix", split_dpf_spec._suite_by_name("automatic-suite").name == suite.name)
        t.check("new suite selectable by short name", split_dpf_spec._suite_by_name("automatic").name == suite.name)
    # Profiles use deterministic tie-breaking for interactive probing. Automatic
    # builds must instead surface ties rather than pick an arbitrary writer.
    profile = F.by_key("dpf-framework")
    detection = profile.detect("DPFs/ONE-DPF.md", dpf("ONE"))
    with patch.object(F, "detect", return_value=(profile, detection)), \
            patch.object(F, "detect_all", return_value=[(profile, detection), (F.by_key("adr"), detection)]):
        t.rejects("ambiguous profile is explicit", lambda: discover(root), "ambiguous profile")


def test_global_units(t, root):
    put(root, "frameworks/adr-a.md", "# First decisions\n\n## ADR-0001 - First\n\nBody.\n")
    put(root, "frameworks/adr-b.md", "# Second decisions\n\n## ADR-0001 - Second\n\nBody.\n")
    t.rejects("cross-document unit collision rejected", lambda: discover(root), "duplicate unit ID")


def test_whole_document(t, root):
    put(root, "frameworks/notes.md", "# Notes\n\n## Example\n\nFirst.\n\n## Example\n\nSecond.\n")
    plan = discover(root)
    cfg = plan.configs["notes"]
    t.check("repeated prose headings retained in whole document", quiet_build(cfg) == 0
            and (cfg.output / "reference/docs/notes.md").read_text("utf-8").count("## Example") == 2)


def test_baseline_verification(t, root):
    expected = F.Publication(path="FPF-Spec.md", kind="FPF", patterns=2)
    extra = F.Publication(path="DPFs/NEW-DPF.md", kind="DPF", patterns=1)
    snapshot = put(root, "snapshot.json", "{}")

    def verify(local, allow_local):
        args = argparse.Namespace(verify=True, counts=True, json=False, remote=False,
                                  offline=True, snapshot=snapshot, allow_local=allow_local)
        def tree(path):
            count = next(p.patterns for p in local if path.name == Path(p.path).name)
            return argparse.Namespace(patterns=[None] * count, headings=1), None
        with patch.object(F, "load_local", return_value=local), \
                patch.object(F, "load_snapshot", return_value=([expected], {"count": 1})), \
                patch.object(fpf_frameworks, "_decompose", side_effect=tree), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            result = fpf_frameworks.cmd_catalogue(args)
        return result, output.getvalue()

    rc, message = verify([expected, extra], False)
    t.check("publisher verification stays strict by default", rc == 1 and "not in the publisher catalogue" in message)
    rc, message = verify([expected, extra], True)
    t.check("allow-local reports additions without weakening baseline", rc == 0 and extra.path in message)
    rc, message = verify([extra], True)
    t.check("allow-local still rejects missing baseline source", rc == 1 and "published but missing locally" in message)

    args = argparse.Namespace(verify=True, counts=True, json=False, remote=False,
                              offline=True, snapshot=None, allow_local=False)
    with patch.object(F, "load_local", return_value=[]), \
            contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()) as errors:
        rc = fpf_frameworks.cmd_catalogue(args)
    t.check("publisher comparison requires explicit snapshot", rc == 1 and "--snapshot" in errors.getvalue())


def test_variable_inventory(t, root):
    from skillmaker import mcp_server
    from skillmaker.split_spec import SpecParser

    source = put(root, "DPFs/VARIABLE-DPF.md", dpf("VAR"))
    original = discover(root).configs["var"]
    for pattern_ids, reference_ids in ((["VAR.1"], []),
                                       (["VAR.1", "VAR.2", "VAR.NEW"], ["VAR.Reference:1"]),
                                       ([], ["VAR.Reference:1", "VAR.Application:1"])):
        text = "# Variable input\n\n**DocID:** `VAR`\n\n"
        expected_ids = set(pattern_ids + reference_ids)
        for uid in pattern_ids + reference_ids:
            text += f"## {uid} - Current unit\n\nBody for {uid}.\n\n"
        source.write_bytes(text.encode("utf-8"))
        plan = D.discover(root, configured=[original])
        cfg = plan.configs["var"]
        D.validate_outputs(plan)
        t.check("changed inventory builds without editing config", quiet_build(cfg) == 0)
        entries = json.loads((cfg.output / ".var_manifest.json").read_text("utf-8"))
        units = [e for e in entries if e["kind"] == "unit"]
        t.check("manifest follows source additions and removals", {e["id"] for e in units} == expected_ids)
        files = {p.name for p in (cfg.output / "reference/var").glob("*.md") if p.name != "index.md"}
        t.check("obsolete unit files are pruned", files == {uid.replace(":", "-") + ".md" for uid in expected_ids})
        parser = SpecParser(cfg, cfg.frameworks[0])
        parser.parse()
        t.check("builder and independent decomposition agree", {c.id for c in parser.chunks if c.kind == "unit"}
                == set(F.decompose(F.by_key("dpf-framework"), text).ids()))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            rc = mcp_server.selftest(root / "skills")
        t.check("MCP selftest adapts to current inventory", rc == 0 and "PASSED" in output.getvalue())

    # Whole-document and empty corpora have no patterns, which is valid.
    empty = root / "empty-skills"
    empty.mkdir()
    with contextlib.redirect_stdout(io.StringIO()):
        rc = mcp_server.selftest(empty)
    t.check("MCP selftest accepts empty corpus", rc == 0)
    notes = put(root, "frameworks/notes.md", "# Notes\n\nOnly prose.\n")
    plan = discover(root, output_root=root / "prose-skills", source_roots=[Path("frameworks")])
    quiet_build(plan.configs["notes"])
    with contextlib.redirect_stdout(io.StringIO()):
        rc = mcp_server.selftest(root / "prose-skills")
    t.check("MCP selftest accepts whole-document corpus", rc == 0)

    # An offline maker check validates source ownership, not a publisher total.
    with patch.object(D, "discover", return_value=plan):
        result = mcp_server.Server(root / "prose-skills").call("verify_catalogue", {})
    t.check("MCP catalogue check is local by default", result["ok"] and result["mode"] == "local")


def test_optional_curated_inventory(t, root):
    put(root, "frameworks/notes.md", "# A private corpus\n\nNo Library source files.\n")
    plan = D.discover(root)
    t.check("default discovery needs no fixed Library inventory", set(plan.configs) == {"notes"})
    quiet_build(plan.configs["notes"])
    with patch.object(skill_index, "SKILLS_ROOT", root / "skills"), \
            patch.object(skill_index, "_REPO_ROOT", root):
        rows = skill_index.collect()
        t.check("index supports corpus without Core or curated Suites", {row["name"] for row in rows} == {"notes"})
    from skillmaker.mcp_server import Server

    result = Server(root / "skills").call("verify_catalogue", {})
    t.check("local catalogue verification accepts private input inventory", result["ok"] and result["publications"] == 1)
    (root / "frameworks/notes.md").unlink()
    t.check("removed source is not required by discovery", not D.discover(root).configs)


def test_index(t, root):
    put(root, "DPFs/NEW-DPF.md", dpf("NEW"))
    plan = discover(root)
    cfg = plan.configs["new"]
    quiet_build(cfg)
    # Keep the index's curated Core/Suite API while isolating its corpus.
    core = copy.deepcopy(cfg)
    core.name, core.output = "fpf", root / "skills/fpf"
    core.frameworks, core.docs = [], []
    all_cfgs = {"fpf": core, "new": cfg}
    with patch.object(skill_index, "SKILLS_ROOT", root / "skills"), \
            patch.object(skill_index, "_REPO_ROOT", root), \
            patch.object(skill_index, "SUITE_SKILL_CONFIGS", {}), \
            patch.object(D, "discover", return_value=D.Discovery(all_cfgs)):
        rows = skill_index.collect()
        payload = skill_index.payload(rows)
        t.check("discovered DocID appears in routing", payload["docid_to_skill"].get("NEW") == "new")
        t.check("discovered skill indexed once", [r["name"] for r in rows].count("new") == 1)
        t.check("index uses generated counts", payload["totals"]["patterns"] == 1)
        t.check("index --check inputs deterministic", skill_index.collect() == rows)


def test_cli(t, root):
    put(root, "DPFs/NEW-DPF.md", dpf("NEW"))
    args = [sys.executable, str(D._SCRIPT_DIR / "discover_skills.py"),
            "--repo-root", str(root), "--unconfigured", "--json"]
    run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", cwd=root.parent)
    t.check("JSON dry-run from another cwd succeeds", run.returncode == 0)
    data = json.loads(run.stdout)
    t.check("JSON lists source and skill", data["skills"][0]["name"] == "new"
            and data["skills"][0]["sources"] == ["DPFs/NEW-DPF.md"])
    t.check("CLI dry-run writes nothing", not (root / "skills").exists())
    args[-1] = "--views"
    run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    t.check("CLI builds discovered skill", run.returncode == 0 and (root / "skills/new/SKILL.md").is_file())
    put(root, "DPFs/BAD-DPF.md", dpf("NEW"))
    run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    t.check("CLI reports conflict without traceback", run.returncode == 1
            and "duplicate DocID" in run.stderr and "Traceback" not in run.stderr)


def main():
    t = TestRunner()
    print("Offline automatic framework discovery tests")
    with tempfile.TemporaryDirectory(prefix="skill-discovery-") as temporary:
        base = Path(temporary)
        for test in (test_standalone, test_suite, test_profiles, test_conflicts,
                     test_malformed, test_safety, test_preflight_and_selection,
                     test_global_units, test_whole_document, test_baseline_verification,
                     test_variable_inventory, test_optional_curated_inventory,
                     test_index, test_cli):
            root = base / test.__name__
            root.mkdir()
            try:
                test(t, root)
            except Exception as exc:
                t.check(f"{test.__name__} raised {type(exc).__name__}: {exc}", False)
    print(f"Results: {t.passed} passed, {t.failed} failed / {t.passed + t.failed} total")
    return int(bool(t.failed))


if __name__ == "__main__":
    sys.exit(main())
