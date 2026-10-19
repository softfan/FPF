# AGENTS.md — skill-maker

Applies to work in `skill-maker/`. `README.md` here is the design + command
reference and `FRAMEWORKS.md` is the general-decomposition design; this file
holds only what you cannot get from reading them.

## What this directory is

One parser (`split_spec.py`) plus one declarative catalogue (`skill_config.py`)
turn the Library's publications into **skills** — 15 of them under `skills/`,
one per FPF Core / DPF Suite / standalone DPF, 1498 unit files.

```
FPF-Spec.md, DPFs/**  ──►  skill_config.py  ──►  split_spec.py  ──►  skills/<name>/
                          (what to build)       (the engine)         (generated)
```

`skills/` is gitignored and disposable. **Never hand-edit it** — a manual fix
survives exactly until the next build prunes it. Edit the source publication,
`skill_config.py`, or a template.

## Commands

Full build (same 10 steps in all three, run from the repo root):

```bash
bash skill-maker/build.sh                    # bash  (PYTHON=python3)
powershell -File skill-maker\build.ps1       # pwsh  (PYTHON=python, or $env:PYTHON)
skill-maker\build.cmd                        # cmd
```

Inner loop — seconds, not minutes:

```bash
python3 skill-maker/split_fpf_spec.py split --source FPF-Spec.md --output skills/fpf --views
python3 skill-maker/split_dpf_spec.py split --framework PSDA        # or --suite / --all
python3 skill-maker/split_dpf_spec.py analyze                      # parse only, no writes
python3 skill-maker/skill_index.py --check                          # exit 1 if the index is stale
python3 skill-maker/build_generic.py DOC.md --skill x --dry-run    # plan without writing
python3 skill-maker/fpf_frameworks.py probe DOC.md | plan DOC.md    # classify + artefacts
python3 skill-maker/mcp_server.py --selftest                       # serve check, no client
```

Every script derives the repo root from `__file__`, so cwd does not matter for
the script — but `--source` / `--output` you type are relative to **your** cwd.
Run from the repo root, as the README shows.

## Verification

- **No pytest, no dependencies, no CI.** Each suite is a standalone script with
  its own `TestRunner`; `-v` prints each assertion. There is no per-test
  selector — run the whole suite (0.3–5 s each).
- `test_fpf_pipeline.py` and `test_dpf_pipeline.py` build what they need, so
  they run standalone; the latter still needs the index (`skills/README.md`,
  `index.json`, `CROSS-REFERENCES.md`) from `skill_index.py`.
- The rest read the built tree: `test_mcp_server.py` refuses to start without
  `skills/`, and `test_derived.py` / `test_frameworks.py` fail their built-tree
  checks. Build first — "skills/ missing" is an unbuilt tree, not a bug.
- Green today is **1095 assertions**: FPF 88, DPF 539, frameworks 116, generic
  48, MCP 118, derived 157, HTTP 29.
- The suites are offline. They verify against the committed
  `catalogue.snapshot.json`. Only `fpf_frameworks.py catalogue --verify`
  (without `--offline`) and `fpf_update.py` reach the network — do not wire
  either into a default path.
- **Step 4, the audit, is non-fatal in all three build scripts.** A green build
  does not mean the audit was clean; read its output.
- Step 10 is *skipped*, not passed, when `bash` is missing (PowerShell/cmd).

## Where a change belongs

| Change | File |
| --- | --- |
| Add / move a publication | `skill_config.py` — a `DPFSpec`, plus `SuiteSpec.members` if it belongs to a Suite |
| New framework kind (ADR, standards, …) | a module in `frameworks/profiles/` exporting `PROFILE`, registered in `frameworks/profiles/__init__.py`. Nothing else. |
| Wording / structure of a generated skill | `templates/` — `{{placeholder}}` syntax, `genres/<genre>.md`, `roles/<role>.md` |
| Retrieval artefacts (routes, entries, glossary, boot) | `derive.py`; section offsets and tiers in `sections.py` |
| Hand-written routes that must survive a rebuild | `<skill>/curated-routes.json` — the builder never overwrites it |

