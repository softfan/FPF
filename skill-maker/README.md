# skill-maker — build agent skills from Markdown frameworks

This directory turns Markdown publications into **skills**: directories an
AI agent can navigate without loading multi-megabyte files. One parser
(`split_spec.py`) builds them; `discover_skills.py` combines automatic local
discovery with the curated names and groupings in `skill_config.py`.

```
bash skill-maker/build.sh             # or build.ps1 / build.cmd on Windows
```

## Supported input structures

The input documents determine the skills, Suites, patterns and reference units.
There is no expected corpus size or fixed publication inventory. Profiles
describe supported structures; curated configs supply optional naming/grouping.

| Kind | What it is | Where |
| --- | --- | --- |
| **FPF Core** | Shared pattern language with an optional embedded Architectural Reference | `FPF-Spec.md` |
| **DPF Suites** | Constituent frameworks plus a Suite Architectural Reference | `DPFs/<Suite> DPF Suite/` |
| **Standalone DPFs** | A domain framework document | `DPFs/*.md` |
| **Other Markdown** | ADRs, standards, pattern languages, guides and prose | `frameworks/**/*.md` or explicit source roots |

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
section inside it. DocIDs and units come from the input; they are not an
enumeration embedded in the generic engine.

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

Index files are named after what they index, not after who they are for.
`docs/` and `intro/` keep whole documents and front matter distinct from units.

### Which skills are produced

Skill directory names say what the skill is. The DocID stays the framework key
(`reference/psda/PSDA.1.md`), so pattern IDs keep working.

The discovery plan is the current inventory:

```bash
python3 skill-maker/src/skillmaker/discover_skills.py --json
```

Names and Suite membership are derived from the current files, with existing
curated naming/grouping overrides taking precedence. Do not copy a build's
totals into configuration or documentation as expected values.

`skills/README.md` is generated and lists all built skills with their DocIDs, counts
and when to use each. `skills/index.json` carries the same facts plus a
DocID → skill routing table, so a caller holding `PSDA.1` can find
`decision-design` without knowing the mapping.

## Automatic discovery: adding a framework

Put new Markdown publications in **`DPFs/`** or **`frameworks/`** at the repository
root, then run the normal build. No `DPFSpec`, pattern-count constant or new
Suite entry is required for these additions. Discovery is offline and uses the
registered profiles (path, header and heading structure), not an external service.

| Input | Result |
| --- | --- |
| `DPFs/EXAMPLE-DPF.md` declaring DocID `XYZ` | `skills/xyz/` |
| A new DPF beside the members of an existing Suite | Added to that Suite's skill |
| `DPFs/Example DPF Suite/` with at least one DPF and exactly one `*-SUITE-REFERENCE.md` | `skills/example-suite/`, including its README as a whole document |
| `frameworks/adr-payments.md`, `frameworks/iso-example.md`, a pattern language or plain Markdown | One skill per document, using a lower-case hyphenated filename stem when no DocID is declared |

Present curated inputs such as `decision-design` and `engineering-suite` keep
their paths and grouping. A declared DocID determines a new skill's name and
reference directory; without one, a DPF's single heading prefix may be inferred.
`DPFs/README.md` and the existing Suite READMEs stay navigation, not separate skills.

Preview without writing:

```bash
python3 skill-maker/src/skillmaker/discover_skills.py --dry-run
python3 skill-maker/src/skillmaker/discover_skills.py --json
```

Build discovered and curated skills, then refresh the index (the normal build
already does both):

```bash
python3 skill-maker/src/skillmaker/discover_skills.py --views
python3 skill-maker/src/skillmaker/skill_index.py
```

`split_dpf_spec.py split --all` also discovers new DPF-side skills; individual
`--framework XYZ` and `--suite example` selections work for discovered
frameworks and Suites. `skills/index.json` and DocID routing use the same plan.

For a private corpus without the curated FPF publications:

