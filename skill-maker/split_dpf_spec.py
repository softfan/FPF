#!/usr/bin/env python3
"""
split_dpf_spec.py -- DPF skill splitter (thin wrapper).

Delegates to the generic config-driven engine (``split_spec.py``) using the
configs in ``skill_config.py``:

* ``SUITE_SKILL_CONFIGS`` -- one skill per DPF Suite (Engineering, Management,
  Foundational Thinking, Human Capability Engineering).  Each holds its
  constituent frameworks plus the Suite Architectural Reference.
* ``DPF_SKILL_CONFIGS`` -- one skill per standalone DPF published directly in
  ``DPFs/`` (PSDA, RMP, EXD, NSTD, IS, ECO, FDM, DTM, RHY, MDPE).

Usage (from the repository root):

    split    [--suite SLUG] [--framework DOCID] [--all] [--output DIR]
    analyze  [--suite SLUG] [--framework DOCID] [--all]
    rebuild  --skill-dir DIR --output OUT.md

With no selector, everything is built.  ``--output`` is only meaningful when a
single skill is selected.

Exit codes: 0 = success, 1 = parse error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _fpf_common import ensure_utf8_stdio  # noqa: E402
from skill_config import (  # noqa: E402
    ALL_DPF_CONFIGS, DPF_SKILL_CONFIGS, SUITE_SKILL_CONFIGS,
)
from split_spec import analyze, build_skill, print_stats, rebuild_spec  # noqa: E402

ensure_utf8_stdio()


def _suite_by_name(name: str):
    """Accept ``engineering`` or ``engineering-suite``."""
    for key, cfg in SUITE_SKILL_CONFIGS.items():
        if name in (key, cfg.name):
            return cfg
    raise SystemExit(f"Error: unknown suite '{name}'. Known: "
                     + ", ".join(sorted({k for k in SUITE_SKILL_CONFIGS} |
                                        {c.name for c in SUITE_SKILL_CONFIGS.values()})))


def _framework_by_name(name: str):
    """Accept a DocID (``PSDA``) or the skill name (``decision-design``)."""
    for key, cfg in DPF_SKILL_CONFIGS.items():
        if name.lower() in (key.lower(), cfg.name.lower()):
            return cfg
    raise SystemExit(f"Error: unknown framework '{name}'. Known DocIDs: "
                     + ", ".join(sorted(DPF_SKILL_CONFIGS)))


def _select(args) -> list:
    if args.suite:
        cfg = _suite_by_name(args.suite)
        return [(cfg.name, cfg)]
    if args.framework:
        cfg = _framework_by_name(args.framework)
        return [(cfg.name, cfg)]
    return sorted(ALL_DPF_CONFIGS.items())


def main() -> int:
    ap = argparse.ArgumentParser(prog="split_dpf_spec")
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("split")
    s.add_argument("--suite", default=None,
                   help="Build one Suite skill (engineering or engineering-suite)")
    s.add_argument("--framework", default=None,
                   help="Build one standalone DPF skill (PSDA or decision-design)")
    s.add_argument("--all", action="store_true", help="Build every DPF skill (default)")
    s.add_argument("--output", type=Path, default=None,
                   help="Override output dir (single skill only)")
    s.add_argument("--views", action="store_true",
                   help="Also write contract views (working sections only)")

    a = sub.add_parser("analyze")
    a.add_argument("--suite", default=None)
    a.add_argument("--framework", default=None)
    a.add_argument("--all", action="store_true")

    sub.add_parser("stats")

    r = sub.add_parser("rebuild")
    r.add_argument("--skill-dir", required=True, type=Path)
    r.add_argument("--output", required=True, type=Path)

    args = ap.parse_args()

    if args.cmd == "split":
        selected = _select(args)
        if args.output is not None and len(selected) > 1:
            print("Error: --output needs a single --suite/--framework selection",
                  file=sys.stderr)
            return 1
        for name, cfg in selected:
            print(f"\n=== {name} ===")
            rc = build_skill(cfg, output=args.output,
                             emit_views=True if args.views else None)
            if rc != 0:
                return rc
        return 0

    if args.cmd == "analyze":
        for name, cfg in _select(args):
            print(f"\n=== {name} ===")
            analyze(cfg)
        return 0

    if args.cmd == "stats":
        return print_stats(sorted(ALL_DPF_CONFIGS.items()))

    if args.cmd == "rebuild":
        name = args.skill_dir.name
        if name not in ALL_DPF_CONFIGS:
            print(f"Error: unknown skill dir {args.skill_dir}", file=sys.stderr)
            return 1
        cfg = ALL_DPF_CONFIGS[name]
        cfg.output = args.skill_dir
        rebuild_spec(cfg, args.output)
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
