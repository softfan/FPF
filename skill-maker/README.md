# skill-maker — build agent skills from the FPF Library

This directory turns the Library's publications into **skills**: directories an
AI agent can navigate without loading multi-megabyte files. One parser
(`split_spec.py`) and one declarative catalogue (`skill_config.py`) produce all
of them.

```
python3 skill-maker/build.sh          # or build.ps1 / build.cmd on Windows
```

## What is in the Library

The Library has three kinds of publication, and the skills mirror them exactly.

| Kind | What it is | Where |
| --- | --- | --- |
| **FPF Core** | 397 patterns (`A.1`, `C.40.OD`, `G.Core`) plus an embedded Architectural Reference (`FPF.Reference:N`) | `FPF-Spec.md` |
| **Four DPF Suites** | a composite discipline: several constituent DPFs plus the Suite Architectural Reference | `DPFs/<Suite> DPF Suite/` |
| **Ten standalone DPFs** | one field, one file | `DPFs/*.md` |

Library-level guidance ships with the FPF skill: `USING-FPF.md` (how to find and
apply a contribution), `FPF-LIBRARY-REFERENCE.md` (why the publications are
arranged this way) and `Readme.md` (the landing page).

### How a publication is addressed

```
## SYSE.24 - Choose How the Project Will Obtain a Needed Engineering Result   <- pattern
### SYSE.24:4 - Solution                                                      <- section
#### SYSE.24:4.1 - Name one result and one decision                           <- subsection
### SYSE.24:End                                                               <- end of pattern
## SYSE.Reference:3 - Use and System concepts stay linked                     <- reference unit
```

A **DocID** (`SYSE`, `MATH`, `Library`) identifies a whole document; a
**PatternID** identifies a pattern; a **SectionRef** (`SYSE.24:4.1`) locates a
section inside it. `FPF-LIBRARY-REFERENCE.md` § `Library.Reference:11.1` is the
authoritative DocID → title → carrier table, and the tests check this
toolchain against it.

### Units: patterns versus reference units

Every `## <ID> - <Title>` heading is an addressable **unit**. The `:` section
separator decides its role:

| ID shape | Role | Example |
| --- | --- | --- |
| `PREFIX.<digits>` | `pattern` | `SYSE.24`, `A.1` |
| `PREFIX.<WORD>` | `pattern` | `KCAE.USE`, `G.Core` |
| `PREFIX.Reference:<n>` | `reference` | `MATH.Reference:3.2` |
| `PREFIX.Application:<n>` | `application` | `PSDA.Application:3` |
| `PREFIX.Sources:<n>` | `sources` | `SYSE.Sources:2` |
| `PREFIX.Advising:<n>` | `advising` | `PSDA.Advising:1` |

Patterns go into the pattern index; every other role goes into
`reference/reference-index.md`. Both are addressable, so a README link to
`SYSE.Reference:25.1` still resolves inside a skill.

`## X.Something:End` closes a block: the marker line is kept with the preceding
unit (so a publication can be reassembled) but never gets a file of its own.

## What a generated skill looks like

