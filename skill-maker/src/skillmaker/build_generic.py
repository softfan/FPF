#!/usr/bin/env python3
"""
build_generic.py -- build a skill from any framework kind.

``split_fpf_spec.py`` and ``split_dpf_spec.py`` build configured/discovered
publications. This command builds a skill
from *any* document, using a decomposition profile to decide how it splits:

    python skill-maker/src/skillmaker/build_generic.py docs/adr/adr-0001.md --skill payments-adr
    python skill-maker/src/skillmaker/build_generic.py standard.md --skill arch-standard
    python skill-maker/src/skillmaker/build_generic.py notes.md --skill notes --profile generic

It is the other half of ``fpf_frameworks.py plan``: the plan says what would be
produced, this produces it.  Both go through the same profile, grammar and
shape, so the two cannot disagree.

Two emission paths, chosen by the profile's shape:

* **unit files** (ADR, standards, pattern languages, and the Library kinds) --
  reuse the tested engine in ``split_spec``: indexes, manifest, prune,
  idempotent rewrite.
* **whole document** (guides, generic Markdown) -- copy the source into
  ``reference/docs/`` and write an entry point.  A document with no unit
  structure gains nothing from being split.

Usage::

    build_generic.py PATH --skill NAME [--profile KEY] [--output DIR]
                          [--dry-run] [--force]

Exit codes: 0 = built, 1 = nothing to do or an error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PKG_PARENT = _SCRIPT_DIR.parent          # the directory to import `skillmaker` from
_MAKER_DIR = _PKG_PARENT.parent           # skill-maker/
_REPO_ROOT = _MAKER_DIR.parent            # repository root
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from skillmaker._fpf_common import ensure_utf8_stdio  # noqa: E402

ensure_utf8_stdio()

from skillmaker import frameworks as F  # noqa: E402
from skillmaker.frameworks import genre as genre_mod  # noqa: E402
from skillmaker.skill_config import DocSpec, FrameworkSpec, SkillConfig  # noqa: E402
from skillmaker.split_spec import build_skill  # noqa: E402

TEMPLATES = _SCRIPT_DIR / "templates"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _title_of(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _prefix_of(profile, text: str) -> str:
    """A harmless prefix for the engine when the grammar does the real work."""
    docid = F.docid_of(text)
    return docid or "unit"


def config_for(path: Path, profile, skill_name: str,
               output: Optional[Path] = None,
               genre: str = "lookup") -> SkillConfig:
    """Turn a document + profile into the engine's config."""
    text = path.read_text("utf-8", errors="replace")
    title = _title_of(text, skill_name)
    grammar = profile.grammar_for(text)
    rel = _rel(path)
    out = output or (_REPO_ROOT / "skills" / skill_name)

    if profile.shape.unit_files:
        framework = FrameworkSpec(
            key=skill_name,
            prefix_re=_prefix_of(profile, text),
            source=path,
            name=title,
            description=profile.description,
            docid=F.docid_of(text),
            domains={F.docid_of(text) or skill_name: title},
            grammar=grammar,
        )
        return SkillConfig(
            name=skill_name,
            title=title,
            prefix_token=F.docid_of(text) or "",
            output=out,
            frameworks=[framework],
            docs=[],
            layout="flat",
            intro_split="h2",
            skill_template=TEMPLATES / "GENERIC-SKILL.md.template",
            readme_template=TEMPLATES / "GENERIC-README.md.template",
            scripts=[],
            domain_label_prefix="",
            builds_on_fallback=False,
            kind_label=profile.kind_info().label,
            profile_key=profile.key,
            genre=genre,
            source_path=rel,
            source_note=f"the {title} {profile.kind_info().label}",
        )

    # Whole-document path: the document is shipped as published.
    return SkillConfig(
        name=skill_name,
        title=title,
        prefix_token="",
        output=out,
        frameworks=[],
        docs=[DocSpec(source=path, slug=skill_name, title=title,
                      description=profile.description)],
        layout="flat",
        intro_split="h2",
        skill_template=TEMPLATES / "GENERIC-SKILL.md.template",
        readme_template=TEMPLATES / "GENERIC-README.md.template",
        scripts=[],
        domain_label_prefix="",
        kind_label=profile.kind_info().label,
        profile_key=profile.key,
        genre=genre,
        source_path=rel,
        source_note=f"the {title} {profile.kind_info().label}",
    )


