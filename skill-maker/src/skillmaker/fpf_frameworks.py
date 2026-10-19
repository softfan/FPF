#!/usr/bin/env python3
"""
fpf_frameworks.py -- inspect and plan framework decompositions.

The toolchain has two builders (``split_fpf_spec.py``, ``split_dpf_spec.py``)
that emit skills, and this command, which answers the question they cannot:
*what is in this document, and what would decomposing it produce?*  It works on
any framework kind, including ones FPF Library does not publish.

Subcommands::

    kinds                    the publication-kind vocabulary
    profiles                 the registered decomposition profiles
    catalogue                the register of publications, local and published
    probe PATH...            classify a document and show the evidence
    tree PATH                list its addressable units
    plan PATH                the artefacts a decomposition would produce

Examples::

    python skill-maker/src/skillmaker/fpf_frameworks.py catalogue --verify
    python skill-maker/src/skillmaker/fpf_frameworks.py probe DPFs/README.md
    python skill-maker/src/skillmaker/fpf_frameworks.py tree FPF-Spec.md --limit 10
    python skill-maker/src/skillmaker/fpf_frameworks.py plan DPFs/README.md --skill guide

Exit codes: 0 = success, 1 = verification failed or a document did not decompose.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import urllib.error
from pathlib import Path
from typing import List, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
_MAKER_DIR = _PKG_PARENT.parent           # skill-maker/
_REPO_ROOT = _MAKER_DIR.parent            # repository root
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

from skillmaker import frameworks as F  # noqa: E402

#: Saved copy of the publisher catalogue, used for offline verification.
SNAPSHOT = _SCRIPT_DIR / "catalogue.snapshot.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text("utf-8", errors="replace")


def _resolve(arg: str) -> Path:
    """Resolve a CLI path argument against the working directory."""
    candidate = Path(arg)
    if candidate.exists():
        return candidate
    return _REPO_ROOT / arg


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _rule(char: str = "-", width: int = 78) -> str:
    return char * width


def _decompose(path: Path):
    text = _read(path)
    rel = _rel(path)
    profile, detection = F.detect(rel, text)
    tree = F.decompose(profile, text, rel)
    return tree, detection


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_kinds(_args) -> int:
    print("Publication kinds")
    print(_rule("="))
    print(f"{'kind':<16} {'label':<32} {'flags':<26} what a reader gets")
    print(_rule())
    for kind in F.PublicationKind:
        print(F.describe_kind(kind))
    print()
    print(f"{len(F.CATALOGUE_KINDS)} kinds are published by FPF Library "
          f"({', '.join(F.CATALOGUE_KINDS)});")
    print("the others are extension kinds this toolchain can already decompose.")
    return 0


def cmd_profiles(_args) -> int:
    print("Decomposition profiles (most specific first)")
    print(_rule("="))
    print(f"{'key':<20} {'kind':<16} {'layout':<11} produces")
    print(_rule())
    for profile in F.all_profiles():
        print(profile.describe())
    print()
    print("Add a kind: create frameworks/profiles/<name>.py exporting PROFILE,")
    print("then list it in frameworks/profiles/__init__.py.  Nothing else changes.")
    return 0


def cmd_catalogue(args) -> int:
    local = F.load_local(_REPO_ROOT, classify=F.classify)
    if args.verify and not args.counts:
        # Comparing pattern counts is the point of --verify, so it implies the
        # decomposition that produces them.
        args.counts = True
    if args.counts:
        measured = []
        for pub in local:
            tree, _ = _decompose(_REPO_ROOT / pub.path)
            measured.append(dataclasses.replace(
                pub, patterns=len(tree.patterns), sections=tree.headings))
        local = measured

    if args.json:
        payload = {
            "repo_root": str(_REPO_ROOT),
            "publications": [p.to_dict() for p in local],
            "kinds": F.summarise(local),
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Local publications under {_REPO_ROOT}")
    print(_rule("="))
    print(f"{'kind':<11} {'patterns':>8} {'sections':>8}  path")
    print(_rule())
    for pub in local:
        print(f"{pub.kind:<11} {pub.patterns:>8} {pub.sections:>8}  {pub.path}")
    print(_rule())
    counts = F.summarise(local)
    total = sum(pub.patterns for pub in local)
    print(f"{len(local)} publications: "
          + ", ".join(f"{k} {v}" for k, v in counts.items())
          + f"; {total} patterns")

    if not (args.verify or args.remote):
        print("\n(--verify compares against the publisher catalogue; "
              "--counts fills in pattern counts)")
        return 0

    remote: Optional[List[F.Publication]] = None
    meta = {}
    if args.offline:
        if not SNAPSHOT.exists():
            print(f"\nNo snapshot at {SNAPSHOT}; cannot verify offline.", file=sys.stderr)
            return 1
        remote, meta = F.load_snapshot(SNAPSHOT)
        print(f"\nPublisher snapshot: {meta.get('snapshot', '?')} "
              f"({meta.get('count')} publications, saved copy)")
    else:
        try:
            remote, meta = F.load_remote()
            print(f"\nPublisher catalogue: {meta.get('snapshot', '?')} "
                  f"({meta.get('count')} publications, live)")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"\nCould not reach {F.REMOTE_URL}: {exc}", file=sys.stderr)
            if SNAPSHOT.exists():
                remote, meta = F.load_snapshot(SNAPSHOT)
                print(f"Falling back to the saved snapshot "
                      f"{meta.get('snapshot', '?')}.", file=sys.stderr)
            else:
                return 1

    issues = F.verify(local, remote)
    if not issues:
        print(f"\n\u2705 {len(local)} publications agree with the publisher "
              f"(kind and pattern count).")
        return 0
    print(f"\n\u274c {len(issues)} disagreement(s):")
    for issue in issues:
        print(f"  {issue.describe()}")
    return 1


def cmd_probe(args) -> int:
    rc = 0
    for arg in args.paths:
        path = _resolve(arg)
        if not path.exists():
            print(f"not found: {arg}", file=sys.stderr)
            rc = 1
            continue
        tree, detection = _decompose(path)
        profile = tree.profile
        print(_rule("="))
        print(f"{tree.path}")
        print(_rule("="))
        print(f"  title      {tree.title or '(none)'}")
        print(f"  kind       {profile.kind.value} -- {profile.kind_info().label}")
        print(f"  profile    {profile.key} ({profile.name})")
        print(f"  evidence   {', '.join(detection.reasons)} (score {detection.score})")
        print(f"  grammar    {tree.grammar.describe()}")
        print(f"  shape      {profile.shape.describe()}")
        print(f"  units      {len(tree.units)} "
              f"({len(tree.patterns)} patterns, {len(tree.references)} other)")
        if tree.by_role():
            print("  roles      " + ", ".join(f"{k}={v}" for k, v in tree.by_role().items()))
        if tree.parts:
            print(f"  parts      {len(tree.parts)}")
        print(f"  headings   {tree.headings} in {tree.line_count} lines")
        if args.all:
            print("  scores:")
            for candidate, det in F.detect_all(tree.path, _read(path)):
                print(f"    {candidate.key:<20} {det.score:>5}  {', '.join(det.reasons)}")
    return rc


def cmd_tree(args) -> int:
    path = _resolve(args.path)
    if not path.exists():
        print(f"not found: {args.path}", file=sys.stderr)
        return 1
    tree, _ = _decompose(path)
    units = tree.patterns if args.role == "pattern" else tree.units
    print(f"{tree.path} -- {tree.profile.kind.value}, {len(units)} unit(s)"
          + (f" (showing {args.limit})" if args.limit else ""))
    print(_rule())
    for index, unit in enumerate(units, 1):
        if args.limit and index > args.limit:
            print(f"  ... {len(units) - args.limit} more")
            break
        name = tree.grammar.filename(unit.id, unit.title)
        print(f"  {unit.id:<34} {unit.role:<12} {name}.md")
        print(f"  {'':<34} {unit.title[:80]}")
    return 0


def cmd_plan(args) -> int:
    path = _resolve(args.path)
    if not path.exists():
        print(f"not found: {args.path}", file=sys.stderr)
        return 1
    tree, _ = _decompose(path)
    shape = tree.profile.shape
    skill = args.skill or tree.profile.key
    outputs = shape.outputs(skill, framework_keys=[skill],
                            unit_names=tree.filenames())

    print(f"Plan for {tree.path}")
    print(_rule("="))
    print(f"  kind     {tree.profile.kind.value}")
    print(f"  profile  {tree.profile.key}")
    print(f"  shape    {shape.describe()}")
    print(f"  units    {len(tree.units)} ({len(tree.patterns)} patterns)")
    print()
    print(f"Would produce {len(outputs)} artefact(s):")
    for item in outputs:
        print(f"  {item}")
    if args.json:
        print()
        print(json.dumps({"tree": tree.stats(), "outputs": outputs}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fpf_frameworks.py",
        description="Inspect and plan decompositions of framework documents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("kinds", help="list publication kinds").set_defaults(func=cmd_kinds)
    sub.add_parser("profiles", help="list decomposition profiles").set_defaults(func=cmd_profiles)

    p = sub.add_parser("catalogue", help="list publications and verify against a catalogue")
    p.add_argument("--verify", action="store_true",
                   help="compare kind and pattern counts with the publisher")
    p.add_argument("--remote", action="store_true", help="fetch the publisher catalogue")
    p.add_argument("--offline", action="store_true",
                   help="verify against the saved snapshot instead of the network")
    p.add_argument("--counts", action="store_true",
                   help="decompose each publication to fill in pattern counts")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_catalogue)

    p = sub.add_parser("probe", help="classify documents and show the evidence")
    p.add_argument("paths", nargs="+")
    p.add_argument("--all", action="store_true", help="show every profile's score")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("tree", help="list the addressable units of a document")
    p.add_argument("path")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--role", choices=("all", "pattern"), default="all")
    p.set_defaults(func=cmd_tree)

    p = sub.add_parser("plan", help="show the artefacts a decomposition would produce")
    p.add_argument("path")
    p.add_argument("--skill", default="", help="skill directory name to plan for")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_plan)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
