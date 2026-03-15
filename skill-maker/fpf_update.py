#!/usr/bin/env python3
"""
fpf_update.py — Self-update pipeline for FPF skill.

Downloads latest spec from GitHub, splits into skill, audits, tests.

Usage from repo root:
    python skill-maker/fpf_update.py                  # full: download + split + audit + test
    python skill-maker/fpf_update.py --no-download     # re-split from local files
    python skill-maker/fpf_update.py --download-only    # just download, don't build
    python skill-maker/fpf_update.py --test-only        # just run tests

Exit codes: 0 = all OK, 1 = download error, 2 = split error, 3 = audit error, 4 = test error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

SPEC_URL = "https://github.com/ailev/FPF/raw/refs/heads/main/FPF-Spec.md"
README_URL = "https://github.com/ailev/FPF/raw/refs/heads/main/Readme.md"

SPEC_PATH = _REPO_ROOT / "FPF-Spec.md"
README_PATH = _REPO_ROOT / "Readme.md"
SKILL_DIR = _REPO_ROOT / "skills" / "fpf"


def _print(msg: str, symbol: str = "•"):
    print(f"  {symbol} {msg}")


def download_file(url: str, dest: Path) -> bool:
    """Download a file from URL. Returns True on success."""
    _print(f"Downloading {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fpf-update/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        dest.write_bytes(data)
        _print(f"  → {dest} ({len(data)} bytes)", "✓")
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        _print(f"  → FAILED: {e}", "✗")
        return False


def step_download() -> bool:
    """Download latest FPF-Spec.md and Readme.md."""
    print("\n[1/4] Downloading latest spec from GitHub...")
    ok1 = download_file(SPEC_URL, SPEC_PATH)
    ok2 = download_file(README_URL, README_PATH)
    if not ok1:
        _print("FPF-Spec.md download failed — cannot continue", "✗")
        return False
    if not ok2:
        _print("Readme.md download failed — will use existing or skip", "⚠")
    return True


def step_split() -> bool:
    """Run split_fpf_spec.py split."""
    print("\n[2/4] Splitting spec into skill...")
    if not SPEC_PATH.exists():
        _print(f"{SPEC_PATH} not found", "✗")
        return False
    cmd = [
        sys.executable, str(_SCRIPT_DIR / "split_fpf_spec.py"),
        "split",
        "--source", str(SPEC_PATH),
        "--output", str(SKILL_DIR),
    ]
    if README_PATH.exists():
        cmd += ["--readme", str(README_PATH)]
    result = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    if result.returncode != 0:
        _print("Split failed", "✗")
        return False
    _print("Split complete", "✓")
    return True


def step_audit() -> bool:
    """Run audit_fpf_patterns.py."""
    print("\n[3/4] Running audit...")
    cmd = [
        sys.executable, str(_SCRIPT_DIR / "audit_fpf_patterns.py"),
        "--source", str(SPEC_PATH),
        "--skill-dir", str(SKILL_DIR),
    ]
    result = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    if result.returncode != 0:
        _print("Audit found issues (see above)", "⚠")
        return False
    _print("Audit passed", "✓")
    return True


def step_test() -> bool:
    """Run test_fpf_pipeline.py."""
    print("\n[4/4] Running tests...")
    test_script = _SCRIPT_DIR / "test_fpf_pipeline.py"
    if not test_script.exists():
        _print(f"{test_script} not found — skipping tests", "⚠")
        return True
    result = subprocess.run(
        [sys.executable, str(test_script)],
        cwd=str(_REPO_ROOT),
    )
    if result.returncode != 0:
        _print("Tests failed (see above)", "✗")
        return False
    _print("Tests passed", "✓")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="FPF Skill self-update pipeline")
    ap.add_argument("--no-download", action="store_true", help="Skip download, use local files")
    ap.add_argument("--download-only", action="store_true", help="Only download, don't build")
    ap.add_argument("--test-only", action="store_true", help="Only run tests")
    ap.add_argument("--skip-test", action="store_true", help="Skip tests after build")
    args = ap.parse_args()

    print("=" * 60)
    print("FPF Skill — Self-Update Pipeline")
    print("=" * 60)

    if args.test_only:
        return 0 if step_test() else 4

    if not args.no_download:
        if not step_download():
            return 1

    if args.download_only:
        print("\n✓ Download complete. Run without --download-only to build.")
        return 0

    if not step_split():
        return 2

    if not step_audit():
        # Audit warnings are non-fatal for build, but we report them
        _print("Audit reported issues — build continues", "⚠")

    if not args.skip_test:
        if not step_test():
            return 4

    print("\n" + "=" * 60)
    print("✅ FPF Skill update complete")
    print(f"   Skill directory: {SKILL_DIR}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