def build(path: Path, skill_name: str, profile_key: str = "",
          output: Optional[Path] = None, dry_run: bool = False,
          genre: str = "lookup") -> int:
    if (not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name)
            or len(skill_name) > 64):
        print("Error: skill name must be 1-64 lowercase letters, digits and single hyphens",
              file=sys.stderr)
        return 1
    if genre not in {item.value for item in genre_mod.Genre}:
        print(f"Error: unknown genre {genre!r}", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"Error: {path} not found", file=sys.stderr)
        return 1
    target = (output or (_REPO_ROOT / "skills" / skill_name)).resolve()
    if path.resolve().is_relative_to(target) or _SCRIPT_DIR.is_relative_to(target):
        print("Error: output must not contain the source or the engine", file=sys.stderr)
        return 1
    if target.is_dir() and any(target.iterdir()) and not (target / ".skill.json").is_file():
        print("Error: refusing to build into a nonempty directory without a skill marker", file=sys.stderr)
        return 1
    marker = target / ".skill.json"
    if marker.exists():
        try:
            metadata = json.loads(marker.read_text("utf-8"))
            if not isinstance(metadata, dict) or metadata.get("name") != skill_name:
                raise ValueError("skill name does not match existing output")
        except (OSError, ValueError) as exc:
            print(f"Error: refusing to overwrite existing skill: {exc}", file=sys.stderr)
            return 1

    text = path.read_text("utf-8", errors="replace")
    rel = _rel(path)
    if profile_key:
        profile = F.by_key(profile_key)
        detection = None
    else:
        profile, detection = F.detect(rel, text)

    if dry_run:
        tree = F.decompose(profile, text, rel)
        cfg = config_for(path, profile, skill_name, output, genre)
        artefacts = profile.shape.outputs(skill_name, [skill_name],
                                          tree.filenames())
        print(f"Would build {skill_name} from {rel}")
        print(f"  kind     {profile.kind.value}")
        print(f"  profile  {profile.key}"
              + (f"  (evidence: {', '.join(detection.reasons)})" if detection else ""))
        print(f"  units    {len(tree.units)}")
        print(f"  genre    {genre} ({', '.join(genre_mod.by_value(genre).roles) or 'no roles'})")
        for item in artefacts:
            print(f"  {item}")
        return 0

    print(f"Building {skill_name} from {rel}")
    print(f"  kind {profile.kind.value}, profile {profile.key}")
    cfg = config_for(path, profile, skill_name, output, genre)
    rc = build_skill(cfg, output=cfg.output)
    if rc == 0:
        print(f"Built {cfg.output}")
        if cfg.output.resolve().parent == (_REPO_ROOT / "skills").resolve():
            print("  Add it to skills/index.json by running: "
                  "python skill-maker/src/skillmaker/skill_index.py")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="build_generic.py",
        description="Build a skill from any framework document.")
    ap.add_argument("path", type=Path, help="Source Markdown document")
    ap.add_argument("--skill", required=True, help="Skill directory name")
    ap.add_argument("--profile", default="",
                    help="Force a profile instead of detecting one")
    ap.add_argument("--output", type=Path, default=None,
                    help="Output directory (default: skills/<skill>)")
    ap.add_argument("--genre", default="lookup",
                    help="Why the skill is opened: lookup, apply, setup, maintain")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be produced, write nothing")
    args = ap.parse_args()

    # Validate here, not where the profile is looked up: by_key() raises a
    # KeyError, which reaches the user as a traceback instead of the list of
    # profiles that do exist.
    if args.profile:
        known = {p.key for p in F.all_profiles()}
        if args.profile not in known:
            print(f"Error: unknown profile {args.profile!r}. "
                  f"Known: {', '.join(sorted(known))}", file=sys.stderr)
            return 1

    return build(args.path, args.skill, args.profile, args.output,
                 args.dry_run, args.genre)


if __name__ == "__main__":
    sys.exit(main())
