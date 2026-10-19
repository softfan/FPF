#!/usr/bin/env python3
"""
skill_config.py -- Declarative skill definitions for the skill-maker toolchain.

Every generated skill is described by a :class:`SkillConfig`: where its source
documents live, how each document is split into addressable units, which
templates to use and where the output goes.  The generic engine
(``split_spec.py``) reads these configs, so FPF Core, the four DPF Suites and
the ten standalone DPF frameworks all share one parser and one writer.

Library layout reproduced here (see ``FPF-LIBRARY-REFERENCE.md`` and
``DPFs/README.md``):

* **FPF Core** -- ``FPF-Spec.md`` plus the Library documents ``USING-FPF.md``
  and ``FPF-LIBRARY-REFERENCE.md`` (shipped inside the skill as reference
  documents).
* **Four DPF Suites** -- Engineering, Management, Foundational Thinking and
  Human Capability Engineering.  A Suite skill holds its constituent
  frameworks plus the Suite Architectural Reference.
* **Ten standalone DPFs** -- frameworks published directly in ``DPFs/``.

Each source document is parsed with the same rules: a ``## <ID> - <Title>``
heading starts an addressable unit; units whose first segment is numeric are
patterns, units such as ``SYSE.Reference:1``, ``PSDA.Application:3`` or
``PSDA.Sources:2`` are reference units of their role.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern

from _fpf_common import ID_SEGMENT_RE

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

#: Root of the DPF catalogue (``DPFs/`` with its Suite sub-folders).
_DPF_ROOT = _REPO_ROOT / "DPFs"


# ---------------------------------------------------------------------------
# Document specs
# ---------------------------------------------------------------------------

@dataclass
class FrameworkSpec:
    """One framework document and the rules to split it into units."""

    key: str
    """Sub-directory name under ``reference/`` (e.g. ``fpf-patterns``, ``syse``)."""

    prefix_re: str
    """Regex fragment matching this document's unit-ID prefix.

    FPF uses ``[A-K]`` (plus ``FPF`` for the embedded Architectural
    Reference); DPF frameworks use a word token such as ``SYSE``."""

    source: Path
    """Path to the source Markdown document."""

    name: str
    """Human-readable framework name (indexes, SKILL.md)."""

    description: str
    """One-line description used in the domain block."""

    docid: str = ""
    """Publication DocID declared in the Library catalogue (e.g. ``SYSE``)."""

    domains: Dict[str, str] = field(default_factory=dict)
    """Mapping from domain key -> description (FPF: letter parts, DPF: DocID)."""

    domain_prefix_re: str = ""
    """Regex capturing the domain key from a unit ID."""

    role: str = "framework"
    """``framework`` for pattern sources, ``reference`` for a Suite Reference."""

    grammar: Any = None
    """Optional :class:`frameworks.grammar.UnitGrammar`.

    When set, the grammar decides what counts as a unit heading and how units
    are named, instead of the prefix-derived regex.  This is what lets the
    engine build frameworks whose IDs are not dotted (``ADR-0007``,
    ``4.3.2``, ``12.``)."""

    @property
    def id_re(self) -> Pattern:
        return re.compile(r"^(?:" + self.prefix_re + r")" + ID_SEGMENT_RE + r"$")

    def domain_of(self, pattern_id: str) -> str:
        if self.domain_prefix_re:
            m = re.match(self.domain_prefix_re, pattern_id)
            if m:
                return m.group(1)
        m = re.match(r"^(" + self.prefix_re + r")", pattern_id)
        return m.group(1) if m else pattern_id[0]


@dataclass
class DocSpec:
    """A whole document shipped inside a skill (no unit splitting)."""

    source: Path
    slug: str
    """Output file stem: ``reference/<slug>.md``."""

    title: str
    description: str

    docid: str = ""
    """DocID declared by the document, when it has one (``Library``)."""


# ---------------------------------------------------------------------------
# Skill config
# ---------------------------------------------------------------------------

TOC_HEADING_RE = r"^#\s+Table\s+of\s+Content"
H1_RE = r"^#\s+(.+)$"
H2_RE = r"^##\s+(.+)$"
FENCE_OPEN_RE = r"^(`{3,}|~{3,})"


@dataclass
class SkillConfig:
    """Everything the generic engine needs to build one skill directory."""

    name: str
    """Skill key, e.g. ``fpf``, ``engineering``, ``syse``."""

    output: Path
    """Output directory (``skills/<name>``)."""

    frameworks: List[FrameworkSpec] = field(default_factory=list)
    """Source documents split into addressable units."""

    docs: List[DocSpec] = field(default_factory=list)
    """Whole documents copied into ``reference/`` (Library guidance etc.)."""

    title: str = ""
    """Human-readable display name."""

    prefix_token: str = ""
    """Short ID prefix shown in the skill front matter (``SYSE``, ``FPF``)."""

    # --- TOC / row parsing ---
    toc_id_location: str = "section"
    """``section`` (FPF: ID in the "§" column), ``id_title`` (DPF: ID inside the
    link in the "ID & Title" column) or ``locus`` (backticked ID column)."""

    # --- heading / fence regexes ---
    toc_heading_re: str = TOC_HEADING_RE
    h1_re: str = H1_RE
    h2_re: str = H2_RE
    fence_open_re: str = FENCE_OPEN_RE

    # --- intro split ---
    intro_split: str = "h2"
    """``h1`` or ``h2``: which heading level starts a new intro section."""

    # --- templates / scripts ---
    skill_template: Optional[Path] = None
    readme_template: Optional[Path] = None
    scripts: List[str] = field(default_factory=list)
    """Runtime scripts copied into ``<output>/scripts/``."""

    layout: str = "flat"
    """``flat`` -- one ``reference/<key>/`` dir (FPF, standalone DPF).
    ``frameworks`` -- one ``reference/<key>/`` dir per framework (Suites)."""

    # --- index generation toggles ---
    gen_keyword_index: bool = True
    gen_query_index: bool = True

    # --- dependency index formatting ---
    builds_on_fallback: bool = False
    """Fall back to extracting own pattern IDs from dependency prose (DPF)."""

    # --- domain block formatting ---
    domain_label_prefix: str = "Part "
    """Prefix before the domain key in the SKILL.md domain block."""

    # --- kind labelling (generic templates) ---
    emit_views: bool = False
    """Write ``reference/<framework>/contract/<ID>.md`` beside each unit.

    The unit file stays canonical and is what ``rebuild`` reassembles; the view
    is derived from it and holds only the working sections. It exists for
    readers that have no section-aware tool -- a plain ``read`` or ``rg`` over
    a directory of files. Off by default: the offsets in ``sections.json`` give
    the same saving without duplicating ~45% more files."""

    genre: str = "lookup"
    """Why the skill is opened: ``lookup``, ``apply``, ``setup``, ``maintain``.

    The genre decides the middle of ``SKILL.md`` and which roles ship in
    ``roles/``.  See :mod:`frameworks.genre`."""

    kind_label: str = ""
    """Publication kind shown to the reader (``Architecture Decision Record``)."""

    profile_key: str = ""
    """Decomposition profile that produced this skill (``adr``)."""

    source_path: str = ""
    """Repo-relative path of the source document."""

    # --- provenance / docs ---
    source_note: str = ""
    """Sentence fragment naming the source publication set for templates."""

    def toc_re(self) -> Pattern:
        return re.compile(self.toc_heading_re, re.IGNORECASE)

    def h1_compiled(self) -> Pattern:
        return re.compile(self.h1_re)

    def h2_compiled(self) -> Pattern:
        return re.compile(self.h2_re)

    def fence_open_compiled(self) -> Pattern:
        return re.compile(self.fence_open_re)


# ---------------------------------------------------------------------------
# FPF Core config
# ---------------------------------------------------------------------------

FPF_DOMAINS = {
    "A": "Kernel Architecture -- Ontology, holons, bounded contexts, transformers",
    "B": "Trans-disciplinary Reasoning -- Gamma algebra, assurance F-G-R, loops",
    "C": "Kernel Extensions -- Pluggable calculi (CAL), logics (LOG), CHR",
    "D": "Multi-scale Ethics -- Bias audits, conflict-optimisation",
    "E": "Constitution & Authoring -- 11 Pillars, guard-rails, MVPK, TGA",
    "F": "Unification Suite -- SenseCells, concept-sets, alignment bridges",
    "G": "Discipline SoTA Kit -- SoTA harvesting, benchmarks, portfolios",
    "H": "Glossary & Index",
    "I": "Annexes & Tutorials",
    "J": "Indexes & Navigation",
    "K": "Lexical Debt & Replacement Maps",
}

FPF_CONFIG = SkillConfig(
    name="fpf",
    title="First Principles Framework",
    prefix_token="FPF",
    output=_REPO_ROOT / "skills" / "fpf",
    frameworks=[
        FrameworkSpec(
            key="fpf-patterns",
            # ``FPF`` covers the embedded Architectural Reference
            # (``FPF.Reference:N``), which is addressable but is not a pattern.
            prefix_re=r"(?:[A-K]|FPF)",
            source=_REPO_ROOT / "FPF-Spec.md",
            name="First Principles Framework",
            description="First Principles Framework",
            docid="FPF",
            domains=FPF_DOMAINS,
            domain_prefix_re=r"^([A-K])",
        )
    ],
    docs=[
        DocSpec(
            source=_REPO_ROOT / "USING-FPF.md",
            slug="using-fpf",
            title="Using FPF Library",
            description="The common working instruction: choose what to read, "
                        "resolve references, keep the receiving work in view.",
        ),
        DocSpec(
            source=_REPO_ROOT / "FPF-LIBRARY-REFERENCE.md",
            slug="library-reference",
            title="FPF Library Architectural Reference",
            docid="Library",
            description="Why general Methods belong to Core, why some disciplines "
                        "form Suites, and how the publications fit together.",
        ),
        DocSpec(
            source=_REPO_ROOT / "Readme.md",
            slug="library-readme",
            title="FPF Library Readme",
            description="Entry points into the Library: start with your work, "
                        "Suites, standalone frameworks and development.",
        ),
    ],
    toc_id_location="section",
    intro_split="h2",
    skill_template=_SCRIPT_DIR / "templates" / "SKILL.md.template",
    readme_template=_SCRIPT_DIR / "templates" / "README.md.template",
    scripts=[
        # Runtime tools plus the engine and everything the engine imports, so
        # the copy inside the skill can rebuild or analyse itself without the
        # repository.  A missing dependency here is a broken copy: split_spec
        # imports frameworks, sections, derive and skill_root at module level.
        "_fpf_common.py",
        "fpf_lookup.py",
        "split_spec.py",
        "skill_config.py",
        "split_fpf_spec.py",
        "fpf_update.py",
        "audit_fpf_patterns.py",
        "sections.py",
        "derive.py",
        "skill_root.py",
        "frameworks",
        "templates",
    ],
    layout="flat",
    kind_label="FPF Core",
    profile_key="fpf-core",
    genre="lookup",
    source_path="FPF-Spec.md",
    source_note="the FPF Core specification",
)


# ---------------------------------------------------------------------------
# DPF catalogue
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DPFSpec:
    """One Domain Principle Framework as published in ``DPFs/``."""

    docid: str
    title: str
    filename: str
    description: str
    patterns: int
    """Number of pattern bodies (the "Patterns" column of the DPF catalogue)."""

    slug: str = ""
    """Readable skill directory name (``decision-design`` for PSDA).

    Empty falls back to the lower-cased DocID, which is what a brand-new
    framework gets before anyone has chosen a name for it."""

    @property
    def source(self) -> Path:
        return _DPF_ROOT / self.filename

    @property
    def key(self) -> str:
        """Framework key: the sub-directory under ``reference/``.

        This stays the lower-cased DocID.  Pattern IDs are ``PSDA.1``, so the
        directory that holds them is ``psda/`` regardless of what the skill
        itself is called."""
        return self.docid.lower()

    @property
    def skill_name(self) -> str:
        """Skill directory name: readable, stable, and what an agent loads."""
        return self.slug or self.docid.lower()


ENGINEERING_DPFS = [
    DPFSpec("SYSE", "Systems Engineering",
            "Engineering DPF Suite/SYSTEMS-ENGINEERING-PRINCIPLES-FRAMEWORK.md",
            "Define the system and intended use; compare designs and ways to "
            "obtain them; realize, integrate, qualify and change the result.", 53),
    DPFSpec("MNT", "Maintenance Engineering and Management",
            "Engineering DPF Suite/MAINTENANCE-ENGINEERING-PRINCIPLES-FRAMEWORK.md",
            "Select maintenance policy from condition and failure knowledge; "
            "prepare interventions, restore functioning and qualify return to use.", 16),
    DPFSpec("KCAE", "Knowledge-Corpus Access Engineering",
            "Engineering DPF Suite/KNOWLEDGE-CORPUS-ACCESS-ENGINEERING-PRINCIPLES-FRAMEWORK.md",
            "Engineer arrangements for finding, reading and using documentary "
            "knowledge, including links back to source passages, delivery and "
            "coherent updates.", 11),
    DPFSpec("SIE", "Semantic Integration Engineering",
            "Engineering DPF Suite/SEMANTIC-INTEGRATION-ENGINEERING-PRINCIPLES-FRAMEWORK.md",
            "Make separately governed meanings usable together through models, "
            "mappings, interfaces, validation and response to change.", 12),
]

MANAGEMENT_DPFS = [
    DPFSpec("STR", "Strategy",
            "Management DPF Suite/STRATEGY-PRINCIPLES-FRAMEWORK.md",
            "Find a worthwhile direction; compare options, capabilities, "
            "investments and business models; revise commitments when "
            "conditions change.", 17),
    DPFSpec("OPS", "Operations Management",
            "Management DPF Suite/OPERATIONS-MANAGEMENT-PRINCIPLES-FRAMEWORK.md",
            "Organize flow, queues, capacity, admission, quality and "
            "simultaneous work under actual operating conditions.", 28),
    DPFSpec("ADM", "Organization Administration",
            "Management DPF Suite/ORGANIZATION-ADMINISTRATION-PRINCIPLES-FRAMEWORK.md",
            "Make requests, permissions, obligations, provision, records and "
            "provider coordination effective without unnecessary burden.", 15),
    DPFSpec("CGOV", "Corporate Governance",
            "Management DPF Suite/CORPORATE-GOVERNANCE-PRINCIPLES-FRAMEWORK.md",
            "Constitute and exercise corporate powers, decisions, controls and "
            "accountability under applicable governing rules.", 17),
    DPFSpec("MA", "Management Accounting",
            "Management DPF Suite/MANAGEMENT-ACCOUNTING-PRINCIPLES-FRAMEWORK.md",
            "Construct cost and capacity accounts, forecasts and explanations "
            "that inform organizational choices.", 9),
    DPFSpec("FIN", "Corporate Finance",
            "Management DPF Suite/CORPORATE-FINANCE-PRINCIPLES-FRAMEWORK.md",
            "Arrange financing, liquidity and capital allocation; compare value, "
            "exposure and financial consequences.", 22),
    DPFSpec("MKT", "Marketing",
            "Management DPF Suite/MARKETING-PRINCIPLES-FRAMEWORK.md",
            "Investigate customers and markets; design, communicate and sustain "
            "feasible offers and relationships.", 14),
    DPFSpec("CUST", "Customization and Productization Management",
            "Management DPF Suite/CUSTOMIZATION-AND-PRODUCTIZATION-MANAGEMENT-PRINCIPLES-FRAMEWORK.md",
            "Handle client differences while developing repeatable offerings, "
            "delivery and compatible transitions for existing clients.", 8),
    DPFSpec("EAM", "Engineering Asset Management",
            "Management DPF Suite/ENGINEERING-ASSET-MANAGEMENT-PRINCIPLES-FRAMEWORK.md",
            "Compare use, renewal, replacement and other asset changes over "
            "time, including shared risk, cost and capacity.", 16),
    DPFSpec("LDR", "Leadership",
            "Management DPF Suite/LEADERSHIP-PRINCIPLES-FRAMEWORK.md",
            "Obtain feasible agreement and contributions to joint work, "
            "including preparation through first useful work.", 3),
    DPFSpec("CB", "Community Management",
            "Management DPF Suite/COMMUNITY-MANAGEMENT-PRINCIPLES-FRAMEWORK.md",
            "Develop useful participation, relationships, shared practices and "
            "contributions in organizations or voluntary communities.", 16),
    DPFSpec("OCE", "Organization Change Engineering",
            "Management DPF Suite/ORGANIZATION-CHANGE-ENGINEERING-PRINCIPLES-FRAMEWORK.md",
            "Construct and qualify organizational changes to contributions, "
            "roles, authority, interfaces, capabilities and culture.", 17),
]

FOUNDATIONAL_DPFS = [
    DPFSpec("MATH", "Mathematical Thinking",
            "Foundational Thinking DPF Suite/MATHEMATICAL-PRACTICE-DPF.md",
            "Construct mathematical objects, operations and alternatives; "
            "derive consequences and meet proof obligations.", 20),
    DPFSpec("MMP", "Mathematical Modeling",
            "Foundational Thinking DPF Suite/MATHEMATICAL-MODELING-PRACTICE-DPF.md",
            "Relate a subject question to mathematics; infer, predict, compare "
            "interventions, design observations and revise or combine models.", 17),
    DPFSpec("PHY", "Physical Thinking",
            "Foundational Thinking DPF Suite/PHYSICAL-THINKING-DPF.md",
            "Construct and test physical accounts; select interactions and "
            "idealizations, derive consequences and distinguish them by "
            "observation.", 10),
    DPFSpec("CMP", "Computational Thinking",
            "Foundational Thinking DPF Suite/COMPUTATIONAL-THINKING-DPF.md",
            "Construct algorithms that obtain the required answer within "
            "correctness, resource and interaction conditions.", 15),
    DPFSpec("NOT", "Notational Engineering",
            "Foundational Thinking DPF Suite/NOTATIONAL-ENGINEERING-DPF.md",
            "Design expressions, interpretations and transformations that make "
            "operations usable and changes recoverable.", 8),
]

HUMAN_CAPABILITY_DPFS = [
    DPFSpec("HCD", "Human Capability Development",
            "Human Capability Engineering DPF Suite/HUMAN-CAPABILITY-DEVELOPMENT-PRINCIPLES-FRAMEWORK.md",
            "Connect later work to capability demand, personal programmes, "
            "learning products, individual and shared practice, feedback, "
            "assessment, transfer and retention.", 29),
    DPFSpec("SOM", "Somatic Movement Modeling",
            "Human Capability Engineering DPF Suite/SOMATIC-MOVEMENT-MODELING-PRINCIPLES-FRAMEWORK.md",
            "Connect bodily experience, regulated effort and coordinated "
            "movement; adapt within a familiar movement practice as support or "
            "load changes.", 5),
]

STANDALONE_DPFS = [
    DPFSpec("PSDA", "Decision Design",
            "DECISION-DESIGN-PRINCIPLES-FRAMEWORK.md",
            "Formulate a decision problem, construct alternatives, compare "
            "consequences and uncertainty, and connect a recommendation to its "
            "use.", 18,
            slug="decision-design"),
    DPFSpec("RMP", "Research Method Practice",
            "RESEARCH-METHOD-PRACTICE-PRINCIPLES-FRAMEWORK.md",
            "Frame and design research, obtain and criticize evidence, "
            "synthesize sources, and return a warranted knowledge contribution.", 11,
            slug="research-methods"),
    DPFSpec("EXD", "Explanation Design",
            "EXPLANATION-DESIGN-PRINCIPLES-FRAMEWORK.md",
            "Design an explanation, worked example or dialogue that helps its "
            "recipient understand and perform the needed operation.", 6,
            slug="explanation-design"),
    DPFSpec("NSTD", "Narrativization and Narrative Studies",
            "Narrativization-and-Narrative-Studies-Principles-Framework.md",
            "Turn source material into a followable account while retaining the "
            "relations, uncertainty and links back to the source passages the "
            "reader needs.", 8,
            slug="narrativization"),
    DPFSpec("IS", "Implementation Facilitation",
            "IMPLEMENTATION-FACILITATION-PRINCIPLES-FRAMEWORK.md",
            "Help participants put an evidence-informed practice to use under "
            "local conditions, adapt the assistance and develop their capacity "
            "for further change.", 7,
            slug="implementation-facilitation"),
    DPFSpec("ECO", "Economic Reasoning and Coordination",
            "ECONOMIC-REASONING-AND-COORDINATION-PRINCIPLES-FRAMEWORK.md",
            "Reason about exchange, commitments, incentives, shared resources "
            "and coordination under changing information and demand.", 10,
            slug="economic-reasoning"),
    DPFSpec("FDM", "Financial Domain Modeling",
            "FINANCIAL-DOMAIN-MODELING-PRINCIPLES-FRAMEWORK.md",
            "Model financial positions, rights, obligations, events and payment "
            "flows without confusing their different effects.", 5,
            slug="financial-modeling"),
    DPFSpec("DTM", "Defense and Transmission Modeling",
            "DEFENSE-AND-TRANSMISSION-MODELING-DPF.md",
            "Explain how practices persist and spread, how they help or impair "
            "work, and how protective action changes those outcomes.", 9,
            slug="defense-transmission"),
    DPFSpec("RHY", "Embodied Rhythmics",
            "EMBODIED-RHYTHMICS-PRINCIPLES-FRAMEWORK.md",
            "Recognize, represent, alter and perform rhythmic relations; "
            "coordinate sound, movement, reference and simultaneous layers.", 14,
            slug="embodied-rhythmics"),
    DPFSpec("MDPE", "Music and Dance Practice Engineering",
            "MUSIC-AND-DANCE-PRACTICE-ENGINEERING-PRINCIPLES-FRAMEWORK.md",
            "Create, configure, perform, learn and transmit music and dance "
            "practices, including changes in tools, environments and styles.", 22,
            slug="music-dance-practice"),
]

ALL_DPFS: List[DPFSpec] = (
    ENGINEERING_DPFS + MANAGEMENT_DPFS + FOUNDATIONAL_DPFS
    + HUMAN_CAPABILITY_DPFS + STANDALONE_DPFS
)

DPF_BY_ID: Dict[str, DPFSpec] = {d.docid: d for d in ALL_DPFS}


@dataclass(frozen=True)
class SuiteSpec:
    """One DPF Suite: a composite discipline plus its Architectural Reference."""

    slug: str
    title: str
    docid: str
    readme: str
    reference: str
    reference_title: str
    description: str
    members: List[DPFSpec]

    @property
    def skill_name(self) -> str:
        """Suite skills carry a ``-suite`` suffix.

        ``engineering`` beside ``decision-design`` gives no hint that one is a
        bundle of four frameworks and the other is a single framework.  The
        suffix makes the difference visible in a directory listing."""
        return f"{self.slug}-suite"


SUITES: Dict[str, SuiteSpec] = {
    "engineering": SuiteSpec(
        slug="engineering",
        title="Engineering DPF Suite",
        docid="Engineering",
        readme="Engineering DPF Suite/README.md",
        reference="Engineering DPF Suite/ENGINEERING-DPF-SUITE-REFERENCE.md",
        reference_title="Engineering DPF Suite Architectural Reference",
        description="Designing, realizing, changing and maintaining systems; "
                    "knowledge access and semantic integration.",
        members=ENGINEERING_DPFS,
    ),
    "management": SuiteSpec(
        slug="management",
        title="Management DPF Suite",
        docid="Management",
        readme="Management DPF Suite/README.md",
        reference="Management DPF Suite/MANAGEMENT-DPF-SUITE-REFERENCE.md",
        reference_title="Management DPF Suite Architectural Reference",
        description="Direction, commitments, operations, resources, markets, "
                    "communities and organizational change.",
        members=MANAGEMENT_DPFS,
    ),
    "foundational-thinking": SuiteSpec(
        slug="foundational-thinking",
        title="Foundational Thinking DPF Suite",
        docid="Foundational",
        readme="Foundational Thinking DPF Suite/README.md",
        reference="Foundational Thinking DPF Suite/FOUNDATIONAL-THINKING-DPF-SUITE-REFERENCE.md",
        reference_title="Foundational Thinking DPF Suite Architectural Reference",
        description="Mathematical and physical accounts, models, algorithms and "
                    "usable notation.",
        members=FOUNDATIONAL_DPFS,
    ),
    "human-capability-engineering": SuiteSpec(
        slug="human-capability-engineering",
        title="Human Capability Engineering DPF Suite",
        docid="HCE",
        readme="Human Capability Engineering DPF Suite/README.md",
        reference="Human Capability Engineering DPF Suite/HUMAN-CAPABILITY-ENGINEERING-DPF-SUITE-REFERENCE.md",
        reference_title="Human Capability Engineering DPF Suite Architectural Reference",
        description="Human learning and somatic change, connected to capability "
                    "in later work.",
        members=HUMAN_CAPABILITY_DPFS,
    ),
}


def _dpf_framework(spec: DPFSpec) -> FrameworkSpec:
    return FrameworkSpec(
        key=spec.key,
        prefix_re=re.escape(spec.docid),
        source=spec.source,
        name=spec.title,
        description=spec.description,
        docid=spec.docid,
        domains={spec.docid: spec.description},
        domain_prefix_re=r"^(" + re.escape(spec.docid) + r")",
    )


def build_dpf_skill_config(spec: DPFSpec) -> SkillConfig:
    """One standalone skill per DPF framework published directly in ``DPFs/``.

    Output: ``skills/<docid_lower>/`` with units under ``reference/<docid_lower>/``."""
    return SkillConfig(
        name=spec.skill_name,
        title=spec.title,
        prefix_token=spec.docid,
        output=_REPO_ROOT / "skills" / spec.skill_name,
        frameworks=[_dpf_framework(spec)],
        toc_id_location="id_title",
        intro_split="h2",
        skill_template=_SCRIPT_DIR / "templates" / "DPF-FRAMEWORK-SKILL.md.template",
        readme_template=_SCRIPT_DIR / "templates" / "DPF-FRAMEWORK-README.md.template",
        scripts=[],
        layout="flat",
        domain_label_prefix="",
        builds_on_fallback=True,
        kind_label="Domain Principle Framework",
        profile_key="dpf-framework",
        genre="lookup",
        source_path=f"DPFs/{spec.filename}",
        source_note=f"the {spec.title} DPF ({spec.docid})",
    )


def build_suite_skill_config(suite: SuiteSpec) -> SkillConfig:
    """One skill per DPF Suite.

    Output: ``skills/<suite-slug>/`` with one ``reference/<docid_lower>/``
    directory per constituent framework plus the Suite Architectural
    Reference under ``reference/<suite-slug>-reference/``."""
    frameworks = [_dpf_framework(m) for m in suite.members]
    frameworks.append(FrameworkSpec(
        key=f"{suite.slug}-reference",
        prefix_re=re.escape(suite.docid),
        source=_DPF_ROOT / suite.reference,
        name=suite.reference_title,
        description="How the Suite's disciplines fit together, why they form a "
                    "whole and which contributions stay outside it.",
        docid=suite.docid,
        domains={suite.docid: suite.reference_title},
        domain_prefix_re=r"^(" + re.escape(suite.docid) + r")",
        role="reference",
    ))
    domains: Dict[str, str] = {}
    for m in suite.members:
        domains[m.docid] = m.description
    return SkillConfig(
        name=suite.skill_name,
        title=suite.title,
        prefix_token=suite.members[0].docid if len(suite.members) == 1 else "",
        output=_REPO_ROOT / "skills" / suite.skill_name,
        frameworks=frameworks,
        toc_id_location="id_title",
        intro_split="h2",
        skill_template=_SCRIPT_DIR / "templates" / "DPF-FRAMEWORK-SKILL.md.template",
        readme_template=_SCRIPT_DIR / "templates" / "DPF-FRAMEWORK-README.md.template",
        scripts=[],
        layout="frameworks",
        domain_label_prefix="",
        builds_on_fallback=True,
        kind_label="DPF Suite",
        profile_key="dpf-framework",
        genre="lookup",
        source_path=f"DPFs/{suite.reference}",
        source_note=f"the {suite.title}",
    )


#: One config per standalone DPF (10 skills).
DPF_SKILL_CONFIGS: Dict[str, SkillConfig] = {
    spec.docid: build_dpf_skill_config(spec) for spec in STANDALONE_DPFS
}

#: One config per Suite (4 skills).
SUITE_SKILL_CONFIGS: Dict[str, SkillConfig] = {
    slug: build_suite_skill_config(suite) for slug, suite in SUITES.items()
}

#: Every DPF-side skill, keyed by its directory name.
ALL_DPF_CONFIGS: Dict[str, SkillConfig] = {
    **{cfg.name: cfg for cfg in SUITE_SKILL_CONFIGS.values()},
    **{cfg.name: cfg for cfg in DPF_SKILL_CONFIGS.values()},
}

#: Expected pattern counts per DocID (the DPF catalogue's "Patterns" column).
EXPECTED_PATTERNS: Dict[str, int] = {d.docid: d.patterns for d in ALL_DPFS}