```
skills/<skill>/
├── SKILL.md                      # entry point: purpose, indexes, stop rule
├── README.md                     # the same, for a human reader
├── boot.md                       # the first lines a session reads
├── .skill.json                   # marker: makes the directory movable
├── .<skill>_manifest.json        # every file, in source order
├── .<skill>_hashes.json          # write cache (skip unchanged files)
├── .<skill>_build.json           # engine + source digests, for incremental builds
├── curated-routes.json           # optional: hand-written routes, never overwritten
├── roles/                        # apply / setup / maintain genres only
├── reference/
│   ├── index.md                  # what is in this skill
│   ├── pattern-index.md          # ID | Title | Builds on | Contract | All | File
│   ├── query-index.md            # Question | Pattern ID
│   ├── keyword-index.md          # Keyword | Pattern IDs
│   ├── reference-index.md        # Unit | Role | Title | File
│   ├── entries.md                # situation -> starting unit
│   ├── glossary.md               # term -> one-line meaning -> unit
│   ├── sections.json             # anchors, tiers, line ranges, byte sizes
│   ├── routes.json               # what to read before a unit
│   ├── entries.json              # entries, machine-readable
│   ├── docs/                     # whole documents, read as published
│   ├── intro/                    # readme / contents / practical entries
│   │                             #   (a Suite prefixes them with the DocID)
│   └── <docid>/                  # e.g. syse/, fpf-patterns/, psda/
│       ├── index.md              # every unit of this framework
│       ├── <ID>.md               # one unit per file (":" becomes "-")
│       └── contract/<ID>.md      # working sections only (--views)
└── scripts/                      # FPF skill only: search/read/update tools
    ├── __init__.py               #   re-exports the runtime tools
    └── skillmaker/               #   a copy of the engine package
        ├── fpf_lookup.py
        ├── split_spec.py
        ├── frameworks/
        └── templates/
```

Every index row ends with the exact `File` to load, so an agent never has to
guess a path.

The four index files are named after what they index, not after who they are
for. `docs/` and `intro/` are directories because a flat `reference/` used to
mix 26 entries of five different kinds.

### Which skills are produced

Skill directory names say what the skill is. The DocID stays the framework key
(`reference/psda/PSDA.1.md`), so pattern IDs keep working.

| Skill | Kind | Sources |
| --- | --- | --- |
| `fpf` | FPF Core | `FPF-Spec.md`, `USING-FPF.md`, `FPF-LIBRARY-REFERENCE.md`, `Readme.md` |
| `engineering-suite` | Suite | SYSE, MNT, KCAE, SIE + Engineering Suite Reference |
| `management-suite` | Suite | STR, OPS, ADM, CGOV, MA, FIN, MKT, CUST, EAM, LDR, CB, OCE + Suite Reference |
| `foundational-thinking-suite` | Suite | MATH, MMP, PHY, CMP, NOT + Suite Reference |
| `human-capability-engineering-suite` | Suite | HCD, SOM + Suite Reference |
| `decision-design` | PSDA | Decision Design |
| `research-methods` | RMP | Research Method Practice |
| `explanation-design` | EXD | Explanation Design |
| `narrativization` | NSTD | Narrativization and Narrative Studies |
| `implementation-facilitation` | IS | Implementation Facilitation |
| `economic-reasoning` | ECO | Economic Reasoning and Coordination |
| `financial-modeling` | FDM | Financial Domain Modeling |
| `defense-transmission` | DTM | Defense and Transmission Modeling |
| `embodied-rhythmics` | RHY | Embodied Rhythmics |
| `music-dance-practice` | MDPE | Music and Dance Practice Engineering |

`skills/README.md` is generated and lists all fifteen with their DocIDs, counts
and when to use each. `skills/index.json` carries the same facts plus a
DocID → skill routing table, so a caller holding `PSDA.1` can find
`decision-design` without knowing the mapping.

## Adding or moving a publication

Everything is declared in `skill_config.py`:

1. Add a `DPFSpec` to the right list (`ENGINEERING_DPFS`, … `STANDALONE_DPFS`)
   with its DocID, title, path under `DPFs/`, one-line description and the
   number of pattern bodies published in the catalogue.
2. If it belongs to a Suite, add it to that `SuiteSpec.members`; a new Suite is
   a new `SuiteSpec` in `SUITES`.
3. Run `python3 skill-maker/src/skillmaker/split_dpf_spec.py analyze` and compare the reported
   counts with the "Patterns" column in `DPFs/README.md`.
4. Run the tests — they fail if a file in `DPFs/` is unused, if a configured
   source is missing, or if a DocID/carrier disagrees with
   `Library.Reference:11.1`.

Paths in `skill_config.py` are relative to the repository root, which is the
parent of this directory, so the toolchain works from any working directory.