```bash
python3 skill-maker/src/skillmaker/discover_skills.py --repo-root /path/to/corpus --unconfigured --dry-run
# Repeat --source-root to replace the default DPFs/ and frameworks/ roots:
python3 skill-maker/src/skillmaker/discover_skills.py --unconfigured --source-root docs/decisions --dry-run
```

Relative `--source-root` and `--output` paths are relative to `--repo-root`.
Discovery never scans outside that repository or follows symbolic links.
It rejects duplicate DocIDs, unit IDs and normalized filenames, skill-name
collisions, ambiguous profile matches and incomplete Suites. Before building,
it checks every destination: nonempty directories without a matching skill and
source marker are not overwritten. Renaming/moving a source requires an explicit
ownership decision; old generated directories are **not** automatically deleted.

Curated entries are optional overrides for source files present in the input;
they do not require absent publications to exist. An explicitly supplied
configuration still requires all of its declared sources.

Use `skill_config.py` when you want a curated name, description or explicit
grouping, or to move a curated source. Those entries override discovery by
claiming their source paths. A new heading format still needs a profile; use
`build_generic.py --profile KEY` for a deliberate one-document override.

Build validation compares current sources with generated unit identities,
roles, files and rebuilt content. No publisher snapshot or fixed totals are
required. Publisher comparison is optional: supply your own catalogue with
`fpf_frameworks.py catalogue --verify --offline --snapshot PATH`. Add
`--allow-local` to report extra local publications without failing comparison.

## Decomposing other kinds of framework

`skill_config.py` holds curated naming and grouping overrides. A
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
bash skill-maker/build.sh                          # bash
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

