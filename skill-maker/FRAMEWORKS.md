# Decomposing any kind of framework

`skill-maker` started with two hard-coded families — FPF Core and the DPFs —
and grew one config entry per publication. That worked for fifteen skills and
stopped there: a new publication meant editing `skill_config.py`, and a
framework the Library does not publish had no way in at all.

The `frameworks/` package replaces that with a structure. A framework is
described by **what kind of document it is**, and each kind states its own
**unit grammar** and **skill shape**. Decomposition then runs the same way for
all of them.

---

## 1. The taxonomy

The vocabulary is not invented here. A published catalogue classifies every
publication it serves with a `kind`, and the current one uses exactly four:

| kind | publications | what it is |
|---|---:|---|
| `FPF` | 1 | FPF Core: the shared pattern language |
| `DPF` | 33 | A domain pattern language |
| `Reference` | 4 | A DPF Suite Architectural Reference |
| `Guide` | 8 | An introduction or working instruction |

46 publications in total, carrying **885 patterns** — the same figure the
Library front page reports as "885 patterns & other named entries".

Four kinds are not enough to answer *"decompose all types of frameworks"*,
because the frameworks a team actually holds are rarely Library publications.
So `PublicationKind` also carries the kinds the toolchain can already handle
without any new parsing code:

| kind | example heading | unit |
|---|---|---|
| `ADR` | `## ADR-0007 - Choose a broker` | a decision record |
| `Standards` | `## 4.3.2 Architecture rationale` | a clause |
| `PatternLanguage` | `## 12. THE GATE` | a numbered pattern |
| `Generic` | `## How to upgrade` | a section, keyed by its slug |

`Generic` is the fallback. Every Markdown document decomposes into something
retrievable, which is the difference between a tool for the Library and a tool
for frameworks.

---

## 2. What a decomposition produces

Measured on the current tree:

| kind | publications | units | patterns | other units |
|---|---:|---:|---:|---:|
| `FPF` | 1 | 418 | 397 | 21 reference |
| `DPF` | 33 | 1027 | 488 | 539 reference / application / sources |
| `Reference` | 4 | 53 | 0 | 53 reference |
| `Guide` | 8 | 58 | 0 | 58 sections |
| **total** | **46** | **1556** | **885** | 671 |

The pattern count is the load-bearing number: it is what the Library catalogue
publishes, and `test_frameworks.py` checks every one of the 46 against it.

---

## 3. Genre: what the skill is *for*

Kind says what a document is. Genre says why someone opens it, and that decides
two things the data does not: the middle of `SKILL.md`, and which roles ship.

| Genre | Roles | Middle section |
| :--- | :--- | :--- |
| `lookup` | none | indexes, tiers, stop rule |
| `apply` | classifier -> retriever -> reasoner -> reviewer | scope, pipeline, answer shape |
| `setup` | installer -> validator | routes, four layers of evidence |
| `maintain` | sync | check, rebuild, verify, report |

A role is a division of work, not a requirement to spawn agents. `lookup` ships
no `roles/` directory at all rather than an empty one.

Adding a genre is a partial under `templates/genres/` plus an entry in
`frameworks/genre.py`. Adding a role is a file under `templates/roles/` and a
one-line question in `split_spec.ROLE_QUESTIONS`.

## 4. Reading less than a unit

`sections.py` derives the section map from each unit's own headings. It exists
because a pattern is one file but not one reading:

| | FPF Core | Systems Engineering |
| :--- | ---: | ---: |
| median unit | 33 KB | 19 KB |
| largest unit | 258 KB | 79 KB |
| working sections | 60% | 56% |

The tiers follow the sections the publications actually use. Across the built
tree there are 11 378 sections under 1 234 distinct titles; the working ones
are the frequent ones -- `relations` 862, `forces` 841, `problem frame` 835,
`consequences` 829, `problem` 828, `solution` 793, `conformance checklist` 788
-- against the depth ones -- `common anti-patterns and how to avoid them` 722,
`SoTA-echoing` 720, `bias-annotation` 693, `archetypal grounding` 641,
`rationale` 474.

Titles vary by publication (`use this when` 252, `architectural rationale` 331),
which is why the tier is decided by prefix rather than by an exact list.

Offsets rather than files: the working sections are not contiguous (in `A.1`
they run `:4`, `:7`, `:9`, `:12`), so selecting them needs ranges, not
truncation. `--views` materialises them for readers without section-aware
tooling; the unit file stays canonical either way.

## 5. Derived artefacts

Four files the source cannot contain, because it is organised for reading rather
than retrieval:

| File | Question | Derived from |
| :--- | :--- | :--- |
| `routes.json` | what must I read first? | the `Builds on` column |
| `entries.json` / `.md` | where do I start with this situation? | each unit's own queries |
| `glossary.md` | what does this term mean, in one line? | each unit's opening |
| `boot.md` | what do I read before anything else? | the build itself |

