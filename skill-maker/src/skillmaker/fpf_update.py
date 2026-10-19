#!/usr/bin/env python3
"""
fpf_update.py — Self-update pipeline for the FPF skill.

Downloads the current Core specification and the Library documents from GitHub,
splits them into the skill, audits and tests the result.

The FPF skill carries four source documents:

    FPF-Spec.md                Core patterns (A–K) + embedded Architectural Reference
    USING-FPF.md               Library working instruction
    FPF-LIBRARY-REFERENCE.md   Library Architectural Reference
    Readme.md                  Library landing page

Usage from repo root:
    python skill-maker/src/skillmaker/fpf_update.py                  # download + split + audit + test
    python skill-maker/src/skillmaker/fpf_update.py --no-download     # re-split from local files
    python skill-maker/src/skillmaker/fpf_update.py --download-only   # just download, don't build
    python skill-maker/src/skillmaker/fpf_update.py --test-only       # just run tests
    python skill-maker/src/skillmaker/fpf_update.py --dpfs            # also refresh every DPF file

Exit codes: 0 = all OK, 1 = download error, 2 = split error, 3 = audit error,
4 = test error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
_MAKER_DIR = _PKG_PARENT.parent           # skill-maker/
_REPO_ROOT = _MAKER_DIR.parent            # repository root
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

_BASE = "https://github.com/ailev/FPF/raw/refs/heads/main/"

#: Root documents of the Library that the FPF skill ships.
LIBRARY_DOCS = [
    ("FPF-Spec.md", True),
    ("Readme.md", False),
    ("USING-FPF.md", True),
    ("FPF-LIBRARY-REFERENCE.md", True),
]

SKILL_DIR = _REPO_ROOT / "skills" / "fpf"


def _print(msg: str, symbol: str = "•"):
    print(f"  {symbol} {msg}")


def download_file(url: str, dest: Path) -> bool:
    """Download a file from URL. Returns True on success."""
    _print(f"Downloading {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fpf-update/1.1"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        _print(f"  → {dest.relative_to(_REPO_ROOT)} ({len(data)} bytes)", "✓")
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        _print(f"  → FAILED: {e}", "✗")
        return False


def _dpf_sources() -> list:
    """Every DPF source file known to the skill configs."""
    from skillmaker.skill_config import ALL_DPFS
    return [d.source for d in ALL_DPFS]


def step_download(with_dpfs: bool = False) -> bool:
    """Download the Core specification and the Library documents."""
    print("\n[1/4] Downloading the latest Library sources from GitHub...")
    ok_required = True
    for name, required in LIBRARY_DOCS:
        ok = download_file(_BASE + name, _REPO_ROOT / name)
        if required and not ok:
            ok_required = False
    if with_dpfs:
        for path in _dpf_sources():
            rel = path.relative_to(_REPO_ROOT).as_posix()
            url = _BASE + rel.replace(" ", "%20")
            if not download_file(url, path):
                _print(f"DPF download failed: {rel}", "⚠")
    if not ok_required:
        _print("A required source could not be downloaded — cannot continue", "✗")
        return False
    return True


def _run(cmd: list) -> int:
    return subprocess.run(cmd, cwd=str(_REPO_ROOT)).returncode


def step_split() -> bool:
    """Run split_fpf_spec.py split."""
    print("\n[2/4] Splitting the Core specification into the skill...")
    spec = _REPO_ROOT / "FPF-Spec.md"
    if not spec.exists():
        _print(f"{spec} not found", "✗")
        return False
    rc = _run([sys.executable, str(_SCRIPT_DIR / "split_fpf_spec.py"),
               "split", "--source", str(spec), "--output", str(SKILL_DIR)])
    if rc != 0:
        _print("Split failed", "✗")
        return False
    _print("Split complete", "✓")
    return True


def step_audit() -> bool:
    """Run audit_fpf_patterns.py."""
    print("\n[3/4] Running the audit...")
    rc = _run([sys.executable, str(_SCRIPT_DIR / "audit_fpf_patterns.py"),
               "--source", str(_REPO_ROOT / "FPF-Spec.md"),
               "--skill-dir", str(SKILL_DIR)])
    if rc != 0:
        _print("Audit found issues (see above)", "⚠")
        return False
    _print("Audit passed", "✓")
    return True


def step_test() -> bool:
    """Run test_fpf_pipeline.py."""
    print("\n[4/4] Running the tests...")
    test_script = _MAKER_DIR / "tests" / "test_fpf_pipeline.py"
    if not test_script.exists():
        _print(f"{test_script} not found — skipping tests", "⚠")
        return True
    rc = _run([sys.executable, str(test_script)])
    if rc != 0:
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
    ap.add_argument("--dpfs", action="store_true",
                    help="Also refresh every DPF source file in DPFs/")
    args = ap.parse_args()

    print("=" * 60)
    print("FPF Skill — Self-Update Pipeline")
    print("=" * 60)

    if args.test_only:
        return 0 if step_test() else 4

    if not args.no_download:
        if not step_download(with_dpfs=args.dpfs):
            return 1

    if args.download_only:
        print("\n✓ Download complete. Run without --download-only to build.")
        return 0

    if not step_split():
        return 2

    if not step_audit():
        _print("Audit reported issues — build continues", "⚠")

    if not args.skip_test:
        if not step_test():
            return 4

    print("\n" + "=" * 60)
    print("✅ FPF Skill update complete")
    print(f"   Skill directory: {SKILL_DIR.relative_to(_REPO_ROOT)}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
