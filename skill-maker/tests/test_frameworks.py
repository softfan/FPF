#!/usr/bin/env python3
"""
test_frameworks.py -- tests for the general framework-decomposition layer.

Three questions are being answered here:

1. **Does it cover everything the Library publishes?**  All 46 publications must
   classify into the right kind, and every pattern count must agree with the
   publisher's own catalogue (``catalogue.snapshot.json``, fetched from
   publisher's own catalogue).  Checking against the publisher rather than
   against the previous build is what makes this a real test.

2. **Does it agree with the existing engine?**  The dotted-identifier grammar in
   ``frameworks/grammar.py`` must recognise exactly the units that
   ``split_spec.build_heading_re`` recognises, on every published document.  Two
   parsers that disagree would silently ship two different skills.

3. **Does it generalise beyond the Library?**  ADR sets, clause-numbered
   standards, Alexander-style pattern languages and plain Markdown must all
   decompose, with no new code -- only a profile.

Usage from repo root::

    python skill-maker/tests/test_frameworks.py
    python skill-maker/tests/test_frameworks.py -v

Exit codes: 0 = all passed, 1 = failures found.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
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

from skillmaker import frameworks as F  # noqa: E402
from skillmaker._fpf_common import FenceTracker  # noqa: E402

SNAPSHOT = _SCRIPT_DIR / "catalogue.snapshot.json"


def _toolchain_py() -> List[Path]:
    """Every Python file that is part of the toolchain.

    The package holds the engine; ``tests/`` holds the suites that run it.
    Both are scanned for the platform traps below, because a suite that
    decodes a subprocess with the locale codec breaks the build just as
    surely as the engine does.
    """
    return [p for p in sorted(_MAKER_DIR.rglob("*.py"))
            if "__pycache__" not in p.parts]


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

def snapshot() -> Dict[str, Dict]:
    payload = json.loads(SNAPSHOT.read_text("utf-8"))
    return {p["path"]: p for p in payload["publications"]}


def local_text(rel: str) -> str:
    return (_REPO_ROOT / rel).read_text("utf-8", errors="replace")


ADR_DOC = """# Payments service decisions

Architecture decisions for the payments service.

## ADR-0001 - Use an outbox table

Status: accepted.

We write domain events to an outbox in the same transaction.

## ADR-0002 - Choose PostgreSQL

Status: accepted.

The outbox needs transactional guarantees.
"""

STANDARDS_DOC = """# Architecture description standard

## 1 Scope

This document specifies requirements.

## 1.1 Purpose

Requirements for architecture descriptions.

## 4.3.2 Architecture rationale

The rationale shall identify the decisions.
"""

PATTERN_DOC = """# A small pattern language

## 1. THE GATE

Context: a boundary between two worlds.

Therefore: place a gate.
"""

GENERIC_DOC = """# Release notes

## What changed

Everything.

## How to upgrade

Carefully.
"""

END_MARKER_DOC = """# Demo framework

**DocID:** `DEMO` within **FPF Library**.

## DEMO.1 - First pattern

Body of the first pattern.

## DEMO.Reference:1 - A reference unit

Reference body.

## DEMO.Reference:End
"""

FENCE_DOC = """# Fenced

## DEMO.1 - Real unit