All are marked `derived: true`. A hand-written route goes in
`curated-routes.json`, which the builder never overwrites, and wins on its own
id.

The glossary takes its line from the unit's own opening and removes only a
lead-in such as "Use this pattern when", so it quotes rather than paraphrases:
a generated definition that rewrites freely is a claim the source does not
make.

## 6. The pipeline

```
catalogue  ──►  detect  ──►  grammar  ──►  units  ──►  shape  ──►  artefacts
   │             │             │             │           │           │
   │             │             │             │           │           └ build_generic.py
   │             │             │             │           └ what to write   writes them
   │             │             │             └ UnitTree: ids, roles, lines
   │             │             └ what counts as a unit heading
   │             └ which profile claims this document, and why
   └ which publications exist, locally and at the publisher
```

Each arrow is a module, and each module can be inspected on its own:

| module | question it answers |
|---|---|
| `kinds.py` | what kinds of framework exist |
| `grammar.py` | what counts as an addressable unit in a kind |
| `shape.py` | what artefacts a decomposition produces |
| `profile.py` | one kind, end to end: identity + detection + grammar + shape |
| `decompose.py` | what are the units of this document |
| `catalogue.py` | what publications exist, and do they match the publisher |
| `registry.py` | which profile claims this document |

`split_spec.py` keeps its job — writing skill directories. It is no longer the
place where a framework's identity is decided.

---

## 7. The profile contract

A `DecompositionProfile` is the unit of extension. Four fields are
required (`key`, `kind`, `name`, `description`), two decide the decomposition
(`grammar`, `shape`), and four more are optional detection hints:

```python
DecompositionProfile(
    key="dpf-framework",              # stable id
    kind=PublicationKind.DPF,         # which kind this is
    name="Domain Principle Framework",
    description="Flat tree per framework: patterns plus reference units.",
    grammar=DOTTED,                   # how headings split
    shape=DPF_SKILL,                  # what gets written
    path_globs=("DPFs/*.md", ...),    # detection by path
    header_markers=("**DocID:**",),   # detection by header
    docid_prefix=True,                # ID prefix comes from the publication
)
```

`docid_prefix=True` is why one profile serves 33 publications: each DPF
declares `**DocID:** `SYSE``, and the grammar binds itself to that prefix. A
DPF that forgot its header is still recognised — the prefix is recovered from
the first dotted heading.

`fixed_prefix` covers the opposite case: FPF Core declares `DocID: FPF` but
publishes `A.1`…`K.x`, so its prefix is a regex fragment, not a DocID.

---

## 8. Adding a kind

Three steps, no engine changes:

```python
# 1. frameworks/profiles/decision_log.py
from ..grammar import ADR
from ..kinds import PublicationKind
from ..profile import DecompositionProfile
from ..shape import REFERENCE_SKILL

PROFILE = DecompositionProfile(
    key="adr", kind=PublicationKind.ADR, name="Architecture Decision Record set",
    description="One file per decision: context, decision, consequences.",
    grammar=ADR, shape=REFERENCE_SKILL,
    path_globs=("**/adr/*.md", "**/adr-*.md"),
    header_markers=("## Status", "## Consequences"),
)
```

```python
# 2. frameworks/profiles/__init__.py
PROFILES = (..., adr.PROFILE, generic.PROFILE)
```

```bash
# 3. check it
python skill-maker/src/skillmaker/fpf_frameworks.py probe docs/adr/adr-0001.md
```

That is the whole extension story. `adr`, `standards` and `pattern-language`
in `profiles/` are the worked examples.

---

## 9. Detection is scored, not guessed

`probe` prints the evidence, so a surprising classification can be explained:

```
$ python skill-maker/src/skillmaker/fpf_frameworks.py probe DPFs/README.md
  kind       Guide -- Guide
  profile    guide (Guide)
  evidence   path~DPFs/README.md (score 114)
  grammar    level ##, id=(?:[A-Za-z][A-Za-z0-9]*)(?:[.:]...)+, sep=[-–—:], roles=dotted
  units      5 (0 patterns, 5 other)
```

The scoring has three sources:

* **path globs** — decisive for documents published under known names;
  specificity breaks ties, so `**/README.md` beats `DPFs/*.md` and a Suite
  README is a guide, not a DPF;
* **header markers** — for documents found anywhere;
* **heading structure** — the fraction of `##` headings the grammar recognises.

Two guards keep the structural signal honest:

* a grammar with **no identifier requirement** scores zero, because it matches
  every heading and therefore carries no evidence;
* fewer than **three** unit headings is a coincidence, not a grammar.

