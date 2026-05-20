# First Principles Framework (FPF) - Core Conceptual Specification

> Pattern language and core specification for admissible action in problematic engineering, research, and mixed human/AI work.

- **Author:** Anatoly Levenchuk (with AI-agents assistance)
- **Version:** May 2026
- **Status:** Normative kernel, "eternal alpha" - already used in working projects and development programmes, while still evolving.

FPF helps when insight is not enough by itself: meanings, claims, alternatives,
evidence, boundaries, publication forms, and work decisions must remain stable
across contexts, time, people, tools, or AI agents.

It helps an engineer-manager, researcher, or mixed human/AI team answer practical questions such as:

- what problem situation is live, and which responsibility boundaries matter;
- which roles, methods, plans, work occurrences, claims, evidence, and publication forms are being mixed;
- which alternatives, comparisons, local choices, or actions are admissible under the current evidence and context;
- what source, test, decision record, terminology sheet, or engineering justification is needed before stronger use;
- how to publish descriptions, explanations, screens, summaries, and other outputs for engineering, management, research, or assurance readers without semantic drift.

Use FPF when:

- work is split across specialists, teams, or AI agents;
- the real-world oracle is slow, expensive, noisy, or risky;
- different audiences need different views of the same underlying work;
- your current vocabulary is breaking down;
- you need state-of-the-art (SoTA) work as a managed portfolio, not a leaderboard snapshot;
- a solo or small-team decision still needs durable reasoning, auditability, or stable publication.

FPF may be too heavy when:

- the task is small,
- vocabulary is already stable,
- feedback is fast and cheap,
- the cost of semantic drift is low,
- no durable shared reasoning form is needed,
- or you mainly need a quick answer rather than a reusable reasoning form.

## First entry

This README is high-recall, low-detail. `Preface` gives coarse orientation,
`J.4` is the compact canonical entry index, and `I.2` is the worked-reading
depth role. A pattern's own `Problem frame` is the local high-precision
first-reading role.

This README is downstream of Core. It may echo `Preface`, `J.4`, and `I.2`,
but it does not add new first-pattern choices, nearby starting-point clusters,
or lexical names absent from Core.
It is not the public canonical entry table, a conformance authority, or a
getting-started workflow.
The short entries below name typical stabilizing results, not guaranteed
outputs, handoffs, or route scripts.
Update this entry echo when public entry claims change materially, not for every
local candidate-pattern wording repair inside Core.

Choose your first entry by what you are really trying to decide, stabilize, or
publish, not by document order. If you are new to FPF, read the entry title and
opening sentence first; use pattern IDs only after you know the entry matches
your situation.

A first practical session often stabilizes one or more of:

- who means what, and which responsibility boundaries matter;
- explicit decision criteria, comparison characteristics, or admissibility guards;
- a small alternative set or local choice record when selection is part of the current work;
- a visible list of missing evidence or tests before commitment;
- a starter terminology sheet, a starter DRR, or another output form for the live question.

If you first need to decide whether FPF fits your situation, inspect `E.1-E.2`.
If you need to write or review patterns, inspect `E.8` and `E.19`.

Use this repository as an entry menu, not as one universal starter trunk:

1. **Project alignment**

   - **Use this when:** responsibilities, working method, plans, and what actually happened are being mixed.
   - **Typical stabilizing result:** a clean separation between responsibility, method, plan, and actual execution, plus a first worksheet, alignment frame, or term sheet.
   - **First inspect:** `A.1.1`, `A.15`, `A.15.2 / A.15.3`, and `B.5.1`. Consider `F.11` when method/work vocabulary itself must be aligned across contexts, `F.9` where bridge discipline matters, and `F.17 (UTS)` when vocabulary stabilization is live.

2. **Partly-said / language-state discovery**

   - **Use this when:** you have a serious cue, concern, or emerging idea that is too important to ignore but too early to present as a settled claim, requirement, or work record.
   - **Typical stabilizing result:** a short preservation-and-support note that says what was noticed, how mature it is, and what kind of work should inspect it next.
   - **First inspect:** `C.2.2a`, `C.2.LS / C.2.4-C.2.7`, `A.16 / A.16.1 / A.16.2`, and `B.4.1 / B.5.2.0`; consider endpoint patterns only when the live question actually belongs to an endpoint.