## Decomposing other kinds of framework

`skill_config.py` describes the fifteen skills this repository publishes. A
framework the Library does *not* publish — an ADR set, a clause-numbered
standard, a third-party pattern language, or plain Markdown — is handled by the
`frameworks/` package instead.

Each kind of document has a **profile** that states its unit grammar and the
artefacts a decomposition produces. Four kinds match the publisher's own
classification (`FPF`, `DPF`, `Reference`, `Guide`); `ADR`, `Standards`,
`PatternLanguage` and `Generic` extend it.

```bash
python3 skill-maker/src/skillmaker/fpf_frameworks.py kinds      # the vocabulary
python3 skill-maker/src/skillmaker/fpf_frameworks.py profiles   # registered profiles
python3 skill-maker/src/skillmaker/fpf_frameworks.py probe DPFs/README.md   # classify + evidence
python3 skill-maker/src/skillmaker/fpf_frameworks.py tree FPF-Spec.md --limit 10
python3 skill-maker/src/skillmaker/fpf_frameworks.py plan DPFs/README.md --skill guide
```

To add a kind, drop a module in `frameworks/profiles/` exporting `PROFILE` and
list it in `frameworks/profiles/__init__.py`. Nothing else changes. The full
design — taxonomy, pipeline, scoring, verification — is in
[FRAMEWORKS.md](FRAMEWORKS.md).

## Commands

```bash
# Build everything
python3 skill-maker/build.sh                       # bash
powershell -File skill-maker/build.ps1             # PowerShell
skill-maker\build.cmd                              # cmd.exe

# Build selectively
python3 skill-maker/src/skillmaker/split_fpf_spec.py split --output skills/fpf
python3 skill-maker/src/skillmaker/split_dpf_spec.py split --all
python3 skill-maker/src/skillmaker/split_dpf_spec.py split --suite engineering-suite
python3 skill-maker/src/skillmaker/split_dpf_spec.py split --framework PSDA
python3 skill-maker/src/skillmaker/split_dpf_spec.py split --framework decision-design   # same skill

# Inspect
python3 skill-maker/src/skillmaker/split_fpf_spec.py analyze      # parse only, no writes
python3 skill-maker/src/skillmaker/split_dpf_spec.py analyze
python3 skill-maker/src/skillmaker/split_dpf_spec.py stats        # counts from manifests
python3 skill-maker/src/skillmaker/split_fpf_spec.py diff --skill-dir skills/fpf

# Reassemble a publication from a built skill
python3 skill-maker/src/skillmaker/split_fpf_spec.py rebuild --skill-dir skills/fpf --output /tmp/FPF.md
python3 skill-maker/src/skillmaker/split_dpf_spec.py rebuild --skill-dir skills/decision-design --output /tmp/psda.md

# Integrity and tests
python3 skill-maker/src/skillmaker/audit_fpf_patterns.py --source FPF-Spec.md --skill-dir skills/fpf
python3 skill-maker/tests/test_fpf_pipeline.py -v
python3 skill-maker/tests/test_dpf_pipeline.py -v
python3 skill-maker/tests/test_frameworks.py -v

# Framework decomposition and publisher verification
python3 skill-maker/src/skillmaker/fpf_frameworks.py catalogue --verify --counts
python3 skill-maker/src/skillmaker/fpf_frameworks.py catalogue --verify --offline --counts

# Build a skill from any framework kind (ADR, standards, plain Markdown)
python3 skill-maker/src/skillmaker/build_generic.py docs/adr/adr-0001.md --skill payments-adr --dry-run
python3 skill-maker/src/skillmaker/build_generic.py docs/adr/adr-0001.md --skill payments-adr

# Serve the built skills over MCP
python3 skill-maker/src/skillmaker/mcp_server.py --selftest
python3 skill-maker/src/skillmaker/mcp_server.py --skills-root skills

# Refresh from GitHub
python3 skill-maker/src/skillmaker/fpf_update.py                  # Core + Library documents
python3 skill-maker/src/skillmaker/fpf_update.py --dpfs           # also every DPF source
```