The lookup tool parses the small Markdown indexes and caches them only in memory.
Old `.fpf_index.pickle` files are ignored, never deserialized. Pattern IDs cannot
be paths, and index/document/intro symlinks must not escape the skill root.
Reconstruction also validates each manifest path and fails on missing inputs
before writing its output; it does not silently emit a partial publication.

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
python3 -c "import sys; sys.path.insert(0,'skill-maker/src'); from skillmaker import sections as s; \
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
python3 skill-maker/run-mcp.py --selftest          # no client needed
bash skill-maker/run-mcp.sh                       # stdio (default)
bash skill-maker/run-mcp.sh --http                # http://127.0.0.1:8765/mcp
```

On Windows (native Python, no Bash/WSL):

```powershell
skill-maker\run-mcp.ps1                           # stdio
skill-maker\run-mcp.ps1 --http 127.0.0.1:8765       # HTTP, Ctrl+C to stop
skill-maker\run-mcp.cmd --http                    # cmd alternative
```

The runners work from any working directory, defaulting to this repository's
built `skills/`. Build first; starting the server never builds or downloads
anything. All server options are forwarded unchanged, including `--help`,
`--list-tools`, `--selftest`, `--skills-root PATH` and `--allow-maker-tools`.
An explicit relative `--skills-root` stays relative to the caller's directory.
The shell/native wrappers respect `PYTHON` (`python3` on Bash, `python` on
PowerShell/cmd by default); invoking `run-mcp.py` directly uses your chosen
interpreter. The server runs in the foreground and stdout remains the MCP
stream, with startup diagnostics on stderr.

For an MCP client's stdio command, use an absolute interpreter and script path,
for example `python C:/X/FPF-skills/fpf10/skill-maker/run-mcp.py` (as separate
command/argument entries). No client working-directory setting is required.

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

The local walkthrough waits up to 60 seconds for corpus loading before failing
readiness; override with `MCP_STARTUP_TIMEOUT` (1–3600 seconds). It bypasses
proxies for the child server and uses real temporary files instead of a POSIX
null-device path, including with Windows `curl.exe`. On failure it reports the
last health-probe error and server log, retaining its private diagnostic directory.
PowerShell/cmd builds run the native Python equivalent automatically, without
Bash/curl/WSL. To retry just that step from Windows PowerShell after building:

```powershell
python skill-maker/tests/test_mcp_http.py --startup-timeout 120
```

The native test launches the server with `sys.executable` (printed at startup),
uses an OS-selected free loopback port and stops its child even on failure.
It mirrors the shell's 29 checks and retains diagnostics on failure. The shell
walkthrough remains available separately, including for remote endpoints; an
explicit `PYTHON` is never silently replaced and Python below 3.9 is rejected.

Optional startup regressions (requires Bash and curl, separate from the default
suite): `python skill-maker/tests/test_http_startup.py`. They simulate slow
startup, a broken proxy, Windows-style Python stdout, a child-process crash and
a readiness timeout. JSON helper output has no trailing newline, avoiding CRLF
in Bash numeric/string comparisons when the interpreter is native Windows Python.

`skills/CONNECT.md` is the generated connection guide: transports, endpoint,
tool table, the four layers of evidence, and a by-hand curl walkthrough.

The reading corpus is frozen in memory at server startup. Its snapshot hashes
the reading artefacts, not just index counts: a text-only revision changes it.
Every reading response carries the snapshot; restart after rebuilding to serve
the new edition. A running process continues serving its original edition.
Finish the build before starting: startup rechecks file contents and membership
and refuses a corpus that changes during loading. Manifest paths must stay inside
their own skill, not merely somewhere inside the corpus root.

HTTP exposes the ten reading/derived tools by default. Add `--allow-maker-tools`
only for trusted clients that need document classification and decomposition.
Document tools accept repository-relative regular Markdown files up to 32 MiB,
and reject absolute paths and symlink escapes. `verify_catalogue` is offline
unless explicitly called with `offline: false`.

The local HTTP transport limits bodies to 1 MiB, socket reads to 10 seconds,
connections to 32, and sessions to 1024 with a one-hour lifetime. It has no
authentication or TLS. Do not expose it directly to the internet: shared hosting
requires a maintained reverse proxy providing authentication, TLS and rate limits.

It serves whatever was built here -- a patched edition, a private framework or
an ADR set -- across the current built corpus, without assuming how many skills
or unit files it contains.

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

The fingerprint also includes all declarative configuration fields (including
genre, grammar and views) and the optional `curated-routes.json`. The existing
hash registry lists every generated output; bytes are checked against it, so
deleting or corrupting a derived file or an individual view triggers repair.
Malformed cache files are rebuilt rather than trusted. The manifest has its own
digest in the build stamp, so edits to cached metadata cannot silently change
the reconstructed publication. The registry itself is digested too, so deleting
an entry cannot hide a missing output. Source hashes preserve individual file
boundaries and distinguish empty publications from missing sources.

## Cross-skill references

Publications cite each other across skill boundaries: a management pattern
citing `SYSE.24`, a DPF citing FPF `A.1`. `skills/CROSS-REFERENCES.md` lists
all 1349 such identifiers with the skill that owns each one, and the MCP server
resolves them without the table.

## Platforms

The toolchain requires standard-library Python 3.9+ and runs on Linux, macOS
and Windows. Portability is protected by the following invariants:

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
- **Existing hidden/system files.** Windows may reject a create-and-truncate
  open on a hidden/system file even when writing is allowed. `write_text_lf`
  opens without `O_TRUNC` and truncates the opened handle, preserving attributes
  and ACLs. It does not clear ReadOnly, bypass locks or change permissions. If a
  manifest remains inaccessible, inspect it with `Get-Item -Force <path> |
  Format-List FullName,Attributes` and check permissions/other processes; do not
  recursively clear attributes or run the build as Administrator as a default fix.

`build.cmd` and `build.ps1` run the same ten steps as `build.sh`; step 10 uses
`test_mcp_http.py` and the build's own Python, not whichever `bash.exe` PATH
selects. On Windows that command can be WSL, whose older Linux Python and
environment are independent of the working Windows interpreter. No Bash is
required for these build entry points. `build.sh` retains the curl walkthrough.

## Test suites

All three build scripts run the offline suites below and stop at the first
failure. Assertion totals vary with the local corpus and available platform
wrappers. `test_hardening.py` covers malformed requests, snapshots, boundaries,
cache repair and updates.

| Suite | What it covers |
| :--- | :--- |
| `test_fpf_pipeline.py` | Current source split, manifest, audit, reconstruction and bundled engine |
| `test_dpf_pipeline.py` | Discovered frameworks and Suites: source identity, unit inventory, indexes and reconstruction |
| `test_frameworks.py` | Source-to-manifest agreement, parser agreement, generality and portability |
| `test_build_generic.py` | ADR, standards, pattern language, whole documents and genre shapes |
| `test_mcp_server.py` | MCP protocol, reading-tool contract, derived tools and launchers |
| `test_discovery.py` | Automatic discovery, variable input inventories, routing and output preflight |
| `test_derived.py` | Section maps, routes, entries, glossary, genres, markers and build stamps |
| `test-mcp-http.sh` | Streamable HTTP walkthrough with curl |
| `test_mcp_http.py` | Native HTTP walkthrough used by PowerShell/cmd |
| `test_hardening.py` | Malformed requests, boundaries, cache repair and transactional updates |

On Windows the hardening suite additionally exercises real Hidden/System and
ReadOnly file attributes. Its total varies with platform support for symlinks
and special files; Windows-only checks are not counted as Linux executions.

A user-provided native Windows 10 run of `build.ps1` with Python 3.13.7 passed
its regression suites and FPF audit. This confirms that configuration, not every Windows/Python version;
the native cmd entry point has not yet been execution-verified.

`test_http_startup.py` adds optional startup/regression checks, separate from
default totals; these include a native run with an empty PATH, broken proxy and
unusable `PYTHON` override, plus child lifecycle and shell fallback checks.

## Optional skill quality evaluations

`evals/cases.json` and `evals/README.md` define three realistic tasks, paired
with/without-skill comparisons, positive/negative trigger queries and an evidence
rubric. These are not run against a model in the default build. Only their format
and generated metadata constraints are checked offline. Obtain usage approval
before running model evaluations; no quality gain is claimed without results.

## Updating source editions

`fpf_update.py` resolves upstream `main` to one commit and stages all requested
documents before replacing any local source. Failed downloads leave the local
sources unchanged. `--dpfs` includes the local DPFs, Suite References and README
pages, then rebuilds all DPF skills and the common index and runs DPF/framework
checks too. This remains an explicit network operation, never part of a build.
Review the resulting source diff before retaining an update; the updater does
not discover upstream additions or renames not present in the local catalogue.
If source replacement fails, rollback is attempted for every affected file. An
incomplete rollback is reported explicitly and original bytes are preserved in
a recovery directory; the command never reports that as a successful update.
Symlink or outside-root destinations are rejected before contacting upstream.
Downloaded publications must be nonempty UTF-8 and no larger than 64 MiB.

`build_generic.py` refuses an output directory containing its source or the
engine, an unmarked nonempty directory, or an existing skill with a different
name. Output directories are disposable: retain personal material outside them,
except the explicitly preserved `curated-routes.json`.

## Invariants the tests protect

- Every `.md` under `DPFs/` (except READMEs) is used by exactly one skill.
- Generated unit identities and roles match the current source documents.
- Declared DocIDs agree with their source ownership and generated routing.
- New local documents are classified and assigned once; discovery is read-only,
  deterministic and rejects ambiguous or colliding ownership before writing.
- No file name contains `:`, so skills work on Windows as well.
- Every generated file is written with LF endings, so a Windows build produces
  the same bytes as a Linux build.
- Engine sources, templates and data use LF; only the native Windows build
  entry points use CRLF in the working tree. A Windows run cannot leave a
  template or profile that the engine digest reads differently.
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
- Publications classify using registered profiles, without a fixed inventory.
- `frameworks` and `split_spec` agree on current unit headings.

## Files

The toolchain is a package, not a folder of scripts: `src/skillmaker/` holds
everything the engine imports, `tests/` holds the suites that run it, and
`evals/` holds opt-in quality scenarios.

```
skill-maker/
├── .gitignore, .gitattributes          # local exclusions and line endings
├── build.sh, build.cmd, build.ps1     # the ten-step build
├── run-mcp.py, run-mcp.sh, run-mcp.cmd, run-mcp.ps1  # foreground MCP launchers
├── README.md, FRAMEWORKS.md, AGENTS.md
├── evals/                             # optional paired/trigger quality scenarios
├── src/skillmaker/
│   ├── split_spec.py                  # the engine
│   ├── skill_config.py                # the catalogue
│   ├── discover_skills.py             # local discovery + curated overrides
│   ├── split_fpf_spec.py, split_dpf_spec.py, build_generic.py
│   ├── skill_index.py, mcp_server.py, http_transport.py
│   ├── audit_fpf_patterns.py, fpf_lookup.py, fpf_update.py, fpf_frameworks.py
│   ├── sections.py, derive.py, skill_root.py, _fpf_common.py
│   ├── frameworks/                    # kinds, grammars, shapes, profiles
│   └── templates/                     # entry points + genres/ and roles/
└── tests/
    ├── test_*.py                      # regression suites + optional startup checks
    └── test-mcp-http.sh               # the curl walkthrough