Without the first guard, the DPF profile "matched" every README perfectly and
outranked the guide profile on structure alone — the exact failure that
`test_frameworks.py` now pins.

---

## 10. Verification against the publisher

`catalogue.snapshot.json` is a saved copy of `/api/publications`
(snapshot `20261018T215642Z`, 46 publications, 885 patterns). It exists so the
tests compare the decomposition to **the publisher**, not to the previous build:

```
$ python skill-maker/src/skillmaker/fpf_frameworks.py catalogue --verify
Publisher catalogue: 20261018T215642Z-2f2973dc00742cd6 (46 publications, live)

✅ 46 publications agree with the publisher (kind and pattern count).
```

`--offline` uses the saved copy, `--counts` decomposes each publication to fill
in the pattern column, and `--json` emits the whole register.

---

## 11. Agreement with the existing engine

Two parsers now exist: `split_spec.build_heading_re` (which writes the skills)
and `frameworks.grammar` (which plans and classifies). They must not disagree,
so `test_frameworks.py` runs both over every heading of FPF Core and all 33
DPFs and asserts identical `(id, title)` results — 1445 unit headings, zero
disagreements.

This is also why the dotted grammar keeps the lookahead `(?=\s|$)`: a
relaxed lookahead lets `## FPF.Reference:End` split at its own colon into unit
`FPF.Reference` + title `End`. Only grammars whose separator *abuts* the
identifier (`## 12. THE GATE`) may relax it, via `id_abuts_separator=True`.

---

## 12. CLI

```
python skill-maker/src/skillmaker/fpf_frameworks.py kinds
python skill-maker/src/skillmaker/fpf_frameworks.py profiles
python skill-maker/src/skillmaker/fpf_frameworks.py catalogue [--verify] [--offline] [--counts] [--json]
python skill-maker/src/skillmaker/fpf_frameworks.py probe PATH... [--all]
python skill-maker/src/skillmaker/fpf_frameworks.py tree PATH [--limit N] [--role pattern|all]
python skill-maker/src/skillmaker/fpf_frameworks.py plan PATH [--skill NAME] [--json]
```

`tree` and `plan` are the review tools: they show what would be generated
before anything is written.

---

## 13. File map

```
skill-maker/src/skillmaker/
  frameworks/
    __init__.py            public API (re-exports)
    kinds.py               PublicationKind + KindInfo
    grammar.py             UnitGrammar, ready-made grammars, docid_of
    shape.py               SkillShape, Layout, shape presets
    profile.py             DecompositionProfile, Detection, scoring
    decompose.py           Unit, UnitTree, Decomposer
    catalogue.py           Publication, load_local, load_remote, verify
    registry.py            detect / classify / register
    profiles/
      __init__.py          PROFILES (most specific first)
      fpf_core.py          FPF-Spec.md
      dpf_framework.py     33 DPFs
      suite_reference.py   4 Suite References
      guide.py             8 guides
      adr.py               extension: decision records
      standards.py         extension: clause-numbered standards
      pattern_language.py  extension: Alexander-style patterns
      generic.py           fallback: any Markdown
  fpf_frameworks.py        CLI
  catalogue.snapshot.json  saved publisher catalogue
  sections.py              per-unit section map: anchors, tiers, offsets
  derive.py                routes, entries, glossary, boot
  skill_root.py            .skill.json marker
  http_transport.py        Streamable HTTP transport
  test_frameworks.py       kind coverage and generality
  test_derived.py          section map, routes, genres, markers
```

---

## 14. Deliberate limits

* **Units are `##`-level.** Nested `###` headings count as subsections, not as
  units. FPF Core publishes 5572 `###` headings; promoting them to files would
  turn a 418-file skill into a 6000-file one.
* **Tables of contents are not parsed here.** `split_spec` still reads them for
  keywords, statuses and dependencies. The decomposer reports what the
  headings say.
* **Guides and generic Markdown ship whole, not split.** `GUIDE_SKILL` copies
  the document into `reference/docs/` and writes an entry point, which is what
  an agent needs from a guide. `build_generic.py` implements this; unit-bearing
  kinds (ADR, standards, pattern languages) go through the full engine.
* **Routes are derived, not curated.** The chain is the transitive `Builds on`
  closure. For a densely connected publication that can name half the skill,
  which is true but not a reading order on its own -- hence `direct` alongside
  `chain`, and the curated slot for a better answer.
* **Tier classification is by section title.** A unit whose working sections
  are named unconventionally lands wholly in `source`. That is visible (the
  budget columns show it) rather than silent.
* **Section counts are not verified.** They count every heading including
  fenced examples, so they are a publisher-side rendering detail rather than a
  decomposition fact. Pattern counts are verified; section counts are not.
