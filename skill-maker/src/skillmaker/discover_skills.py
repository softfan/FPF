#!/usr/bin/env python3
"""Discover local publications and build them with the existing profile engine.

Curated configs keep their names and grouping. Unclaimed Markdown in DPFs/ and
frameworks/ is classified offline; a directory named '* DPF Suite' is bundled.
Discovery is explicit, read-only and deterministic, never an import side effect.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PKG_PARENT = _SCRIPT_DIR.parent
_REPO_ROOT = _SCRIPT_DIR.parents[2]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402
from skillmaker import frameworks as F  # noqa: E402
from skillmaker.build_generic import config_for  # noqa: E402
from skillmaker.skill_config import ALL_DPF_CONFIGS, FPF_CONFIG, SkillConfig  # noqa: E402
from skillmaker.split_spec import build_skill  # noqa: E402

ensure_utf8_stdio()

DEFAULT_SOURCE_ROOTS = ("DPFs", "frameworks")
_DOCID = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_RESERVED = {"con", "prn", "aux", "nul"} | {
    f"{prefix}{n}" for prefix in ("com", "lpt") for n in range(1, 10)
}


def _name(value: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not _NAME.fullmatch(name) or len(name) > 64 or name in _RESERVED:
        raise ValueError(f"cannot derive a portable skill name from {value!r}")
    return name


def _no_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise ValueError(f"symbolic links/junctions are not discovery inputs or outputs: {item}")


def _markdown(root: Path) -> Iterable[Path]:
    """Do not follow links or read special files, even under explicit roots."""
    _no_links(root)
    if not root.exists():
        return
    if not root.is_dir():
        raise ValueError(f"source root is not a directory: {root}")

    def onerror(error):
        raise error

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        for name in sorted(dirs):
            _no_links(Path(directory) / name)
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix.lower() != ".md":
                continue
            if name.split(".", 1)[0].rstrip(" .").casefold() in _RESERVED:
                raise ValueError(f"reserved Windows device source name: {path}")
            _no_links(path)
            if not path.is_file():
                raise ValueError(f"not a regular publication file: {path}")
            yield path


@dataclass
class Discovery:
    configs: Dict[str, SkillConfig]
    added: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    def report(self, repo_root: Path) -> Dict:
        return {
            "skills": [{
                "name": cfg.name, "profile": cfg.profile_key,
                "kind": cfg.kind_label, "output": str(cfg.output),
                "sources": [p.relative_to(repo_root).as_posix() for p in
                            [f.source for f in cfg.frameworks] + [d.source for d in cfg.docs]],
            } for cfg in self.configs.values()],
            "added_publications": self.added, "skipped": self.skipped,
        }


def discover(repo_root: Path = _REPO_ROOT, output_root: Optional[Path] = None,
             source_roots: Optional[List[Path]] = None,
             configured: Optional[Iterable[SkillConfig]] = None) -> Discovery:
    """Merge curated overrides with unclaimed publications; never write files.

    Explicit source roots replace the defaults and must be inside repo_root.
    Passing configured=[] supports a private/fixture corpus with no FPF tree.
    Default curated entries are optional overrides for files present in the
    input. Explicitly supplied configs still require all their sources.
    """
    _no_links(repo_root.absolute())
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise ValueError(f"repository root is not a directory: {repo_root}")
    out = output_root or repo_root / "skills"
    if not out.is_absolute():
        out = repo_root / out
    _no_links(out)
    out = out.resolve()
    if out == repo_root or repo_root.is_relative_to(out) or _SCRIPT_DIR.is_relative_to(out):
        raise ValueError("output must not contain the repository or the engine")

    originals = list(configured) if configured is not None else [FPF_CONFIG, *ALL_DPF_CONFIGS.values()]
    configs: Dict[str, SkillConfig] = {}
    claimed = set()
    docids: Dict[str, str] = {}
    suite_dirs: Dict[Path, SkillConfig] = {}
    ignored = {repo_root / "DPFs" / "README.md"}

    def claim_docid(docid: str, source: Path) -> None:
        if not docid:
            return
        if not _DOCID.fullmatch(docid):
            raise ValueError(f"invalid DocID {docid!r}: {source}")
        key = docid.casefold()
        if key in docids:
            raise ValueError(f"duplicate DocID {docid!r}: {docids[key]} and {source}")
        docids[key] = str(source)

    def add(cfg: SkillConfig) -> None:
        if _name(cfg.name) != cfg.name:
            raise ValueError(f"invalid skill name: {cfg.name!r}")
        if cfg.name in configs:
            raise ValueError(f"skill name collision: {cfg.name!r}")
        configs[cfg.name] = cfg

    for original in originals:
        cfg = copy.deepcopy(original)
        cfg.output = out / cfg.name
        if configured is None:
            def present(item):
                path = repo_root / item.source.relative_to(_REPO_ROOT)
                _no_links(path)
                return path.is_file()

            cfg.frameworks = [fw for fw in cfg.frameworks if present(fw)]
            cfg.docs = [doc for doc in cfg.docs if present(doc)]
            if not cfg.frameworks:
                continue
            if cfg.kind_label == "DPF Suite" and (
                    not any(fw.role == "reference" for fw in cfg.frameworks)
                    or not any(fw.role != "reference" for fw in cfg.frameworks)):
                # Let discovery report an incomplete Suite rather than hide it.
                continue
        for source in [*cfg.frameworks, *cfg.docs]:
            # Rebase the shipped catalogue for --repo-root / isolated tests.
            try:
                rel = source.source.relative_to(_REPO_ROOT)
            except ValueError:
                rel = source.source.relative_to(repo_root)
            source.source = repo_root / rel
            _no_links(source.source)
            if not source.source.is_file():
                raise ValueError(f"configured source missing: {source.source}")
            if source.source in claimed:
                raise ValueError(f"source used by more than one skill: {source.source}")
            claimed.add(source.source)
            claim_docid(source.docid, source.source)
        if cfg.kind_label == "DPF Suite":
            parents = {fw.source.parent for fw in cfg.frameworks}
            if len(parents) != 1:
                raise ValueError(f"suite sources must share a directory: {cfg.name}")
            parent = next(iter(parents))
            suite_dirs[parent] = cfg
            ignored.add(parent / "README.md")
        add(cfg)

    roots = source_roots if source_roots is not None else [Path(p) for p in DEFAULT_SOURCE_ROOTS]
    paths = set()
    for root in roots:
        root = root if root.is_absolute() else repo_root / root
        _no_links(root)
        root = root.resolve()
        if source_roots is not None and not root.exists():
            raise ValueError(f"explicit source root not found: {root}")
        if not root.is_relative_to(repo_root):
            raise ValueError(f"source root must be inside the repository: {root}")
        if root == out or root.is_relative_to(out) or out.is_relative_to(root):
            raise ValueError(f"source root overlaps generated output: {root}")
        paths.update(_markdown(root))

    pending = {}
    unit_owners: Dict[str, str] = {}

    def claim_units(ids: Iterable[str], source: Path) -> None:
        for unit_id in ids:
            key = unit_id.casefold()
            if key in unit_owners:
                raise ValueError(f"duplicate unit ID {unit_id!r}: {unit_owners[key]} and {source}")
            unit_owners[key] = str(source)

    # Prefix families such as A.* (Core) may differ from the publication's
    # declared DocID. Reserve the actual unit IDs as well as the DocIDs.
    from skillmaker.split_spec import SpecParser

    if paths - claimed - ignored:
        for cfg in configs.values():
            for fw in cfg.frameworks:
                parser = SpecParser(cfg, fw)
                parser.parse()
                claim_units((c.id for c in parser.chunks if c.kind == "unit"), fw.source)

    result = Discovery(configs)
    for path in sorted(paths, key=lambda p: p.as_posix()):
        if path in claimed:
            continue
        rel = path.relative_to(repo_root).as_posix()
        if path in ignored:
            result.skipped.append(rel)
            continue
        text = path.read_text("utf-8")
        if not text.strip():
            raise ValueError(f"empty publication: {rel}")
        profile, detection = F.detect(rel, text)
        tied = [p.key for p, d in F.detect_all(rel, text)
                if d.score == detection.score and d.score > 0]
        if len(tied) > 1:
            raise ValueError(f"ambiguous profile for {rel}: {', '.join(tied)}; use build_generic.py --profile")
        tree = F.decompose(profile, text, rel)
        if profile.shape.unit_files and not tree.units:
            raise ValueError(f"no addressable units for {profile.key}: {rel}")
        if profile.shape.unit_files:
            for values, label in ((tree.ids(), "unit IDs"), (tree.filenames(), "unit filenames")):
                folded = [v.casefold() for v in values]
                if len(folded) != len(set(folded)):
                    raise ValueError(f"duplicate {label}: {rel}")
        docid = F.docid_of(text)
        if profile.docid_prefix:
            # Recover only a single, consistent identifier family, not the
            # first example that happened to look like a heading.
            prefixes = {u.id.split(".")[0] for u in tree.units}
            docid = docid or (next(iter(prefixes)) if len(prefixes) == 1 else "")
            if not docid or prefixes != {docid}:
                raise ValueError(f"missing or inconsistent DocID: {rel}")
            foreign = F.decompose(F.by_key("guide"), text, rel)
            for unit in foreign.units:
                if re.match(r"^[A-Za-z][A-Za-z0-9]*[.:]", unit.id) and not unit.id.startswith(docid + "."):
                    raise ValueError(f"foreign unit ID {unit.id!r} in {rel}")
        claim_docid(docid, path)
        if profile.shape.unit_files:
            claim_units(tree.ids(), path)
        name = _name(docid or path.stem)
        cfg = config_for(path, profile, name, out / name)
        cfg.source_path = rel
        if cfg.frameworks:
            cfg.frameworks[0].docid = docid
            cfg.prefix_token = docid
        elif cfg.docs:
            cfg.docs[0].docid = docid
        pending[path] = cfg
        result.added.append(rel)

    # Existing Suites absorb new siblings. New Suites need an explicit
    # Architectural Reference and at least one DPF, not merely a shared folder.
    groups: Dict[Path, List[Path]] = {}
    for path in pending:
        if path.parent in suite_dirs or path.parent.name.endswith(" DPF Suite"):
            groups.setdefault(path.parent, []).append(path)
    for parent, members in sorted(groups.items(), key=lambda item: item[0].as_posix()):
        suite = suite_dirs.get(parent)
        if suite is None:
            refs = [p for p in members if pending[p].profile_key == "suite-reference"]
            dpfs = [p for p in members if pending[p].profile_key == "dpf-framework"]
            if len(refs) != 1 or not dpfs:
                raise ValueError(f"new Suite needs exactly one Suite Reference and at least one DPF: {parent}")
            name = _name(parent.name[:-len(" DPF Suite")] + "-suite")
            suite = copy.deepcopy(pending[refs[0]])
            suite.name, suite.output = name, out / name
            suite.title = parent.name
            suite.kind_label, suite.layout = "DPF Suite", "frameworks"
            suite.frameworks, suite.docs = [], []
            add(suite)
        for path in members:
            cfg = pending.pop(path)
            if cfg.profile_key not in ("dpf-framework", "suite-reference", "guide", "generic"):
                raise ValueError(f"unsupported Suite member {path}: {cfg.profile_key}")
            suite.frameworks.extend(cfg.frameworks)
            suite.docs.extend(cfg.docs)
            if cfg.profile_key == "suite-reference":
                for fw in cfg.frameworks:
                    fw.role = "reference"
    for cfg in pending.values():
        add(cfg)

    # Case folding catches Windows collisions even when discovery runs on Linux.
    for cfg in configs.values():
        keys = [f.key.casefold() for f in cfg.frameworks]
        slugs = [d.slug.casefold() for d in cfg.docs]
        if len(keys) != len(set(keys)) or len(slugs) != len(set(slugs)):
            raise ValueError(f"duplicate framework/document paths in {cfg.name}")
    for cfg in configs.values():
        if cfg.layout == "frameworks" and len(cfg.frameworks) < 2:
            raise ValueError(f"Suite has no constituent framework: {cfg.name}")
    result.configs = dict(sorted(configs.items()))
    return result


def validate_outputs(plan: Discovery) -> None:
    """Preflight the whole plan before the first generated file is touched."""
    sources = [item.source.resolve() for cfg in plan.configs.values()
               for item in [*cfg.frameworks, *cfg.docs]]
    for cfg in plan.configs.values():
        target = cfg.output
        _no_links(target)
        if any(p.is_relative_to(target.resolve()) for p in sources):
            raise ValueError(f"output contains a source publication: {target}")
        if not target.exists():
            continue
        if not target.is_dir():
            raise ValueError(f"output is not a directory: {target}")
        # The writer prunes unknown files. Never hand it someone else's tree.
        marker = target / ".skill.json"
        if any(target.iterdir()):
            if not marker.is_file():
                raise ValueError(f"nonempty output has no skill marker: {target}")
            _no_links(marker)
            metadata = json.loads(marker.read_text("utf-8"))
            if (not isinstance(metadata, dict) or metadata.get("name") != cfg.name
                    or metadata.get("source") != cfg.source_path):
                raise ValueError(f"output belongs to another skill/source: {target}")
        def onerror(error):
            raise error

        for directory, dirs, files in os.walk(target, followlinks=False, onerror=onerror):
            for name in dirs + files:
                _no_links(Path(directory) / name)
            for name in files:
                if not (Path(directory) / name).is_file():
                    raise ValueError(f"output contains a special file: {Path(directory) / name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    ap.add_argument("--output", type=Path, help="Skills root (default: <repo-root>/skills)")
    ap.add_argument("--source-root", type=Path, action="append",
                    help="Scan this repository subdirectory; repeat to replace DPFs/ + frameworks/")
    ap.add_argument("--unconfigured", action="store_true", help="Discover a private corpus without curated FPF configs")
    ap.add_argument("--dry-run", action="store_true", help="Report the plan without writing")
    ap.add_argument("--json", action="store_true", help="Machine-readable plan (implies --dry-run)")
    ap.add_argument("--views", action="store_true", help="Also emit contract views")
    args = ap.parse_args()
    try:
        plan = discover(args.repo_root, args.output, args.source_root,
                        [] if args.unconfigured else None)
        validate_outputs(plan)
        if args.json:
            print(json.dumps(plan.report(args.repo_root.resolve()), indent=2, ensure_ascii=False))
            return 0
        print(f"Discovery: {len(plan.configs)} skills, {len(plan.added)} new publications")
        for cfg in plan.configs.values():
            if args.dry_run:
                print(f"  {cfg.name}: {cfg.kind_label} -> {cfg.output}")
                for item in [*cfg.frameworks, *cfg.docs]:
                    print(f"    {item.source.relative_to(args.repo_root.resolve()).as_posix()}")
                continue
            print(f"\n=== {cfg.name} ===")
            if build_skill(cfg, emit_views=True if args.views else None):
                return 1
        return 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