```

Modules are run as files, never installed: every entry point puts `src/` on
`sys.path` for itself, so `python skill-maker/src/skillmaker/<module>.py`
works from any cwd and from inside a built skill.

| File | Role |
| --- | --- |
| `src/skillmaker/skill_config.py` | the catalogue: sources, DocIDs, suites, templates, outputs |
| `src/skillmaker/discover_skills.py` | discover local publications, validate the complete plan, build with existing profiles |
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
| `src/skillmaker/templates/` | entry-point templates, plus the `genres/` and `roles/` partials |
| `tests/test_fpf_pipeline.py`, `tests/test_dpf_pipeline.py` | end-to-end tests |
| `tests/test_frameworks.py` | current input coverage, source-to-manifest agreement, generality and portability |
| `tests/test_build_generic.py` | ADR / standards / pattern-language / generic builds, genre shapes |
| `tests/test_discovery.py` | offline discovery, suite grouping, naming, selection, routing and output-safety regressions |
| `tests/test_mcp_server.py` | MCP protocol, reading-tool contract, tool behaviour |
| `tests/test_derived.py` | section map, routes, entries, glossary, genres, markers, build stamp |
| `tests/test-mcp-http.sh` | the HTTP transport, walked by curl with assertions |
| `tests/test_mcp_http.py` | native HTTP subprocess walkthrough for PowerShell/cmd |
| `tests/test_hardening.py` | protocol, cache, update, path and file-output regressions |
| `tests/test_http_startup.py` | optional startup, interpreter and child-cleanup regressions |
| `FRAMEWORKS.md` | design of the general decomposition structure |

## Release checklist

`skill-maker/.gitignore` and `.gitattributes` apply recursively to the toolchain.
Source, tests, templates and evaluation fixtures belong in the release; caches,
logs, virtual environments, generated skills and local evaluation results do not.
Temporary implementation plans and review reports are not release documentation.

1. Run the full build from the repository root using the target platform's entry
   point. Inspect the FPF audit separately: it is non-fatal in the build scripts.
2. Check the offline catalogue, generated index and MCP server:

   ```bash
    python skill-maker/src/skillmaker/fpf_frameworks.py catalogue --counts
   python skill-maker/src/skillmaker/skill_index.py --check
   python skill-maker/src/skillmaker/mcp_server.py --selftest
   ```

3. Optionally run `python skill-maker/tests/test_http_startup.py` with Bash/curl
   available. Model-quality evaluations remain a separate, opt-in activity.
4. Repeat the split phase without source edits and confirm zero writes. Keep
   input documents unchanged unless a source-edition update is explicitly part
   of the release. Never pin the new corpus totals in implementation or tests.
5. Run `git diff --check` and inspect `git status --short --untracked-files=all`.
   Include the new source/tests/configuration, but no local credentials, caches
   or machine-specific logs. Preserve the repository's license notices.

The toolchain is run directly from this repository, not installed as a package.
The publications and licensing files at the repository root are required release
inputs; `skill-maker/` alone is not a standalone distribution. Committing, tagging
and publishing are separate operations after verification and approval.