3. **Boundary unpacking / claim routing**

   - **Use this when:** contract, API, protocol, compliance, or SLA language is mixing rules, gates, duties, and evidence in one blurred boundary story.
   - **Typical stabilizing result:** a Claim Register or routed atomic claim set.
   - **First inspect:** `A.6`, `A.6.B`, and `A.6.C`. If the first question is only what description you are seeing, inspect `A.6.RSIG`; when the boundary text hides overloaded quality or action language, add `A.6.P`, then `A.6.Q` or `A.6.A`.

4. **Admissible comparison / local choice / selected-set publication**

   - **Use this when:** you need to compare alternatives honestly, choose among already-available options, keep a disciplined shortlist live, or publish a selected set without hiding the comparison logic.
   - **Typical stabilizing result:** declared characteristics, a comparison frame, candidate-pool policy, `ChoiceResult`, selected-set publication, or another local decision record.
   - **First inspect:** `A.19:0`, `A.17-A.19`, `A.19.CN`, `C.11`, `G.0`, `C.18`, `C.19`, and `G.5`; use `C.11` when the live work is choosing now versus probing or computing more before choosing, and use `C.24` only for call-planning/checkpoint-return work.

5. **Generator / state-of-the-art / NQD / OEE portfolio kit**

   - **Use this when:** your first deliverable is a reusable search, harvest, generator, novelty/diversity archive, or portfolio scaffold, not a one-off recommendation.
   - **Typical stabilizing result:** a reusable kit that names scope, schools of thought, variants, declared `CharacteristicSpace`, descriptor map, archive policy, and shortlist-ready outputs.
   - **First inspect:** `A.0`, `B.5.2.1`, `C.18`, `C.19`, `G.0`, `G.1`, `G.2`, and `G.5`. Consider `A.19` when characteristic-space comparison is already central, and `C.17-C.19` when creative search or explore/exploit policy is live.

6. **Publication, rendering, explanation, and same-entity reading**

   - **Use this when:** the main job is to publish, restate, explain, re-render, repair, or compare something already written or displayed without quietly changing what it is about or what it authorizes.
   - **Typical stabilizing result:** a publication/use-boundary note, rewrite, explanation note, repair note, or bounded comparison note that keeps the claim-bearing source, publication form, carrier/display, reader use, and work-relevant source relation distinct.
   - **First inspect:** `E.17`, `A.15.4`, `A.6.3.CR`, `A.6.3.RT`, `A.6.3.CSC`, `E.17.EFP`, `E.17.ID.CR`, `E.17.AUD.LHR`, and `E.17.AUD.OOTD`.

7. **Temporal claim adequacy under effort, window, resistance, and rhythm**

   - **Use this when:** a claim about timing, trend, delay, inertia, freshness, decay, or action window is being treated as if time did not change what can be done.
   - **Typical stabilizing result:** a temporal adequacy note that names the live time window, effort/resistance relation, update rhythm, and what must be rechecked before use.
   - **First inspect:** `C.27`, `C.16`, `A.3.3`, `A.6.T`, and the neighboring evidence or decision pattern that owns the live claim.

8. **Causal-use / counterfactual-support repair**

   - **Use this when:** a correlation, explanation, model output, scenario, or comparison is being used as if it already justified intervention, responsibility, or counterfactual choice.
   - **Typical stabilizing result:** a causal-use repair note that separates observation, prediction, intervention support, responsibility support, and engineering justification.
   - **First inspect:** `C.28`, `A.10`, `B.3`, `D.5`, `G.5`, and `G.9`; use the local decision pattern only when an actual choice is being made.

The older abduction reasoning loop (`A.0 -> A.1-A.3 -> B.3 -> F.17 -> E.9`) is here but not the universal
default anymore. Use `B.3` when engineering justification / trust / evidence transport is
already part of the present question, and use `E.9 (DRR)` when normative change
or durable canon rationale must actually be published.

FPF is not:

- a shrink-wrapped project methodology;
- a quick-answer cheat sheet;
- a demand to read the whole specification linearly before doing useful work.

It is an amplifier for collaborative engineering thinking in human-only, mixed human/AI, and AI-agent-heavy work.

## What stays outside this front door