### Using the generated tools

```bash
python3 skills/fpf/scripts/fpf_lookup.py --skill-root skills/fpf search holon
python3 skills/fpf/scripts/fpf_lookup.py --skill-root skills/fpf read C.40.OD
python3 skills/fpf/scripts/fpf_lookup.py --skill-root skills/fpf list A
python3 skills/fpf/scripts/fpf_lookup.py --skill-root skills/fpf intro practical
python3 skills/fpf/scripts/fpf_lookup.py --skill-root skills/fpf docs
python3 skills/fpf/scripts/fpf_lookup.py --skill-root skills/fpf doc using-fpf
```

## Reading less than a whole unit

A unit is one file, but not one reading. Each carries working sections --
problem frame, solution, conformance checklist, consequences, relations -- and
depth sections -- worked cases, rationale, source comparison. Measured on the
built tree, the working sections are **54%** of the bytes overall, ranging from
36% (narrativization) to 60% (FPF Core); the largest unit, FPF `E.10`, is 257 KB,
roughly 65k tokens.

The share is measured per skill and printed into its `SKILL.md`, so the number a
reader sees is the number that skill actually has.

`sections.py` computes the section map from each unit's own headings: anchors,
tiers, line ranges and exact byte sizes. It writes `reference/sections.json` and
adds `Contract` / `All` / `Sections` columns to `reference/pattern-index.md`, so
a reader sees the cost before opening anything.

```bash
python3 -c "import sys; sys.path.insert(0,'skill-maker'); import sections as s; \
  print(s.summarise(s.analyse('SYSE.24', open('skills/engineering-suite/reference/syse/SYSE.24.md').read())))"
```

Two ways to read less, and they compose:

| | How | Cost |
| :--- | :--- | :--- |
| Offsets | `read_pattern(id, tier="contract")`, or the line range in `sections.json` | nothing on disk |
| Views | `split_*_spec.py split --views` writes `contract/<ID>.md` | ~45% more files |

The unit file stays canonical either way: `rebuild` reads units, never views, so
a publication still reassembles byte-identically.

## Genre, roles and the derived layer

A skill is not only data. `SkillConfig.genre` says *why* it is opened, which
decides the middle of `SKILL.md` and which roles ship:

| Genre | Roles | What the middle explains |
| :--- | :--- | :--- |
| `lookup` | none | indexes, tiers, the stop rule |
| `apply` | classifier, retriever, reasoner, reviewer | scope, pipeline, answer shape |
| `setup` | installer, validator | routes, four layers of evidence |
| `maintain` | sync | check, rebuild, verify, report |

`build_generic.py --genre apply` produces the pipeline. The roles are a division
of work, not a requirement to spawn four agents.

Four artefacts are derived, because the source organises for reading rather than
for retrieval:

| File | What it adds | Source |
| :--- | :--- | :--- |
| `reference/routes.json` | what to read before a unit, and its checking section | `Builds on` |
| `reference/entries.json` / `.md` | situation -> starting unit | the units' own queries |
| `reference/glossary.md` | one-line meaning, quoted | each unit's opening |
| `boot.md` | the dozen lines a session reads first | the build itself |

Every derived artefact is marked `derived: true`. A hand-written route goes in
`curated-routes.json`, which the builder never overwrites.

`skill_root.py` writes `.skill.json` at each skill's root, so a copied skill
still resolves its own paths: the lookup tool walks up until it finds the
marker, the same way `git` finds a repository.

## Serving the skills over MCP

