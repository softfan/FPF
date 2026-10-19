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

Exit codes: 0 = completed (audit warnings are non-fatal), 1 = download error,
2 = split/index error, 4 = test error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
_MAKER_DIR = _PKG_PARENT.parent           # skill-maker/
_REPO_ROOT = _MAKER_DIR.parent            # repository root
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

#: Root documents of the Library that the FPF skill ships.
LIBRARY_DOCS = [
    ("FPF-Spec.md", True),
    ("Readme.md", True),
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
            data = resp.read(64 * 1024 * 1024 + 1)
        if not data.strip() or len(data) > 64 * 1024 * 1024:
            raise ValueError("publication is empty or exceeds the 64 MiB download limit")
        data.decode("utf-8")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        _print(f"  → {dest.name} ({len(data)} bytes)", "✓")
        return True
    except (urllib.error.URLError, OSError, ValueError) as e:
        _print(f"  → FAILED: {e}", "✗")
        return False


def _dpf_sources() -> list:
    """DPFs, Suite References and catalogue pages used by local verification."""
    return sorted((_REPO_ROOT / "DPFs").rglob("*.md"))


def _resolve_revision() -> str:
    """Resolve main once so all downloads belong to the same upstream edition."""
    request = urllib.request.Request(
        "https://api.github.com/repos/ailev/FPF/commits/main",
        headers={"User-Agent": "fpf-update/1.2", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        revision = json.load(response)["sha"]
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("upstream returned an invalid commit SHA")
    return revision


def step_download(with_dpfs: bool = False) -> bool:
    """Download the Core specification and the Library documents."""
    print("\n[1/4] Downloading the latest Library sources from GitHub...")
    sources = [_REPO_ROOT / name for name, _ in LIBRARY_DOCS]
    if with_dpfs:
        sources.extend(_dpf_sources())
    root = _REPO_ROOT.resolve()
    for path in sources:
        if (path.is_symlink() or not path.resolve().is_relative_to(root)
                or (path.exists() and not path.is_file())):
            _print(f"Refusing unsafe publication destination: {path}", "✗")
            return False
    try:
        revision = _resolve_revision()
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as exc:
        _print(f"Cannot pin upstream edition: {exc}", "✗")
        return False
    base = f"https://raw.githubusercontent.com/ailev/FPF/{revision}/"
    # A failed download never replaces any local publication. Readme is required
    # too: shipping different Library editions together is not a valid update.
    preferred = Path("/tmp/opencode")
    with tempfile.TemporaryDirectory(prefix="fpf-update-",
                                     dir=preferred if preferred.is_dir() else None) as temporary:
        stage = Path(temporary)
        for path in sources:
            rel = path.relative_to(_REPO_ROOT)
            if not download_file(base + rel.as_posix().replace(" ", "%20"), stage / rel):
                _print("Download failed — local sources left unchanged", "✗")
                return False
        try:
            originals = {path: path.read_bytes() if path.exists() else None for path in sources}
        except OSError as exc:
            _print(f"Cannot read existing sources; nothing replaced: {exc}", "✗")
            return False
        replaced = []
        try:
            for path in sources:
                path.parent.mkdir(parents=True, exist_ok=True)
                # Include the file being attempted: write_bytes can truncate
                # before raising, so that file also needs rollback.
                replaced.append(path)
                path.write_bytes((stage / path.relative_to(_REPO_ROOT)).read_bytes())
        except OSError as exc:
            failures = []
            for path in reversed(replaced):
                data = originals[path]
                try:
                    if data is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_bytes(data)
                except OSError as rollback_error:
                    failures.append(f"{path}: {rollback_error}")
            if failures:
                recovery = Path(tempfile.mkdtemp(prefix="fpf-update-recovery-",
                                dir=preferred if preferred.is_dir() else None))
                for path, data in originals.items():
                    if data is not None:
                        backup = recovery / path.relative_to(_REPO_ROOT)
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        backup.write_bytes(data)
                _print(f"Rollback incomplete; original bytes saved in {recovery}: "
                       + "; ".join(failures), "✗")
            else:
                _print(f"Cannot replace sources; restored previous bytes: {exc}", "✗")
            return False
    _print(f"Updated sources to commit {revision}", "✓")
    return True


def _run(cmd: list) -> int:
    return subprocess.run(cmd, cwd=str(_REPO_ROOT)).returncode


def step_split(with_dpfs: bool = False) -> bool:
    """Run split_fpf_spec.py split."""
    print("\n[2/4] Splitting the Core specification into the skill...")
    spec = _REPO_ROOT / "FPF-Spec.md"
    if not spec.exists():
        _print(f"{spec} not found", "✗")
        return False
    rc = _run([sys.executable, str(_SCRIPT_DIR / "split_fpf_spec.py"),
               "split", "--source", str(spec), "--output", str(SKILL_DIR), "--views"])
    if rc != 0:
        _print("Split failed", "✗")
        return False
    if with_dpfs and _run([sys.executable, str(_SCRIPT_DIR / "split_dpf_spec.py"),
                           "split", "--all", "--views"]) != 0:
        return False
    if _run([sys.executable, str(_SCRIPT_DIR / "skill_index.py")]) != 0:
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


def step_test(with_dpfs: bool = False) -> bool:
    """Run test_fpf_pipeline.py."""
    print("\n[4/4] Running the tests...")
    test_script = _MAKER_DIR / "tests" / "test_fpf_pipeline.py"
    if not test_script.exists():
        _print(f"{test_script} not found — cannot verify update", "✗")
        return False
    rc = _run([sys.executable, str(test_script)])
    if rc != 0:
        _print("Tests failed (see above)", "✗")
        return False
    if with_dpfs:
        for name in ("test_dpf_pipeline.py", "test_frameworks.py"):
            if _run([sys.executable, str(_MAKER_DIR / "tests" / name)]) != 0:
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
    if args.download_only and (args.no_download or args.test_only):
        ap.error("--download-only cannot be combined with --no-download or --test-only")
    if args.test_only and (args.skip_test or args.no_download):
        ap.error("--test-only cannot be combined with --skip-test or --no-download")

    print("=" * 60)
    print("FPF Skill — Self-Update Pipeline")
    print("=" * 60)

    if args.test_only:
        return 0 if step_test(with_dpfs=args.dpfs) else 4

    if not args.no_download:
        if not step_download(with_dpfs=args.dpfs):
            return 1

    if args.download_only:
        print("\n✓ Download complete. Run without --download-only to build.")
        return 0

    if not step_split(with_dpfs=args.dpfs):
        return 2

    if not step_audit():
        _print("Audit reported issues — build continues", "⚠")

    if not args.skip_test:
        if not step_test(with_dpfs=args.dpfs):
            return 4

    print("\n" + "=" * 60)
    print("✅ FPF Skill update complete")
    print(f"   Skill directory: {SKILL_DIR.relative_to(_REPO_ROOT)}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