- coarse orientation lives in `Preface`, not in this README;
- compact comparison of nearby starting points lives in `J.4`;
- longer worked entry readings live in `I.2`;
- advanced internal maps, AI-assistant prompt recipes, and extended examples appear later in this README or in `FPF-Spec.md`.

## One-minute example

A vague project question:

> "Should we buy, fine-tune, or build an agent stack for our platform?"

Without FPF, this often becomes one overloaded discussion with mixed
vocabularies, hidden trade-offs, unclear responsibility, and premature
convergence on a single option.

With FPF, the work can become one disciplined structure:

- `problem framing`
- `bounded contexts` (product / infrastructure / safety / evaluation)
- `decision criteria` (cost / latency / controllability / risk / time-to-value)
- `portfolio of alternatives` (buy / fine-tune / build / hybrid)
- `evidence and test gaps`
- `starter DRR when the decision rationale must be published`
- `starter UTS when vocabulary must be stabilized`
- `aligned outputs` for engineering / management / research / assurance

The list is a compact explanatory sketch, not a required workflow.
The same shape can be used for a plant rollout, a laboratory protocol, a
construction design change, a supply-chain decision, or an AI-agent platform.
The point is one underlying body of reasoning that can be reviewed, revised,
and published without semantic drift.

## Core orientation

The **First Principles Framework (FPF)** is a structured framework for thinking and coordinating work. It is written more like a technical specification than like a management book: there are named patterns, definitions, and review rules. Its job is to help teams model complex work, make reasoning inspectable, and keep decisions stable across engineering, research, and management.

This repository contains the **core specification**. Tooling belongs in tool-specific layers; worked examples, exercises, and guided learning paths belong in the pedagogical companion.

Use the spec as a reference model and entry map, not as a linear textbook.

FPF is not a specific methodology such as Agile or Waterfall, and it is not a static encyclopedia. It is closer to an architecture for reasoning: a set of reusable patterns and working forms that help teams turn tacit thinking into shared, reviewable work.

FPF is not mainly about making one model smarter. It is about making collective reasoning usable: clear local contexts, explicit responsibility boundaries, reviewable decision records, and outputs that different audiences can trust.

A few unusually load-bearing parts of FPF are worth noticing early:

- **A.6 boundary discipline and RPR (Relational Precision Restoration).** FPF does not let one contract/API/SLA/protocol sentence carry rules, gates, duties, evidence, quality words, and action permission as one undifferentiated bundle; `A.6` and `A.6.P` restore the exact relation before stronger use.
- **Characteristic spaces.** FPF treats comparison, measurement, search, and temporal change as work over declared characteristics and scales, not as loose talk about dimensions or scores.
- **NQD / OEE.** Open-ended novelty and quality-diversity work gets explicit descriptor maps, archives, and exploration policy, so a team can search without collapsing too early to one favorite option.
- **Temporal adequacy.** `C.27` handles claims whose usability depends on window, rhythm, inertia/resistance, freshness, effort, and intervention-sensitive change rather than treating time as background decoration.
- **Quantum-like modeling.** FPF has a narrow, non-mystical way to handle probe-coupled reads, distributed enacted state evidence, and viability envelopes when ordinary passive-observation language is false.
- **Publication and use boundaries.** Recent semio patterns make screens, summaries, explanations, credentials, dashboards, and other publications answerable to their claim-bearing source before they are used as work, evidence, gate status, or engineering justification.

## What problem FPF solves

FPF is most useful when raw insight is no longer enough by itself. The hard part
may be coordination, but it may also be semantic precision, evidence shaping,
comparison, claim publication, vocabulary stabilization, or keeping one body of
reasoning coherent across time and readers.

In plain language: FPF turns raw intelligence into work that is easier to
align, review, evolve, publish, and delegate.

It also helps teams and solo practitioners create local zones of closure inside
an open world, so a real decision can be made even when the outside remains
uncertain.

Illustrative example: a platform team is deciding whether to buy, fine-tune, or
build an agent stack. FPF helps separate product, safety, infrastructure, and
evaluation contexts; define decision criteria; keep several options live long
enough to compare them honestly; make missing evidence explicit; and publish
aligned views for engineering and management without changing the underlying
reasoning.

## What you get after one pass

A first practical pass through FPF should stabilize concrete artifacts, not just
better intuitions:

