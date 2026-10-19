#!/usr/bin/env python3
"""
split_dpf_spec.py -- DPF skill splitter (thin wrapper).

Delegates to the generic config-driven engine (``split_spec.py``) using the
curated configs in ``skill_config.py`` plus local discovery:

* curated Suite and standalone configs -- stable names and descriptions for
  sources that are present;
* ``discover_skills`` -- new DPFs and Suites, including new members of existing
  Suites, without changing the curated catalogue.

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
_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402
from skillmaker.split_spec import analyze, build_skill, print_stats, rebuild_spec  # noqa: E402

ensure_utf8_stdio()


def _configs():
    from skillmaker.discover_skills import discover

    return {name: cfg for name, cfg in discover().configs.items()
            if name != "fpf" and any(fw.source.is_relative_to(_SCRIPT_DIR.parents[2] / "DPFs")
                                     for fw in cfg.frameworks)}


def _suite_by_name(name: str):
    """Accept ``engineering`` or ``engineering-suite``."""
    configs = {key: cfg for key, cfg in _configs().items() if cfg.kind_label == "DPF Suite"}
    for key, cfg in configs.items():
        if name in (key.removesuffix("-suite"), cfg.name):
            return cfg
    raise SystemExit(f"Error: unknown suite '{name}'. Known: "
                     + ", ".join(sorted(configs)))


def _framework_by_name(name: str):
    """Accept a DocID (``PSDA``) or the skill name (``decision-design``)."""
    configs = {key: cfg for key, cfg in _configs().items() if cfg.kind_label != "DPF Suite"}
    for cfg in configs.values():
        if name.lower() in (cfg.prefix_token.lower(), cfg.name.lower()):
            return cfg
    raise SystemExit(f"Error: unknown framework '{name}'. Known DocIDs: "
                     + ", ".join(sorted(configs)))


def _select(args) -> list:
    if args.suite:
        cfg = _suite_by_name(args.suite)
        return [(cfg.name, cfg)]
    if args.framework:
        cfg = _framework_by_name(args.framework)
        return [(cfg.name, cfg)]
    return sorted(_configs().items())


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
        if not selected:
            print("Error: no DPF frameworks or Suites were discovered", file=sys.stderr)
            return 1
        from skillmaker.discover_skills import Discovery, validate_outputs

        if args.output is not None:
            selected[0][1].output = args.output
        validate_outputs(Discovery(dict(selected)))
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
        return print_stats(sorted(_configs().items()))

    if args.cmd == "rebuild":
        name = args.skill_dir.name
        configs = _configs()
        if name not in configs:
            print(f"Error: unknown skill dir {args.skill_dir}", file=sys.stderr)
            return 1
        cfg = configs[name]
        cfg.output = args.skill_dir
        try:
            rebuild_spec(cfg, args.output)
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