After editing `skill_config.py`, run `split_dpf_spec.py analyze` and compare the
counts with the "Patterns" column of `DPFs/README.md`.

The build stamp `.<skill>_build.json` digests every engine module, the whole
`frameworks/` package, the whole `templates/` tree and the resolved sources, so
**any** of those edits invalidate all 15 skills. That is the point: editing one
template rewrites exactly the files derived from it (verified: 2 of 892) and
leaves the rest skipped.

## Gotchas that cost real time

- **Windows path separators.** `SkillShape.outputs()` prints forward-slash
  paths; `str(Path.relative_to(...))` renders backslashes. Anything comparing
  the two must use `.as_posix()`. This was a live failure: the generic-builder
  test "every planned file exists" passed on Linux and failed in pwsh with every
  file reported missing, while the build itself was byte-identical. A Windows
  failure with a plausible-looking diff is often this, not the engine.
- **Never hand a backslash path to bash.** `build.cmd` used to call
  `bash skill-maker\test-mcp-http.sh`; bash reads `\` as an escape and reports
  `skill-makertestest-mcp-http.sh: No such file or directory`. Backslashes are
  fine for `%PYTHON%` and PowerShell (Windows programs parse them), wrong for
  any POSIX tool. Step 10 also needs `$env:PYTHON` exported, or the script
  default to `python3`, which most Windows installs do not have.
- **Console encoding.** Every entry point calls `ensure_utf8_stdio()`; a new
  script that prints a pattern title must do the same, and a subprocess must be
  decoded with `encoding="utf-8"`, or a cp1251/cp437 console raises
  `UnicodeEncodeError` mid-run.
- **LF everywhere.** Generated files use `\n` via `write_text_lf`, so trees are
  byte-identical across platforms and `rebuild` compares exactly. `.gitattributes`
  forces LF on `*.py|*.md|*.template|*.sh|*.json` and CRLF on `*.cmd|*.ps1`.
- **`Path.write_text` is newline-translating**: on Windows it rewrites LF as
  `os.linesep`. Never use it on a file the engine digests or git tracks — use
  `write_text_lf` for output, `read_bytes`/`write_bytes` for a round-trip. The
  portability scan in `test_frameworks.py` exempts `test_*.py`, which is how the
  digest probe used to corrupt three templates on every Windows run. Its
  companion check now fails and names any tracked file that picked up a CRLF;
  recover with `git checkout -- <path>`, or strip the CRs when the file is not
  committed yet.
- **No `:` in generated file names** (`SYSE.Application:1` →
  `SYSE.Application-1.md`) — the tree has to work on Windows.
- `skills/index.json`, `CROSS-REFERENCES.md`, `CONNECT.md` and the per-skill
  `SKILL.md`/`README.md` are generated. A wording complaint about them is a
  complaint about a template.

## Operating rules carried over from the machine draft

- Answer from the file when the question names a file. Escalate to an index or
  graph only for relationship questions (callers, blast radius, flow).
- **Consent before heavy pipelines**: `codegraph init`, `gitnexus analyze` (and
  `--pdg`), `/understand`, `/graphify`. They write index directories and take
  minutes. This repo has neither a `.codegraph/` nor a GitNexus index — verify
  before relying on one, and never create one unasked.
- An empty result from a graph or index means *not indexed*, not *does not
  exist*. Say which.
- Do not answer live facts (publisher catalogue, upstream FPF repository) from
  memory — read `catalogue.snapshot.json` or look it up.
- Do not invent tool names or flags; every entry point has `--help`.
- One graph system per question. Do not merge CodeGraph and GitNexus results.
- `mcp_server.py`'s reading contract lives in `READING_TOOLS` and is asserted
  exactly by `test_mcp_server.py`. Change the contract there, not in a client.