- a map of bounded contexts and responsibility boundaries;
- explicit decision criteria and trade-off characteristics;
- a small portfolio of alternatives instead of premature convergence;
- a visible evidence / test gap list before commitment;
- a starter DRR;
- a starter UTS;
- aligned outputs for engineering, management, research, engineering-justification, and audit readers.

## Where FPF earns its keep

FPF tends to pay off when several of these are true:

- work is split across specialised people, teams, copilots, or AI agents;
- the real-world oracle is delayed, noisy, expensive, or risky;
- different audiences need aligned outputs from the same underlying work;
- trade-offs between speed, quality, risk, novelty, and compliance must be made explicitly rather than hidden in one opaque score;
- existing categories are breaking down and you need to grow new concepts from first principles instead of reusing local folklore.

### Three ways to use FPF

1. **Human-only.** Use FPF as a reading, writing, and review discipline even with no AI in the loop. People can map contexts, separate systems / roles / method descriptions / methods / work, and produce shared term sheets and decision records directly.
2. **Mixed team.** Use FPF as a coordination layer across specialised people, teams, copilots, and AI agents. This is the mode where local working frames, responsibility boundaries, decision gates, and audience-specific outputs matter most.
3. **AI assistant.** Use FPF as an attached reference file or indexed reference for an assistant. In this mode, the spec is attached as a file rather than pasted into the prompt window; the dedicated section below shows the concrete loading pattern.

### Why FPF when AI-agents keep getting stronger?

- **Because local generation is not the whole problem.** Stronger LLMs reduce local reasoning scarcity, but they do not remove the need for selection, auditability, safe delegation, semantic stability, and shared understanding across people, agents, time, and viewpoints.
- **Because local working frames still matter.** FPF keeps teams from pretending that product, safety, operations, and research all use one universal vocabulary.
- **Because many real projects cannot just loop until tests pass.** In product, field engineering, strategy, marketing, safety, or open-ended research, the real-world oracle is delayed, noisy, expensive, or risky. FPF aims to catch anti-patterns before contact with the world.
- **Because the same framework can serve both humans and AI.** AI agents can read the specification directly; humans can learn the same working model through didactic layers and the pedagogical companion.
- **Because FPF pays off past a complexity frontier.** It matters most when the problem becomes simultaneously compositional, collaborative, temporal, assurance-heavy, and generative.

### FPF as an Operating System for Thought

Using the OS metaphor, FPF:

- **Provides a common runtime for reasoning and iteration.**
- **Treats local working frames as stable responsibility-boundary units.**
- **Separates systems, roles, method descriptions, methods, plans, and executed work.**
- **Keeps claims tied to scope, carriers, and evidence.**
- **Turns tacit thought into structured artefacts instead of leaving it implicit.**
- **Lets one underlying body of work be published differently for engineering, management, research, and assurance.**
- **Stays extensible through domain-specific packs instead of hard-coding one discipline's worldview.**

For most readers, the practical point is simpler than the internal vocabulary: FPF gives mixed human/AI teams a shared way to specialise locally, move work across responsibility boundaries cleanly, and keep different outputs about the same work coherent.

Loaded as a file into an AI assistant that can read files directly or through retrieval over an indexed copy, FPF can act as a disciplined reasoning scaffold for mixed human/AI work. It steers the model toward first-principles and state-of-the-art-oriented reasoning instead of generic marketing / management / pop-psychology boilerplate - but it will not think instead of you, and without good questions you can still get very confident, well-structured nonsense.

## Who is this for?

- **Engineers and systems engineers** building reliable physical or cyber-physical systems.
- **Researchers** constructing trustworthy knowledge and theories.
- **Platform teams** designing AI-agent / human-in-the-loop work systems.
- **Safety, assurance, and regulatory leads** who need auditable boundaries, evidence, and controlled delegation.
- **Managers and product leaders** orchestrating collective intelligence, budgets, and evolutionary cycles.

## Core ideas (plain language first)

FPF is built on a small kernel of non-negotiable ideas. New readers do not need the internal pattern names immediately; the point of this section is to explain what the framework buys you before you dive into its internal map.

