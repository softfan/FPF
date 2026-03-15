#!/usr/bin/env python3
"""
audit_fpf_patterns.py — Audit integrity of generated FPF skill.

Exit codes: 0 = healthy, 2 = audit failures.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _fpf_common import (
    PATTERN_ID_RE, PATTERN_HEADING_RE, PATTERN_HEADING_BARE_RE,
    TOC_START_RE, FenceTracker,
)

_ROMAN = re.compile(r"^[IVX]+$")


def _is_pseudo_id(pid: str) -> bool:
    parts = pid.split(".")
    if len(parts) < 2:
        return True
    for seg in parts[1:]:
        if _ROMAN.match(seg):
            return True
    if parts[-1] == "x":
        return True
    if pid in {"D.CTX", "E.TGA", "A.CHR", "A.CSLC", "C.Agent"}:
        return True
    return False


def _is_real_pattern_id(pid: str) -> bool:
    return PATTERN_ID_RE.match(pid) is not None and not _is_pseudo_id(pid)


@dataclass
class AuditReport:
    expected_ids: Set[str] = field(default_factory=set)
    generated_ids: Set[str] = field(default_factory=set)
    missing_files: Set[str] = field(default_factory=set)
    missing_stubs_no_body: Set[str] = field(default_factory=set)
    extra_files: Set[str] = field(default_factory=set)
    excluded_stubs: Set[str] = field(default_factory=set)
    excluded_pseudo: Set[str] = field(default_factory=set)
    broken_deps: List[Tuple[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return not self.missing_files and not self.errors

    @property
    def exit_code(self) -> int:
        return 2 if (self.errors or self.missing_files) else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.is_healthy,
            "expected_count": len(self.expected_ids),
            "generated_count": len(self.generated_ids),
            "missing": sorted(self.missing_files),
            "missing_no_body": sorted(self.missing_stubs_no_body),
            "extra": sorted(self.extra_files),
            "excluded_stubs": sorted(self.excluded_stubs),
            "excluded_pseudo_ids": sorted(self.excluded_pseudo),
            "broken_dependencies": [{"pattern": p, "dep": d} for p, d in self.broken_deps],
            "warnings": self.warnings, "errors": self.errors,
        }

    def print_report(self) -> None:
        print("=== FPF Audit Report ===\n")
        print(f"Expected:     {len(self.expected_ids)}")
        print(f"Generated:    {len(self.generated_ids)}")
        print(f"Stubs:        {len(self.excluded_stubs)}")
        print(f"Pseudo-IDs:   {len(self.excluded_pseudo)}")
        if self.missing_files:
            print(f"\n❌ MISSING ({len(self.missing_files)}):")
            for p in sorted(self.missing_files): print(f"  - {p}")
        if self.missing_stubs_no_body:
            print(f"\nℹ️  TOC only, no body ({len(self.missing_stubs_no_body)}):")
            for p in sorted(self.missing_stubs_no_body): print(f"  ○ {p}")
        if self.extra_files:
            print(f"\n⚠️  EXTRA ({len(self.extra_files)}):")
            for p in sorted(self.extra_files): print(f"  + {p}")
        if self.broken_deps:
            print(f"\n⚠️  BROKEN DEPS ({len(self.broken_deps)}):")
            for pat, dep in sorted(self.broken_deps): print(f"  {pat} → {dep}")
        if self.warnings:
            print(f"\n⚠️  WARNINGS:")
            for w in self.warnings: print(f"  {w}")
        if self.errors:
            print(f"\n❌ ERRORS:")
            for e in self.errors: print(f"  {e}")
        print(f"\n{'✅ PASSED' if self.is_healthy else '❌ FAILED'}")


def _extract_toc_ids(source: Path) -> Tuple[Set[str], Set[str], Set[str]]:
    real_ids, stub_ids, pseudo_ids = set(), set(), set()
    in_toc = False
    fence = FenceTracker()
    with open(source, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            fence.update(line)
            if fence.in_fence: continue
            if not in_toc:
                if TOC_START_RE.match(line): in_toc = True
                continue
            m = PATTERN_HEADING_RE.match(line) or PATTERN_HEADING_BARE_RE.match(line)
            if m: break
            if not line.strip().startswith("|"): continue
            cells = [c.strip() for c in line.split("|")]
            non_empty = [c for c in cells if c.strip()]
            if not non_empty: continue
            if all(re.match(r"^:?-+:?$", c) for c in non_empty): continue
            fl = non_empty[0].lower().replace("*", "").strip()
            if fl in ("§", "id", "id & title", "status") or "status" in fl: continue
            status = ""
            for cell in cells:
                cl = cell.strip().lower().replace("*", "").strip()
                if cl in ("stable", "draft", "stub", "new", "transitional stub", "full text"):
                    status = cl; break
            row_id = _extract_row_id(cells)
            if row_id:
                if _is_pseudo_id(row_id): pseudo_ids.add(row_id)
                elif status == "stub": stub_ids.add(row_id)
                else: real_ids.add(row_id)
    return real_ids, stub_ids, pseudo_ids


def _extract_row_id(cells: List[str]) -> Optional[str]:
    for cell in cells[:4]:
        cv = cell.replace("*", "").replace("`", "").strip()
        if not cv: continue
        m = re.match(r"([A-K](?:\.(?:\d+|[A-Za-z][A-Za-z0-9_]*))+)", cv)
        if m and PATTERN_ID_RE.match(m.group(1)):
            return m.group(1)
    return None


def _extract_header_ids(source: Path) -> Set[str]:
    ids: Set[str] = set()
    fence = FenceTracker()
    with open(source, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            fence.update(line)
            if fence.in_fence: continue
            m = PATTERN_HEADING_RE.match(line) or PATTERN_HEADING_BARE_RE.match(line)
            if m:
                pid = m.group(1)
                if _is_real_pattern_id(pid): ids.add(pid)
    return ids


def _get_generated_ids(skill_dir: Path) -> Set[str]:
    pdir = skill_dir / "reference" / "fpf-patterns"
    if not pdir.exists(): return set()
    return {f.stem for f in pdir.glob("*.md")
            if f.name not in ("index.md", "introduction.md") and PATTERN_ID_RE.match(f.stem)}


def _validate_deps(patterns_dir: Path, all_known: Set[str], report: AuditReport):
    for f in sorted(patterns_dir.glob("*.md")):
        if f.name in ("index.md", "introduction.md"): continue
        stem = f.stem
        if not PATTERN_ID_RE.match(stem): continue
        content = f.read_text("utf-8")
        for m in re.finditer(
            r"(?:Builds?\s+on|Prerequisite\s+for|Used\s+by|Refines|"
            r"Integrates|Coordinates\s+with|Constrains)[^.]*?(?:\.|$)",
            content, re.IGNORECASE,
        ):
            refs = re.findall(r"\b([A-K](?:\.(?:\d+|[A-Za-z][A-Za-z0-9_]*))+)\b", m.group(0))
            for ref in refs:
                if ref == stem or not PATTERN_ID_RE.match(ref): continue
                if ref in all_known or _is_pseudo_id(ref): continue
                if ref.rsplit(".", 1)[0] in all_known: continue
                report.broken_deps.append((stem, ref))


def run_audit(source: Optional[Path] = None, skill_dir: Path = Path("skills/fpf"),
              source_type: str = "both", print_ids: bool = False,
              output_json: bool = False) -> int:
    report = AuditReport()
    report.generated_ids = _get_generated_ids(skill_dir)
    if not report.generated_ids:
        report.errors.append(f"No pattern files in {skill_dir}/reference/fpf-patterns/")
    toc_ids, header_ids, stub_ids, pseudo_ids = set(), set(), set(), set()
    if source and source.exists():
        if source_type in ("toc", "both"):
            toc_ids, stub_ids, pseudo_ids = _extract_toc_ids(source)
        if source_type in ("headers", "both"):
            header_ids = _extract_header_ids(source)
    elif source is not None:
        report.errors.append(f"Source file not found: {source}")
    else:
        report.warnings.append("No source file; audit uses generated files only.")
    report.excluded_stubs = stub_ids
    report.excluded_pseudo = pseudo_ids
    if source_type == "toc":
        report.expected_ids = toc_ids.copy()
    elif source_type == "headers":
        report.expected_ids = header_ids.copy()
    else:
        report.expected_ids = header_ids.copy()
        report.missing_stubs_no_body = toc_ids - header_ids - stub_ids - pseudo_ids
    report.expected_ids -= stub_ids | pseudo_ids
    report.expected_ids = {p for p in report.expected_ids if _is_real_pattern_id(p)}
    report.missing_files = report.expected_ids - report.generated_ids
    report.extra_files = report.generated_ids - report.expected_ids
    if source_type == "both" and header_ids:
        report.extra_files -= toc_ids
    pdir = skill_dir / "reference" / "fpf-patterns"
    if pdir.exists():
        _validate_deps(pdir, report.generated_ids | stub_ids | pseudo_ids | toc_ids, report)
    if print_ids:
        for label, ids in [("Expected", report.expected_ids), ("Generated", report.generated_ids),
                           ("Headers", header_ids), ("TOC", toc_ids), ("Stubs", stub_ids),
                           ("Pseudo", pseudo_ids), ("No body", report.missing_stubs_no_body)]:
            if ids:
                print(f"\n{label} ({len(ids)}):")
                for p in sorted(ids): print(f"  {p}")
    if output_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        report.print_report()
    return report.exit_code


def main() -> int:
    ap = argparse.ArgumentParser(description="FPF Skill Audit")
    ap.add_argument("--source", type=Path)
    ap.add_argument("--skill-dir", type=Path, default=Path("skills/fpf"))
    ap.add_argument("--source-type", choices=["toc", "headers", "both"], default="both")
    ap.add_argument("--print-ids", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    return run_audit(source=args.source, skill_dir=args.skill_dir,
                     source_type=args.source_type, print_ids=args.print_ids,
                     output_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