`mcp_server.py` serves a built `skills/` tree over the Model Context Protocol.
Seven reading tools follow one contract, declared in `READING_TOOLS` and
asserted exactly by the tests: an ID in, Markdown out, with paging and a
snapshot guard so a continuation cannot silently cross editions. Three derived
tools answer the retrieval questions the indexes answer on disk -- `route`
(what to read first), `entries` (where to start from a situation) and
`glossary` (what a term means). Four more expose the skill-maker:
`list_profiles`, `probe_document`, `plan_decomposition`, `verify_catalogue`.

```bash
python3 skill-maker/src/skillmaker/mcp_server.py --selftest          # no client needed
python3 skill-maker/src/skillmaker/mcp_server.py --skills-root skills
python3 skill-maker/src/skillmaker/mcp_server.py --http 127.0.0.1:8765
```

Two transports. **stdio**: newline-delimited JSON-RPC, no third-party packages,
registered with any client as a command. **Streamable HTTP**: `POST /mcp`
answers `application/json`, `initialize` mints `Mcp-Session-Id`, notifications
get `202`, `GET /mcp` gets `405` (this server opens no streams), `DELETE`
terminates with `204`. Unknown session `404`, bad `MCP-Protocol-Version` `400`,
foreign `Origin` `403` -- the DNS-rebinding guard the specification requires.

```bash
bash skill-maker/tests/test-mcp-http.sh                      # 29 assertions, curl only
MCP_ENDPOINT=http://host:port/mcp START_SERVER=0 bash skill-maker/tests/test-mcp-http.sh
```

`skills/CONNECT.md` is the generated connection guide: transports, endpoint,
tool table, the four layers of evidence, and a by-hand curl walkthrough.

It serves whatever was built here -- a patched edition, a private framework, an
ADR set -- and answers one question across all fifteen skills at once (1498
unit files) instead of an agent loading four index files per skill to find a
path.

## Building a skill from any framework

`build_generic.py` turns a document into a skill using a decomposition profile.
It is the other half of `fpf_frameworks.py plan`: the plan says what would be
produced, this produces it.

```bash
python3 skill-maker/src/skillmaker/build_generic.py docs/adr/adr-0001.md --skill payments-adr --dry-run
python3 skill-maker/src/skillmaker/build_generic.py docs/adr/adr-0001.md --skill payments-adr
python3 skill-maker/src/skillmaker/build_generic.py notes.md --skill notes --profile generic
```

Two emission paths, chosen by the profile's shape. Unit-bearing kinds (ADR,
standards, pattern languages) go through the same engine as FPF and the DPFs --
indexes, manifest, prune, idempotent rewrite -- driven by the profile's grammar
instead of a prefix regex. Documents with no identifiers (guides, plain
Markdown) are copied whole into `reference/docs/` with an entry point, because
splitting them would invent structure the source does not have.

## Incremental builds

Every skill carries a build stamp (`.<skill>_build.json`) recording the digests
of its sources and of the engine that built it. When both match and every file
the manifest names still exists, the split is skipped. A no-change rebuild of
the split phase takes **under 2 s** instead of about 19 s; the tests that follow
dominate the wall clock (the whole build is about 1 min 45 s).

The stamp covers every module the engine imports, the whole `frameworks/`
package, the whole `templates/` tree and the resolved source paths -- so
editing a genre partial, a role template or a profile invalidates every skill,
which is the behaviour that keeps a cache from serving stale output.
`test_derived.py` proves it by touching a template and re-reading the digest.

## Cross-skill references

Publications cite each other across skill boundaries: a management pattern
citing `SYSE.24`, a DPF citing FPF `A.1`. `skills/CROSS-REFERENCES.md` lists
all 1349 such identifiers with the skill that owns each one, and the MCP server
resolves them without the table.

## Platforms

The toolchain is standard-library Python 3 and runs unchanged on Linux, macOS
and Windows. Three things needed care, and each is now an invariant above:

- **Console encoding.** A Windows console defaults to a legacy code page
  (cp1251, cp437), where printing a check mark or a non-ASCII pattern title
  raises `UnicodeEncodeError`. `ensure_utf8_stdio()` reconfigures stdout and
  stderr to UTF-8 in every entry point.