1. **Local meaning, explicit translation.** Terms live inside bounded contexts: local working frames with their own meanings. Cross-context reuse is never obvious; it needs an explicit bridge.
2. **One underlying reality, many aligned outputs.** Engineering, management, research, and assurance outputs should be projections of the same underlying work, not disconnected documents.
3. **Separate systems, roles, method descriptions, methods, plans, and executed work.** Descriptions, capabilities, plans, and actual occurrences are not the same thing.
4. **Trust has structure and grounding.** A claim should say how formal it is, where it applies, what evidence supports it, and which carriers or systems anchor it.
5. **Composition matters across scales.** The same logic should survive when parts are aggregated into wholes.
6. **Keep search wide before selection.** In open-ended work, diversity of options matters before choosing a winner.
7. **Build from first principles when categories break.** FPF is not only for organising the current state of the art; it is also for growing new abstractions.

## What to expect (and what not to expect)

### Reasonable expectations

- **A coordination fabric for mixed human/AI teams.** FPF helps specialised people and agents participate in one engineering or research effort through bounded contexts, bridges, shared artefacts, and multiple publication forms / views.
- **A way to push some mistakes left, before expensive contact with the world.**
- **A way to keep engineering, management, research, and assurance outputs coherent.**
- **A co-thinker biased toward state-of-the-art and first-principles reasoning.** When loaded into an AI-agent or chat, FPF gives you sharper questions, better comparisons, and far less generic boilerplate.
- **A backbone for disciplines and organisations.** FPF can serve as a structured way to model a discipline or organisation with explicit contexts, roles, calculi, and state-of-the-art packs rather than one more methodology slide-deck.
- **A machine for first-principles synthesis.** Use it not only to recall current best practice, but to grow new Second Principles Framework (SPF) when existing categories are misleading.
- **A kernel for development programmes.** It can also act as a kernel for engineer-manager development and research skill-building.

### Unreasonable expectations

- **I will just read it once and form my opinion.** The spec reads like OS source code, not like a popular book; it is meant to be used with tools, not consumed in one sitting.
- **This is a plug-and-play tool for all work projects.** Today FPF is a research-grade framework that already helps in real projects as an MVP, but it is not yet a shrink-wrapped product; you still need to adapt, localise, and extend it for your discipline and organisation.
- **It works without good framing and always gives the right answer.** AI-agent+FPF will not think instead of you. Without good questions, explicit problem frames, and minimal rational literacy you can still get confident nonsense - just more structured nonsense.
- **A stronger AGI / LLM makes FPF unnecessary.** As models get stronger, the bottleneck often moves from local reasoning to coordination, selection, safe delegation, and cross-role auditability.
- **Adoption should be decided only by transferable benchmark wins from other organisations.** Frameworks such as Agile or Copilot-like practices are often adopted as architectural bets under high variation. FPF is similar: the justification is usually logical fit to your coordination / problem structure, not a neat benchmark that transfers unchanged across organisations.
- **If I ignore first principles, FPF will fix everything.** FPF amplifies whatever style of thinking you bring: if you use it to chase fashion, it will help you catalog fashion; if you use it to chase first principles, it will help you do that more systematically.

## How to approach this repository

There are eight practical newcomer entry families above, plus a few orientation options around them:

1. **If you want the why:** start with **E.1-E.2** (Vision / Mission + Pillars).
2. **If you want the first practical entry:** choose the entry block above whose opening sentence sounds most like your current question, not the code sequence that happens to appear first.
3. **If you already chose an entry and want more detail:** use **Preface** for coarse orientation, **J.4** for compact comparison of nearby starting points, and **I.2** for longer worked readings.
4. **If you want to write or review patterns:** start with **E.8** and **E.19**.
5. **If your real situation is still partly said:** use the partly-said entry family above in full detail - `C.2.2a`, `C.2.LS / C.2.4-C.2.7`, `A.16 / A.16.1 / A.16.2`, `B.4.1 / B.5.2.0`, then the relevant endpoint pattern.
6. **If a publication, dashboard, explanation, summary, credential, or display is being treated as permission to act:** inspect `E.17`, `A.15.4`, and the same-entity rewrite/explanation family before treating it as work, evidence, gate status, or engineering justification.
7. **If an actual choice among available options is live:** inspect `C.11` before collapsing the problem into generation, pool policy, planning, or selected-set publication.
8. **If open-ended generation, novelty, diversity, or characteristic-space search is live:** inspect `A.0`, `B.5.2.1`, `C.18`, `C.19`, `A.19`, and `G.5` before treating the result as a one-off recommendation.
9. **If time, rhythm, delay, or effort changes whether a claim is usable:** inspect the temporal claim adequacy entry family before making the claim operational.
10. **If explanation or model output is being used for action:** inspect the causal-use / counterfactual-support entry family before treating it as intervention or responsibility support.
11. **If measurement or publication may change the state being read:** inspect the quantum-like / probe-coupled entry family before treating the readout as a passive observation.
12. **If you want a compact internal map:** use the simplified cluster map below.

