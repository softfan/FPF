#!/usr/bin/env python3
"""
split_fpf_spec.py -- FPF skill splitter (thin wrapper).

Delegates to the generic config-driven engine (``split_spec.py``) using
``FPF_CONFIG``.  The FPF skill carries the Core specification plus the Library
documents ``USING-FPF.md``, ``FPF-LIBRARY-REFERENCE.md`` and ``Readme.md``.

    split   --source FPF-Spec.md --output skills/fpf [--intro-split h1|h2]
    analyze --source FPF-Spec.md
    rebuild --skill-dir skills/fpf --output OUT.md [--include-docs]
    diff    --source FPF-Spec.md --skill-dir skills/fpf

Exit codes: 0 = success, 1 = parse error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import ensure_utf8_stdio, id_to_filename, sha256, sort_key  # noqa: E402
from skillmaker.skill_config import FPF_CONFIG  # noqa: E402
from skillmaker.split_spec import (  # noqa: E402
    SpecParser, analyze, build_skill, print_stats, rebuild_spec,
)

ensure_utf8_stdio()


def _diff(args) -> int:
    cfg = FPF_CONFIG
    if args.source:
        cfg.frameworks[0].source = args.source
    p = SpecParser(cfg, cfg.frameworks[0])
    p.parse()
    pdir = args.skill_dir / "reference" / cfg.frameworks[0].key
    new = {c.id: c for c in p.chunks if c.kind == "unit"}
    old = {f.stem for f in pdir.glob("*.md") if f.name != "index.md"} if pdir.exists() else set()
    new_stems = {id_to_filename(pid) for pid in new}
    added = sorted(new_stems - old)
    removed = sorted(old - new_stems)
    changed = []
    for pid, chunk in new.items():
        f = pdir / (id_to_filename(pid) + ".md")
        if f.exists() and sha256(chunk.content) != sha256(f.read_text("utf-8")):
            changed.append(pid)
    print(f"Added: {len(added)}, Removed: {len(removed)}, Changed: {len(changed)}, "
          f"Unchanged: {len(new_stems & old) - len(changed)}")
    for x in added:
        print(f"  + {x}")
    for x in removed:
        print(f"  - {x}")
    for x in sorted(changed, key=sort_key):
        print(f"  ~ {x}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="split_fpf_spec")
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("split")
    s.add_argument("--source", type=Path, default=None)
    s.add_argument("--output", required=True, type=Path)
    s.add_argument("--intro-split", choices=["h1", "h2"], default=None)
    s.add_argument("--views", action="store_true",
                   help="Also write contract views (working sections only)")

    a = sub.add_parser("analyze")
    a.add_argument("--source", type=Path, default=None)

    r = sub.add_parser("rebuild")
    r.add_argument("--skill-dir", required=True, type=Path)
    r.add_argument("--output", required=True, type=Path)
    r.add_argument("--include-docs", action="store_true",
                   help="Also concatenate the Library documents")

    sub.add_parser("stats")

    d = sub.add_parser("diff")
    d.add_argument("--source", type=Path, default=None)
    d.add_argument("--skill-dir", required=True, type=Path)

    args = ap.parse_args()

    if args.cmd == "split":
        return build_skill(FPF_CONFIG, output=args.output,
                           source_override=args.source,
                           intro_split=args.intro_split,
                           emit_views=True if args.views else None)
    if args.cmd == "analyze":
        if args.source:
            FPF_CONFIG.frameworks[0].source = args.source
        analyze(FPF_CONFIG)
        return 0
    if args.cmd == "rebuild":
        FPF_CONFIG.output = args.skill_dir
        try:
            rebuild_spec(FPF_CONFIG, args.output, include_docs=args.include_docs)
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.cmd == "stats":
        return print_stats([("fpf", FPF_CONFIG)])

    if args.cmd == "diff":
        return _diff(args)

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