- **Child-process decoding.** The tests decode what they spawn with
  `encoding="utf-8"`. The default is the locale codec, which fails on the first
  non-ASCII byte -- it took down the FPF test run on a Russian Windows.
- **Newlines.** Generated files are written with `\n` rather than
  `os.linesep`, so the tree is byte-identical across platforms and `rebuild`
  compares exactly.

`build.cmd` and `build.ps1` run the same ten steps as `build.sh`; step 10, the
curl walkthrough, is skipped with a notice when `bash` is not installed rather
than failing the build.

## Test suites

`build.sh` runs all seven and stops at the first failure. 1 099 assertions in
total; the invariant list below is what they check.

| Suite | Assertions | What it covers |
| :--- | ---: | :--- |
| `test_fpf_pipeline.py` | 91 | FPF split, structure, SKILL.md, manifest, audit, byte-identical rebuild, bundled engine |
| `test_dpf_pipeline.py` | 539 | every DPF and Suite: catalogue, DocIDs, indexes, per-skill structure, front matter |
| `test_frameworks.py` | 116 | kind coverage, publisher agreement, parser agreement, generality, vendor/placeholder/portability sweeps |
| `test_build_generic.py` | 48 | ADR, standards, pattern language, whole documents, genre shapes |
| `test_mcp_server.py` | 118 | MCP protocol, reading-tool contract, derived tools, stdio client |
| `test_derived.py` | 158 | section map, routes, entries, glossary, genres, markers, build stamp |
| `test-mcp-http.sh` | 29 | Streamable HTTP: sessions, guards, `GET`/`DELETE`, curl only |

## Invariants the tests protect

- Every `.md` under `DPFs/` (except READMEs) is used by exactly one skill.
- Pattern counts equal the DPF catalogue (`DPFs/README.md`).
- DocIDs, titles and carrier paths equal `Library.Reference:11.1`.
- No file name contains `:`, so skills work on Windows as well.
- Every generated file is written with LF endings, so a Windows build produces
  the same bytes as a Linux build.
- No tracked toolchain file carries CRLF, so a Windows run cannot leave a
  template or a profile that the engine digest reads differently.
- Every subprocess is decoded as UTF-8 rather than with the locale codec, so a
  cp1251 or cp437 console cannot break a test run.
- Every manifest entry resolves to an existing file; stale files are pruned.
- Every framework in a Suite contributes its own front matter: intro file
  names are unique and carry the framework key.
- A rebuilt publication matches its source (FPF: byte-identical).
- The engine copied into `skills/fpf/scripts/skillmaker/` imports its own
  dependencies and rebuilds the publication without the repository.
- Every file copied into a skill is in the engine digest, so editing a bundled
  tool refreshes the copy instead of leaving it stale behind a current stamp.
- A second build writes zero files (idempotent).
- No `{{placeholder}}` survives into any generated file; only the templates
  under `scripts/` may contain one.
- `skills/README.md` and `skills/index.json` list every built skill.
- Section offsets account for every byte and never overlap.
- Routes reference existing units only; a dependency cycle terminates.
- Every built skill carries a `.skill.json` marker and resolves after a move.
- No generated file names a vendor product; copied publications are exempt.
- All 46 publications classify into the kind the catalogue assigns them.
- Every pattern count equals the publisher's (`catalogue.snapshot.json`).
- `frameworks` and `split_spec` agree on every unit heading (1445 across FPF
  Core and the 33 DPFs).

## Files

The toolchain is a package, not a folder of scripts: `src/skillmaker/` holds
everything the engine imports, `tests/` holds the suites that run it, and only
the three build entry points and the two design documents sit at the top.