```markdown
## DEMO.99 - Not a unit
```
"""


# ---------------------------------------------------------------------------
# 1. Vocabulary and registry
# ---------------------------------------------------------------------------

def test_kinds(t: TestRunner) -> None:
    print("\n[1] Publication kinds")
    t.equal("eight kinds registered", len(list(F.PublicationKind)), 8)
    t.equal("four catalogue kinds", len(F.CATALOGUE_KINDS), 4)
    t.check("catalogue kinds match the publisher",
            set(F.CATALOGUE_KINDS) == {"FPF", "DPF", "Reference", "Guide"},
            str(F.CATALOGUE_KINDS))
    for value in F.CATALOGUE_KINDS:
        kind = F.kind_from_catalogue(value)
        t.equal(f"catalogue kind round-trip {value}", kind.value, value)
    try:
        F.kind_from_catalogue("Brochure")
        t.check("unknown kind raises", False, "no exception")
    except KeyError as exc:
        t.check("unknown kind raises", "known kinds" in str(exc), str(exc))

    t.check("FPF is pattern-bearing", F.kind_info(F.PublicationKind.FPF).pattern_bearing)
    t.check("Reference is not pattern-bearing",
            not F.kind_info(F.PublicationKind.REFERENCE).pattern_bearing)
    t.check("extension kinds are outside the Library",
            all(not F.kind_info(k).in_library for k in (
                F.PublicationKind.ADR, F.PublicationKind.STANDARDS,
                F.PublicationKind.PATTERN_LANGUAGE, F.PublicationKind.GENERIC)))


def test_registry(t: TestRunner) -> None:
    print("\n[2] Profile registry")
    profiles = F.all_profiles()
    t.equal("eight profiles", len(profiles), 8)
    t.equal("keys are unique", len({p.key for p in profiles}), len(profiles))
    t.equal("fallback is last", profiles[-1].key, "generic")
    t.check("fallback resolves", F.fallback().key == "generic")
    t.equal("dpf profile kind", F.by_key("dpf-framework").kind, F.PublicationKind.DPF)
    t.equal("four profiles for library kinds",
            len([p for p in profiles if p.kind_info().in_library]), 4)
    try:
        F.by_key("nope")
        t.check("unknown profile raises", False, "no exception")
    except KeyError as exc:
        t.check("unknown profile raises", "known profiles" in str(exc), str(exc))
    try:
        F.register(F.by_key("generic"))
        t.check("duplicate registration rejected", False, "no exception")
    except ValueError:
        t.check("duplicate registration rejected", True)


# ---------------------------------------------------------------------------
# 2. Coverage of the published Library
# ---------------------------------------------------------------------------

def test_catalogue(t: TestRunner) -> None:
    print("\n[3] Local catalogue")
    pubs = F.load_local(_REPO_ROOT, classify=F.classify)
    t.equal("46 publications discovered", len(pubs), 46)
    counts = F.summarise(pubs)
    t.equal("DPF count", counts.get("DPF"), 33)
    t.equal("Reference count", counts.get("Reference"), 4)
    t.equal("Guide count", counts.get("Guide"), 8)
    t.equal("FPF count", counts.get("FPF"), 1)
    t.check("every publication has a kind", all(p.kind for p in pubs),
            str([p.path for p in pubs if not p.kind]))
    suite_members = [p for p in pubs if p.suite and p.kind == "DPF"]
    t.equal("23 Suite DPFs", len(suite_members), 23)
    t.equal("10 standalone DPFs",
            len([p for p in pubs if p.kind == "DPF" and not p.suite]), 10)
    t.check("DocIDs are declared",
            all(p.docid for p in pubs if p.kind in ("FPF", "DPF", "Reference")),
            str([p.path for p in pubs
                 if p.kind in ("FPF", "DPF", "Reference") and not p.docid]))


def test_snapshot(t: TestRunner) -> None:
    print("\n[4] Agreement with the publisher catalogue")
    t.check("snapshot file present", SNAPSHOT.exists(), str(SNAPSHOT))
    if not SNAPSHOT.exists():
        return
    remote = snapshot()
    t.equal("snapshot lists 46 publications", len(remote), 46)
    t.equal("snapshot lists 885 patterns",
            sum(p["patterns"] for p in remote.values()), 885)

    pubs = F.load_local(_REPO_ROOT, classify=F.classify)
    missing = [p.path for p in pubs if p.path not in remote]
    t.check("every local publication is published", not missing, str(missing))

    kind_mismatch = [(p.path, p.kind, remote[p.path]["kind"])
                     for p in pubs
                     if p.path in remote and p.kind != remote[p.path]["kind"]]
    t.check("kinds agree with the publisher", not kind_mismatch, str(kind_mismatch))


def test_decomposition(t: TestRunner) -> None:
    print("\n[5] Decomposition of every publication")
    remote = snapshot()
    pubs = F.load_local(_REPO_ROOT, classify=F.classify)

    total_patterns = 0
    total_units = 0
    mismatches: List[str] = []
    empty: List[str] = []
    for pub in pubs:
        text = local_text(pub.path)
        profile, _ = F.detect(pub.path, text)
        tree = F.decompose(profile, text, pub.path)
        if not tree.units:
            empty.append(pub.path)
        total_patterns += len(tree.patterns)
        total_units += len(tree.units)
        expected = remote.get(pub.path, {}).get("patterns", 0)
        if len(tree.patterns) != expected:
            mismatches.append(f"{pub.path}: {len(tree.patterns)} != {expected}")

    t.check("every publication decomposes", not empty, str(empty))
    t.check("pattern counts match the publisher", not mismatches, str(mismatches[:6]))
    t.equal("885 patterns in total", total_patterns, 885)
    # The figure README.md and FRAMEWORKS.md quote.  Asserted here so a change
    # in the grammar or in a source file cannot leave the docs quietly wrong.
    t.equal("1556 units in total", total_units, 1556)

    # FPF Core: 397 patterns plus 21 reference units in the embedded Reference.
    fpf = F.decompose(*_split("FPF-Spec.md"))
    t.equal("FPF units", len(fpf.units), 418)
    t.equal("FPF patterns", len(fpf.patterns), 397)
    t.equal("FPF reference units", len(fpf.references), 21)
    t.equal("FPF parts", len(fpf.parts), 13)

    # Suite References carry no patterns at all.
    for pub in pubs:
        if pub.kind != "Reference":
            continue
        tree = F.decompose(*_split(pub.path))
        t.equal(f"{Path(pub.path).stem} has no patterns", len(tree.patterns), 0)
        t.check(f"{Path(pub.path).stem} has reference units", len(tree.units) > 0,
                str(len(tree.units)))
        t.check(f"{Path(pub.path).stem} roles are reference",
                set(tree.by_role()) == {"reference"}, str(tree.by_role()))

    # Guides are sections, never patterns.
    for pub in pubs:
        if pub.kind != "Guide":
            continue
        tree = F.decompose(*_split(pub.path))
        t.equal(f"{Path(pub.path).stem} guide has no patterns", len(tree.patterns), 0)


def _split(rel: str):
    text = local_text(rel)
    profile, _ = F.detect(rel, text)
    return profile, text, rel


# ---------------------------------------------------------------------------
# 3. Agreement with the existing engine
# ---------------------------------------------------------------------------

def test_engine_agreement(t: TestRunner) -> None:
    print("\n[6] Agreement with split_spec's heading grammar")
    from skillmaker.skill_config import ALL_DPF_CONFIGS, FrameworkSpec
    from skillmaker.split_spec import build_heading_re

    targets: List[Tuple[Path, str, str]] = [(_REPO_ROOT / "FPF-Spec.md", "FPF", r"(?:[A-K]|FPF)")]
    for config in ALL_DPF_CONFIGS.values():
        for fw in config.frameworks:
            targets.append((fw.source, fw.prefix_re, fw.prefix_re))

    mismatches: List[str] = []
    for source, label, prefix in targets:
        text = source.read_text("utf-8", errors="replace")
        fw = FrameworkSpec(key="x", prefix_re=prefix, source=source,
                           name=label, description="")
        engine_with, engine_bare = build_heading_re(fw)
        grammar = F.DOTTED.for_prefix(prefix)

        fence = FenceTracker()
        for line in text.splitlines():
            if not fence.in_fence:
                a = engine_with.match(line) or engine_bare.match(line)
                b = F.split_heading(line, grammar)
                a_id = a.group("id") if a else None
                b_id = b[0] if b else None
                if a_id != b_id:
                    mismatches.append(f"{source.name}: {line[:60]!r} "
                                      f"engine={a_id!r} frameworks={b_id!r}")
                    if len(mismatches) > 8:
                        break
            fence.update(line)
        if len(mismatches) > 8:
            break

    t.check("both parsers agree on every heading", not mismatches, str(mismatches[:6]))


# ---------------------------------------------------------------------------
# 4. Generality beyond the Library
# ---------------------------------------------------------------------------

def test_extension_kinds(t: TestRunner) -> None:
    print("\n[7] Extension kinds (ADR, standards, pattern language, generic)")

    profile, detection = F.detect("docs/adr/adr-0001.md", ADR_DOC)
    t.equal("ADR detected", profile.kind, F.PublicationKind.ADR)
    tree = F.decompose(profile, ADR_DOC, "docs/adr/adr-0001.md")
    t.equal("ADR units", len(tree.units), 2)
    t.equal("ADR ids", tree.ids(), ["ADR-0001", "ADR-0002"])
    t.equal("ADR role", {u.role for u in tree.units}, {"decision"})
    t.equal("ADR filenames", tree.filenames(), ["ADR-0001", "ADR-0002"])
    t.check("ADR detection has evidence", bool(detection.reasons), str(detection))

    profile, _ = F.detect("docs/iso-42010.md", STANDARDS_DOC)
    t.equal("standards detected", profile.kind, F.PublicationKind.STANDARDS)
    tree = F.decompose(profile, STANDARDS_DOC, "docs/iso-42010.md")
    t.equal("clause ids", tree.ids(), ["1", "1.1", "4.3.2"])
    t.equal("clause role", {u.role for u in tree.units}, {"clause"})
    t.equal("clause title", tree.units[-1].title, "Architecture rationale")

    profile, _ = F.detect("book/patterns/01.md", PATTERN_DOC)
    t.equal("pattern language detected", profile.kind, F.PublicationKind.PATTERN_LANGUAGE)
    tree = F.decompose(profile, PATTERN_DOC, "book/patterns/01.md")
    t.equal("pattern id", tree.ids(), ["1"])
    t.equal("pattern role", tree.units[0].role, "pattern")
    t.equal("pattern filename", tree.filenames(), ["1_the_gate"])

    profile, detection = F.detect("notes/release.md", GENERIC_DOC)
    t.equal("generic fallback", profile.kind, F.PublicationKind.GENERIC)
    t.check("fallback states its reason",
            "no path, header or heading evidence" in detection.reasons, str(detection))
    tree = F.decompose(profile, GENERIC_DOC, "notes/release.md")
    t.equal("generic sections", tree.ids(), ["what_changed", "how_to_upgrade"])
    t.equal("generic role", {u.role for u in tree.units}, {"section"})


def test_edge_cases(t: TestRunner) -> None:
    print("\n[8] Edge cases")
    profile = F.by_key("dpf-framework")

    tree = F.decompose(profile, END_MARKER_DOC, "demo.md")
    t.equal("end marker is not a unit", len(tree.units), 2)
    t.equal("end marker ids", tree.ids(), ["DEMO.1", "DEMO.Reference:1"])
    t.check("end marker extends its unit",
            tree.units[-1].end == len(END_MARKER_DOC.splitlines()) + 1,
            f"end={tree.units[-1].end}")

    tree = F.decompose(profile, FENCE_DOC, "fenced.md")
    t.equal("fenced heading ignored", tree.ids(), ["DEMO.1"])

    empty = F.decompose(profile, "", "empty.md")
    t.equal("empty document has no units", len(empty.units), 0)

    no_docid = "# Bare\n\n## ZZ.1 - Something\n\nBody.\n"
    tree = F.decompose(profile, no_docid, "bare.md")
    t.equal("prefix inferred without DocID", tree.ids(), ["ZZ.1"])

    t.equal("colon becomes dash in filenames",
            profile.grammar.filename("MATH.Reference:3.2", "x"), "MATH.Reference-3.2")


def test_shapes(t: TestRunner) -> None:
    print("\n[9] Skill shapes")
    pattern = F.PATTERN_SKILL.outputs("fpf", ["fpf-patterns"], ["A.1", "A.2"])
    t.check("pattern shape writes a hub", "fpf/SKILL.md" in pattern, str(pattern))
    t.check("pattern shape writes unit files",
            "fpf/reference/fpf-patterns/A.1.md" in pattern, str(pattern))
    t.check("pattern shape writes agent indexes",
            "fpf/reference/pattern-index.md" in pattern, str(pattern))
    t.check("pattern shape ships tools", "fpf/scripts/" in pattern, str(pattern))

    suite = F.SUITE_SKILL.outputs("engineering", ["syse", "mnt"], ["SYSE.1"])
    t.check("suite shape fans out per framework",
            "engineering/reference/syse/SYSE.1.md" in suite
            and "engineering/reference/mnt/SYSE.1.md" in suite, str(suite))

    guide = F.GUIDE_SKILL.outputs("guide", ["guide"], ["intro"])
    t.check("guide shape writes no unit files",
            not any(p.endswith("intro.md") for p in guide), str(guide))
    t.check("guide shape writes a hub", "guide/SKILL.md" in guide, str(guide))

    reference = F.REFERENCE_SKILL.outputs("engineering-ref", ["ref"], ["Engineering.Reference-1"])
    t.check("reference shape has no pattern indexes",
            "engineering-ref/reference/pattern-index.md" not in reference,
            str(reference))


#: Names that would tie the generator to one vendor's product.  A skill tree
#: must describe the material it carries, not the site that hosts a copy of it.
VENDOR_NAMES = (
    "fpf" + ".tools", "fpf" + ".sh", "vibe" + "vm", "vibe" + "-gen",
    "ai" + ".lev", "glama",
    "claude", "chatgpt", "codex", "qwen", "gemini", "cursor",
)

#: Files the generator writes.  Copied publications are excluded on purpose:
#: a source document may name any product it likes, and editing it would break
#: the byte-identical rebuild.
GENERATED_NAMES = {
    "SKILL.md", "README.md", "boot.md", "CONNECT.md", "index.md",
    "pattern-index.md", "reference-index.md", "keyword-index.md",
    "query-index.md", "glossary.md", "entries.md", "CROSS-REFERENCES.md",
    "index.json", "sections.json", "routes.json", "entries.json",
    "packages.json",
    # Role files are generated from templates, so they are held to the same
    # rule.  Their names are also the names of the template partials, which is
    # why the copy under scripts/ is excluded below.
    "classifier.md", "retriever.md", "reasoner.md", "reviewer.md",
    "installer.md", "validator.md", "sync.md",
}


def generated_files(root: Path):
    """Every file the generator wrote, skipping the copied engine and sources.

    ``skills/*/scripts/`` holds a copy of the toolchain, templates included;
    a template is *meant* to contain placeholders.  Copied publications keep
    whatever their author wrote, including ``{{``.
    """
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if "scripts" in rel.parts:
            continue
        if path.name not in GENERATED_NAMES:
            continue
        yield path


def test_no_vendor_mentions(t: TestRunner) -> None:
    print("\n[11] Generated prose names no vendor")
    root = _REPO_ROOT / "skills"
    if not root.exists():
        t.check("skills/ built", False, "run build.sh first")
        return

    offenders: List[str] = []
    scanned = 0
    for path in generated_files(root):
        scanned += 1
        text = path.read_text("utf-8", errors="replace").lower()
        for name in VENDOR_NAMES:
            if name in text:
                offenders.append(f"{path.relative_to(root)}: {name}")

    t.check("generated files were scanned", scanned > 50, str(scanned))
    t.check("no vendor names in generated prose", not offenders, str(offenders[:6]))

    # The same rule for the toolchain's own documentation.
    doc_offenders: List[str] = []
    for name in ("README.md", "FRAMEWORKS.md"):
        path = _MAKER_DIR / name
        if not path.exists():
            continue
        text = path.read_text("utf-8").lower()
        for vendor in VENDOR_NAMES:
            if vendor in text:
                doc_offenders.append(f"{name}: {vendor}")
    t.check("no vendor names in toolchain docs", not doc_offenders,
            str(doc_offenders[:6]))


def test_portability(t: TestRunner) -> None:
    """Two Windows traps that cost a real debugging session.

    1. A subprocess writing UTF-8, decoded with the locale codec (cp1251 on a
       Russian Windows), raises ``UnicodeDecodeError`` inside the reader
       thread and leaves ``stdout`` as ``None``.
    2. ``Path.write_text`` translates ``\n`` to ``os.linesep``, so the same
       build produces different bytes on Windows.

    Both are checked statically here, because neither can fail on Linux.
    """
    print("\n[13] Portability invariants")

    call_re = re.compile(r"subprocess\.(run|Popen)\(")
    offenders: List[str] = []
    scanned = 0
    for path in sorted(_toolchain_py()):
        text = path.read_text("utf-8")
        for match in call_re.finditer(text):
            window = text[match.end():match.end() + 400]
            # Only a captured stream is decoded at all: a child that inherits
            # the terminal writes its own bytes and needs no encoding here.
            if not ("capture_output" in window or "PIPE" in window
                    or "text=True" in window):
                continue
            scanned += 1
            if "encoding=" not in window:
                line = text[:match.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line}")
    t.check("capturing subprocess calls were found", scanned >= 5, str(scanned))
    t.check("every subprocess decodes as UTF-8", not offenders, str(offenders))

    # File writes: generated output must go through write_text_lf, never
    # through Path.write_text, which is newline-translating.
    write_offenders: List[str] = []
    for path in sorted(_toolchain_py()):
        if path.name.startswith("test_"):
            continue
        for number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if ".write_text(" in line and "write_text_lf" not in line:
                write_offenders.append(f"{path.name}:{number}")
    t.check("generated files are written with LF", not write_offenders,
            str(write_offenders))

    # The corollary, checked on the bytes rather than the code: a Windows run
    # that wrote a tracked file through Path.write_text leaves it CRLF, which
    # .gitattributes calls a modification and the engine digest treats as an
    # edit -- one corrupt file invalidates every skill's build stamp.
    # ``*.cmd`` and ``*.ps1`` are excluded: .gitattributes asks for CRLF there.
    lf_offenders: List[str] = []
    lf_suffixes = (".py", ".template", ".md", ".json", ".sh")
    for path in sorted(_MAKER_DIR.rglob("*")):
        if (not path.is_file() or path.suffix not in lf_suffixes
                or "__pycache__" in path.parts):
            continue
        if b"\r\n" in path.read_bytes():
            lf_offenders.append(path.relative_to(_MAKER_DIR).as_posix())
    t.check("no tracked toolchain file carries CRLF", not lf_offenders,
            str(lf_offenders[:6]))

def test_no_unresolved_placeholders(t: TestRunner) -> None:
    """Every ``{{...}}`` the generator emits must have been filled in.

    The old check looked at SKILL.md only, so an unfilled placeholder in a
    role file, a genre block or boot.md would ship unnoticed -- and a reader
    would see ``{{FRAMEWORK_NOUN}}`` where a word belongs.
    """
    print("\n[12] No unresolved placeholders in generated files")
    root = _REPO_ROOT / "skills"
    if not root.exists():
        t.check("skills/ built", False, "run build.sh first")
        return

    offenders: List[str] = []
    scanned = 0
    for path in generated_files(root):
        scanned += 1
        text = path.read_text("utf-8", errors="replace")
        for token in re.findall(r"\{\{[A-Z_]+\}\}", text):
            offenders.append(f"{path.relative_to(root)}: {token}")

    t.check("generated files were scanned for placeholders", scanned > 50,
            str(scanned))
    t.check("no unresolved placeholder survives", not offenders,
            str(sorted(set(offenders))[:6]))


# ---------------------------------------------------------------------------
# 5. CLI
# ---------------------------------------------------------------------------

def test_cli(t: TestRunner) -> None:
    print("\n[10] CLI")
    cli = str(_SCRIPT_DIR / "fpf_frameworks.py")

    def run(*args: str) -> subprocess.CompletedProcess:
        # Explicit UTF-8: see test_fpf_pipeline.run_cmd.
        return subprocess.run([sys.executable, cli, *args],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              cwd=str(_REPO_ROOT))

    for sub in ("kinds", "profiles"):
        r = run(sub)
        t.check(f"{sub} exits 0", r.returncode == 0, r.stderr[:300])
        t.check(f"{sub} produces output", bool(r.stdout.strip()), "empty")

    r = run("probe", "DPFs/README.md")
    t.check("probe exits 0", r.returncode == 0, r.stderr[:300])
    t.check("probe reports Guide", "Guide" in r.stdout, r.stdout[:300])

    r = run("tree", "DPFs/README.md")
    t.check("tree exits 0", r.returncode == 0, r.stderr[:300])

    r = run("plan", "DPFs/README.md", "--skill", "guide")
    t.check("plan exits 0", r.returncode == 0, r.stderr[:300])
    t.check("plan lists artefacts", "Would produce" in r.stdout, r.stdout[:300])

    r = run("catalogue", "--verify", "--offline", "--counts")
    t.check("catalogue --verify --offline exits 0", r.returncode == 0,
            (r.stdout + r.stderr)[-500:])
    t.check("catalogue agrees with publisher", "agree with the publisher" in r.stdout,
            r.stdout[-300:])

    r = run("probe", "does-not-exist.md")
    t.check("probe reports a missing file", r.returncode == 1, str(r.returncode))


# ---------------------------------------------------------------------------

def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    print("=" * 60)
    print("Framework Decomposition -- Tests")
    print("=" * 60)

    t = TestRunner(verbose=verbose)
    test_kinds(t)
    test_registry(t)
    test_catalogue(t)
    test_snapshot(t)
    test_decomposition(t)
    test_engine_agreement(t)
    test_extension_kinds(t)
    test_edge_cases(t)
    test_shapes(t)
    test_cli(t)
    test_no_vendor_mentions(t)
    test_no_unresolved_placeholders(t)
    test_portability(t)
    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