<details>
<summary>Advanced: simplified internal map of the specification</summary>

The specification is divided into clusters. The map below is intentionally simplified and focuses on the main semantic blocks. Think of it as source code for an evolvable reasoning architecture, not as an expert system and not as a tutorial; Parts **H-K** then provide glossary, annexes, indexes, and navigation aids. If you only need to choose your first entry, you can skip this block.

### Part A: Kernel Architecture Cluster
The immutable ontological core.
- **Ontology:** Holons, Systems, Epistemes, and Bounded Contexts.
- **Transformation:** the transformer quartet - system bearing TransformerRole, MethodDescription, Method, Work.
- **State Space and boundaries:** Characteristics, Scales, Dynamics, and the signature-stack / boundary-discipline family.

### Part B: Trans-disciplinary Reasoning Cluster
The logic of composition and trust.
- **Aggregation and emergence:** cross-scale composition and reasoning.
- **Assurance:** trust, evidence, canonical evolution, pre-abductive routing, abductive prompting.
- **Bridge use:** how reasoning moves across contexts without silent collapse.

### Part C: Kernel Extension Specifications
Pluggable domain-specific calculi, logics, and characterisation families.
- **Extension families:** Sys / KD / Kind / Method / LOG / CHR.
- **Additional live-question families:** measurement, creativity, NQD/OEE, explore / exploit policy, discipline health, problem typing, method-maturity, agentic tool-use, characteristic-space search, quantum-like state reading, and quality-bundle patterns.

### Part D: Multi-scale Ethics & Conflict-Optimisation
- Multi-scale ethics from agent to planetary scope.
- Conflict topology, trust-aware mediation, and bias / ethical-assurance overlays.

### Part E: The FPF Constitution and Authoring Guides
The governance of the framework itself.
- **Vision, pillars, and guard-rails.**
- **Didactic architecture, authoring protocol, lexical law, and human-facing working-model discipline.**
- **Multi-view publication, transduction-graph architecture, review gates, and DRR-based evolution governance.**

### Part F: The Unification Suite
Techniques for aligning vocabularies across disciplines and specialised agents.
- **Concept-sets, local naming, and role descriptions.**
- **Mint / reuse discipline, bridges, status mappings, and method-quartet harmonisation.**
- **Human-facing publication forms such as UTS.**

### Part G: Discipline State-of-the-Art (SoTA) Patterns Kit
Tools for harvesting state-of-the-art knowledge and building governed portfolios.
- **CG-Spec and CG-Frame authoring.**
- **State-of-the-art harvesting and synthesis.**
- **Admissible characteristic / calculi authoring, selector / dispatcher patterns, shipping-ready publication forms, and refresh discipline.**

### Parts H-K: Glossary, annexes, and navigation aids
Glossary, extended tutorials, indexes, migration notes, and other navigation support around the core clusters.

</details>

## Using FPF with an AI assistant

This is one of the three practical modes above, not the default identity of FPF. If you are working human-only or in a mixed team, you can skip this section and still use the framework fully.

The Core itself remains tool-agnostic; attaching the file or using retrieval over an indexed copy is simply the most convenient current way to expose the spec to an assistant. In practice the spec is too large to paste cleanly as a prompt, so treat it as an attached file or indexed corpus.

The highest-leverage first sessions are concrete. Ask for plain-language outputs first; pull internal FPF names only when they add precision or help you navigate the spec.

AI-agent+FPF will not solve everything automatically: you remain the principal, and the model is an agent that follows your problem framing and constraints.

If you are new to FPF, start with prompt `1` or `5` below. The later examples assume more internal FPF vocabulary.

### A starter prompt that usually works