```
skill-maker/
├── build.sh, build.cmd, build.ps1     # the ten-step build
├── README.md, FRAMEWORKS.md, AGENTS.md
├── src/skillmaker/
│   ├── split_spec.py                  # the engine
│   ├── skill_config.py                # the catalogue
│   ├── split_fpf_spec.py, split_dpf_spec.py, build_generic.py
│   ├── skill_index.py, mcp_server.py, http_transport.py
│   ├── audit_fpf_patterns.py, fpf_lookup.py, fpf_update.py, fpf_frameworks.py
│   ├── sections.py, derive.py, skill_root.py, _fpf_common.py
│   ├── frameworks/                    # kinds, grammars, shapes, profiles
│   ├── templates/                     # entry points + genres/ and roles/
│   └── catalogue.snapshot.json
└── tests/
    ├── test_*.py                      # six Python suites
    └── test-mcp-http.sh               # the curl walkthrough
```

Modules are run as files, never installed: every entry point puts `src/` on
`sys.path` for itself, so `python skill-maker/src/skillmaker/<module>.py`
works from any cwd and from inside a built skill.

| File | Role |
| --- | --- |
| `src/skillmaker/skill_config.py` | the catalogue: sources, DocIDs, suites, templates, outputs |
| `src/skillmaker/split_spec.py` | parser + writer + indexes + rebuild (the engine) |
| `src/skillmaker/_fpf_common.py` | identifier grammar, unit roles, slugs, fence tracking |
| `src/skillmaker/split_fpf_spec.py` | FPF CLI (`split`/`analyze`/`stats`/`rebuild`/`diff`) |
| `src/skillmaker/split_dpf_spec.py` | DPF CLI (`split`/`analyze`/`stats`/`rebuild`) |
| `src/skillmaker/skill_index.py` | writes `skills/README.md`, `index.json`, `CROSS-REFERENCES.md` |
| `src/skillmaker/build_generic.py` | builds a skill from any framework kind |
| `src/skillmaker/mcp_server.py` | serves the built skills over MCP (stdio, no dependencies) |
| `src/skillmaker/audit_fpf_patterns.py` | compares the FPF skill with its source |
| `src/skillmaker/fpf_lookup.py` | runtime search/read tools, bundled into `skills/fpf/scripts/` |
| `src/skillmaker/fpf_update.py` | download → split → audit → test pipeline |
| `src/skillmaker/frameworks/` | kinds, grammars, shapes, profiles, catalogue, decomposer |
| `src/skillmaker/fpf_frameworks.py` | CLI for `kinds`/`profiles`/`catalogue`/`probe`/`tree`/`plan` |
| `src/skillmaker/sections.py` | per-unit section map: anchors, tiers, line ranges, byte sizes |
| `src/skillmaker/derive.py` | routes, entries, glossary and boot, derived from the source |
| `src/skillmaker/frameworks/genre.py` | what a skill is for: `lookup`, `apply`, `setup`, `maintain` |
| `src/skillmaker/skill_root.py` | `.skill.json` marker, so a copied skill finds itself |
| `src/skillmaker/http_transport.py` | Streamable HTTP transport: sessions, guards, `/health` |
| `src/skillmaker/catalogue.snapshot.json` | saved publisher catalogue (`/api/publications`) |
| `src/skillmaker/templates/` | entry-point templates, plus the `genres/` and `roles/` partials |
| `tests/test_fpf_pipeline.py`, `tests/test_dpf_pipeline.py` | end-to-end tests |
| `tests/test_frameworks.py` | kind coverage, publisher agreement, generality, vendor and placeholder sweeps |
| `tests/test_build_generic.py` | ADR / standards / pattern-language / generic builds, genre shapes |
| `tests/test_mcp_server.py` | MCP protocol, reading-tool contract, tool behaviour |
| `tests/test_derived.py` | section map, routes, entries, glossary, genres, markers, build stamp |
| `tests/test-mcp-http.sh` | the HTTP transport, walked by curl with assertions |
| `FRAMEWORKS.md` | design of the general decomposition structure |