```text
You have the FPF specification as a file.
Help me structure [project / problem / programme].
Use plain language for an engineer-manager.
Propose: (1) bounded contexts / specialisations, (2) decision criteria, (3) key alternatives, (4) responsibility boundaries, and (5) missing evidence or tests before commitment.
Introduce internal FPF names only when they add precision.
```

In practice the most productive usage is to treat FPF as a design kit and reference model: ask for bounded-context maps, decision criteria, option portfolios, structured reasoning artefacts, publication forms, and responsibility-boundary contracts for your domain, then iterate.

Below are example prompts; adapt them to your domain and language.

### 1. Turn a vague project into measurable decision criteria

**Goal:** get a step-by-step chain from vague idea to measurable characteristics, indicators, scoring, and decision criteria.

**Prompt:**

```text
You have the FPF specification loaded as a file.
We are starting work on [brief description of project], design has not yet begun.
Propose a step-by-step chain for characterising the objects of our project, normalising measurements, defining indicators, scoring alternatives, and choosing design decisions.
Include steps that I may have forgotten.
Write in the language of engineer-managers, not in FPF jargon.
```

Typical follow-ups:
- "Now take object [X] from this chain and work it through in detail: list 10-15 characteristics, their scales, indicators, and a rough dashboard format for decision-makers."
- "Show how this chain maps to the principles-to-work route for this project."

### 2. Build a disciplined vocabulary for a domain (UTS, shared term sheet)

**Goal:** build a disciplined vocabulary for a niche field using FPF Part F.

**Prompt:**

```text
You have the FPF specification loaded.
Produce a Unified Term Sheet (UTS) block for the core terms of [your domain]: at least 10 rows.
Use the term-sheet discipline from Part F (especially F.17 / F.18): distinguish Tech vs Plain names, show SenseCells for 2-3 key bounded contexts, and flag risky aliases.
```

Follow-up for quantitative structure:
- "For the same domain, propose a Q-bundle that captures the quality of [your object / work system] and produce a UTS block for its characteristics (CHR) and indicators."

### 3. Design better names for ambiguous roles, programmes, and artefacts (Name Cards)

**Goal:** design better names for roles, programs, and artefacts when existing labels are misleading.

**Prompt:**

```text
Using the naming-card discipline (F.18), develop a complete Name Card for what to call [current name of an entity] in the following situation:
[short narrative of current practice and complaints about the existing name]
Do not assume current names are correct; perform an honest search on the local Pareto-front of candidate names and explain trade-offs.
```

### 4. Make the route from principles to work explicit (P2W / E.TGA graph)

**Goal:** make from principles to work explicit for a concrete project.

**Prompt:**

```text
Using E.TGA and TEVB, unpack the canonical P2W flow for my situation [describe your project].
Give the list of nodes (P1...Pn), their Kinds, and explain each node in engineer-manager language.
```

Follow-up:
- "Now build a mini Flow specification table for this P2W graph".

### 5. Organise a mixed team of humans and AI agents

**Goal:** turn a set of people, copilots, and specialised agents into a disciplined work architecture.

**Prompt:**

```text
We have the FPF specification loaded as a file.
We need to organise a mixed team of humans and AI agents for [project / programme].
Propose a bounded-context map: contexts, local vocabularies, roles, bridges, responsibility-boundary artefacts, decision gates, and where human approval is required.
Keep the final answer practical for engineers / managers and avoid FPF jargon.
```

Typical follow-ups:
- "Now define autonomy budgets, allowed tools, escalation paths, and publication forms / views for each context / agent."
- "Show which bridges are high-risk because translation loss or ambiguity is likely."

### 6. Harvest competing schools of thought and build a portfolio (state-of-the-art pack)

**Goal:** use Part G to organise a frontier discipline around first principles.

**Prompt:**

```text
We are searching for the state of the art in [discipline].
Using G.2 and G.4, extract: (a) TraditionCards for competing schools of thought; (b) OperatorCards for their main operators / update rules; (c) a first draft of a state-of-the-art pack and selector-ready portfolio. This is expected to be a long text, therefore start with only TraditionCards.
```

## Citation

If you use FPF, please cite:

```
Levenchuk, Anatoly. First Principles Framework (FPF).
GitHub repository: https://github.com/ailev/FPF
```
