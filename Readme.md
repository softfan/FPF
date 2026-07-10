# First Principles Framework (FPF) - Core Conceptual Specification

> First Principles Framework (FPF) is a standards-style pattern language for turning difficult engineering, research, management, and mixed human/AI work into explicit, reviewable, improvable reasoning.

- **Author:** Anatoly Levenchuk, with AI-agent assistance
- **Version:** July 2026
- **Status:** Normative kernel, eternal alpha: already used in working projects and development programs, while still evolving.

FPF helps when a project has outgrown one clever conversation. It is useful when meanings, claims, options, evidence, architecture, work decisions, publication forms, and improvement criteria must stay coherent across people, teams, tools, time, or AI agents.

Use FPF as a reference model and pattern language, not as a linear textbook. Start from the working question you bring from your project. Bring in internal FPF terms only after they help you keep the work precise.

This readme is a thin first-entry rendering of FPF for engineers, researchers, managers, reviewers, and AI-assisted project workers deciding where FPF can help. It foregrounds the project questions most likely to pay off first and deliberately coarsens, omits, or defers the full pattern language, source publications, source-use history, and relation structure. When a claim becomes important, return to the Preface, Table of Content, and governing pattern body rather than treating this readme as the specification.

The plain starting move is: name the project object at stake. FPF often calls it a holon when the object is being treated as a whole with parts: a machine, product, organization-as-system, body of knowledge, publication system, work occurrence, discipline, AI-agent arrangement, or local framework admitted by a pattern. A method or role may be the live project object, but then FPF uses method or role patterns rather than calling it a holon by label. Once the object is named, FPF asks what structure, claim, decision, evidence, description, work, or improvement question is actually live.

## Decide Whether FPF Fits

Use FPF when ordinary discussion is no longer enough to keep work coherent. Typical signs:

- several teams, experts, tools, or AI agents must reason about the same work;
- the real-world test is slow, expensive, noisy, risky, or politically hard to repeat;
- different readers need different reports, dashboards, explanations, or decisions about the same underlying work;
- names, roles, responsibilities, options, evidence, or quality criteria are starting to blur;
- the team needs a current view of possible approaches, not just one recommendation;
- a decision is small enough to make now but important enough to leave a durable reason.

FPF is probably too heavy when the task is small, feedback is fast and cheap, the vocabulary is already stable, the decision will not be reused or audited, and a quick answer is enough.

FPF is mainly useful for people who have to keep difficult work understandable across boundaries:

- engineers and systems engineers working with complex products or operations;
- researchers building claims that others must inspect or reuse;
- platform and AI teams coordinating humans, models, tools, and approvals;
- safety, assurance, compliance, and regulatory leads who need visible evidence and responsibility boundaries;
- managers and product leaders who must compare options, budgets, risks, and delivery promises without hiding trade-offs.

There are three common ways to use FPF:

1. Human-only: use it as a writing and review discipline for meetings, notes, decisions, and technical documents.
2. Mixed team: use it to keep specialists, managers, safety leads, and AI assistants aligned around the same work.
3. AI-assisted: attach or index the specification, ask for plain-language project help first, and use pattern names only when they make the answer easier to check.

Stronger AI does not remove the need for FPF. AI can generate fluent options quickly, but projects still need to decide what counts as evidence, which option is being compared, who may rely on an answer, when a claim is stale, what remains only a guess, and what work is actually authorized. FPF helps make those boundaries explicit before a confident answer becomes an expensive mistake.

Core ideas in plain language:

- first name the project object under concern; when it is treated as a whole with parts, FPF calls it a holon;
- local teams may use local meanings, but translation must be explicit when work crosses a boundary;
- the project object itself, its description, a dashboard about it, a decision about it, and the work done to change it are not the same;
- architecture is structure of that holon or project object in a context, not the diagram, document, approval, or plan about it;
- serious architecture work can move from problem pressure to candidate structures, selected structures, decisions, method and work, actual structures, and feedback;
- keep several options alive until the comparison is clear enough to choose;
- say what "better" means before optimizing or scoring;
- make trust depend on evidence, freshness, scope, and intended use;
- publish different views for different readers without changing the underlying claim;
- when selected source structure must become an explanation, reader-facing ordering, or narrative for a reader, state what structure is preserved, deliberately coarsened, abstracted, omitted, or lost, and which named source basis or governing pattern receives the return when loss matters;
- use mathematics or formal models when they clarify what structure is preserved, what is lost, and what can be checked;
- build domain or local FPF-grounded frameworks as dependents of FPF Core, not as silent rewrites of the Core.

## First Practical Entries

A first practical entry is the first useful way to enter FPF from a real working project. Choose it by the project question you are trying to settle, not by the order of patterns in the specification.

The entries below are not a required sequence. They are common places where FPF can start paying rent in a project.

### 1. Develop or review architecture

Use this when you need to design, explain, review, or improve the architecture of a product, organization, technical system, document system, AI-agent setup, research program, local practice, or other holon with important internal structure.

FPF helps you start from the holon being changed or described, not from the drawing. It asks which structures are unknown, candidate, selected, expected, or actual; which architecture characteristics are under pressure; which alternatives must remain alive; which decision is now binding; which method or work will realize the selected structures; and what operation, measurement, or feedback can reopen the architecture.

Typical first result: a short P2S flow card or architecture question note that names the described holon, bounded context, problem pressure, unknown or selected structures, architecture characteristics, candidate or decision locus, work or feedback locus, and what real selected structure is still not settled by the current architecture statement.

Entry seed: architecture-relevant problem pressure -> `ProblemToStructureArchitecturingFlowCard@Project` -> return to `C.30`, `C.30.TFS-REL`, `C.32`, `C.32.PAD`, A.15-family work patterns, `E.23`, or `G.11` when the next claim is stronger than the P2S card.

First inspect: `C.32.P2S`, `C.30`, `C.30.TFS-REL`, `A.22`, `A.22.CGUS`, `C.32`, `C.32.PAD`, `C.32.ADR`, `C.33`, `C.34`, `C.35`, `C.30.ASV`, `C.30.AD`, `C.31`, `C.32.CONWAY`, and `B.2` or `B.2.P` when the work may reidentify the whole being discussed.

### 2. Write working rules, methods, and work-process documents

Use this when you need a document that people, teams, tools, or AI agents can use to do the same kind of work: technical regulation, procedure, method description, operating instruction, work-process description, standard-like project document, API document, contract, SLA, protocol, or permission text.

FPF helps decide what the document must actually produce: a method, method description, work plan, interface boundary, work-entry condition, publication use, or performed-work record. That matters because one text can guide work, describe a method, authorize a transition, or report completed work, but it should not silently do all of those jobs at once.

Typical first result: a working-document outline that names the governed object, intended users, method or interface being described, relevant roles, expected work result, and any stronger work, evidence, gate, permission, or publication claim that needs its direct governing pattern.

Entry seed: governed object and document pressure -> method or method-description record plus neighboring work, role, interface, evidence, gate, permission, tool-use, or publication claims -> return to the direct governing pattern when the document starts launching work, fixing completion, or authorizing a transition.

First inspect: `A.6`, `A.6.B`, `A.6.C`, `A.15`, `A.15.1`, `A.15.2`, `A.15.3`, `A.15.4`, `C.24`, `E.18`, `E.18.1`, `E.18.3`, `A.22.CGUS`, `E.8`, and `E.19`.

### 3. Compare alternatives and make a local choice

Use this when a team needs to compare technologies, vendors, designs, policies, research paths, implementation options, or architecture moves without jumping to one favorite too early.

FPF helps you state what is being compared, which characteristics matter, which candidates are still in play, what evidence is missing, when a local choice is justified, and how to publish a selected set without hiding the comparison logic.

Typical first result: a comparison note with declared characteristics, candidate set, evidence gaps, the present scope of the choice, and what a selected-set publication may and may not be used to decide.

Entry seed: candidate or option field -> comparison frame, archive/front/pool, selected set, or local choice -> return to decision, publication, or refresh governing pattern only after the choice relation is explicit.

First inspect: `A.19`, `A.19.ECS`, `C.11`, `C.18`, `C.19`, `G.0`, and `G.5`.

### 4. Turn a vague situation into a usable problem statement

Use this when a project has complaints, opportunities, risks, anomalies, or strategic pressure, but no clear problem yet.

FPF helps you preserve partly formed concerns without pretending they are already requirements, decisions, causes, evidence, or work items. It can turn a vague situation into a problem card or problem portfolio that later work can use without erasing uncertainty.

Typical first result: a problem card, problem portfolio, or problem note that records what has been accepted, what remains only a cue, which context is involved, and which first pattern family can use the problem statement.

Entry seed: cue, anomaly, opportunity, or pressure -> preserved cue set and `ProblemCard@Context` or portfolio -> return to the first downstream governing pattern only after the problem-side record is admitted.

First inspect: `C.22.2`, `C.2.2a`, `A.16`, `A.16.1`, `A.16.2`, `B.4.1`, `B.5.2`, and `B.5.2.0`.

### 5. Define what "better" means and run improvement

Use this when you need to improve a product, process, architecture, document, pattern, regulation, research program, or organization, but the improvement criteria are vague or competing.

FPF helps you define characteristics for evaluation, evaluate what is being improved, generate a portfolio of improvement proposals, choose changes that really improve the situation, and repeat the cycle without reducing quality to one score.

Typical first result: a quality-and-improvement note with evaluation characteristics, one evaluation of the object under improvement, a portfolio of proposed changes, and a condition for stopping or reopening the cycle.

Entry seed: object version under concern -> evaluation frame and first evaluation result -> `E.23` improvement unfolding with candidate repair loci, protected tradeoffs, re-evaluation, and stop/continue/switch decision.

First inspect: `A.19.ECS`, `E.22`, `E.23`, `A.22.CGUS`, `C.16`, `C.25`, `E.21`, `E.9.DA`, and `E.2.DA` when the object is an FPF artifact.

### 6. Prepare a costly or hard-to-reverse action

Use this when the team is ready to act, but the next move spends real money, changes architecture, launches team work, crosses an external boundary, creates a promise, accepts risk, or is expensive to undo.

FPF helps choose the action mode. The project may act now on a named basis, run a smaller experiment, narrow the claim, collect a specific piece of evidence, name an assurance use, pass a gate, make a decision, or return to the work or architecture pattern that governs the stronger claim.

Typical first result: a commitment-readiness note that names the action, the claim it relies on, the minimum basis for that action, any smaller experiment that can reduce cost, any gate or decision boundary, and what the project can do next.

Entry seed: costly or hard-to-reverse action -> commitment-readiness note -> act on named basis, run a smaller experiment, narrow the claim, or return to evidence, assurance, gate, decision, work, or architecture pattern when that stronger claim is live.

First inspect: `A.10`, `B.3`, `A.20`, `A.21`, `C.11`, `C.28`, and the relevant work or architecture pattern if the claim is about planned or performed work.

### 7. Account for timing, freshness, rhythm, and action windows

Use this when a result depends on timing: freshness, latency, rate, cadence, action window, synchronization, inertia, aging, or rhythm.

FPF helps connect timing to the action that uses it. It can say what timestamp, interval, cadence, freshness limit, action window, or rhythm matters, which decision or work depends on it, and when refresh, delay, or re-check changes the next move.

Typical first result: a timing note that names what the timing is about, the relevant time relation or rhythm, the freshness or action-window limit, and the decision, work, publication, comparison, or refresh action that uses it.

Entry seed: object whose timing matters -> temporal aspect, currentness window, freshness limit, or action-window rule -> return to the affected decision, work, evidence, publication, comparison, or `G.11` refresh governing pattern.

First inspect: `C.27`, `A.10`, `A.20`, `A.21`, `C.11`, and the pattern that governs the object whose timing matters.

### 8. Use causal explanations, interventions, responsibility, and model outputs for action

Use this when a project wants to rely on a causal explanation, forecast, simulation, dashboard signal, model output, intervention claim, or responsibility assignment to choose what to do next.

FPF helps turn an explanation or model output into a governed next move: study, smaller experiment, intervention, decision, responsibility assignment, work, or stop condition. It makes the intended use explicit before the output is carried into action.

Typical first result: a causal-use or model-output-use note that names the claim, the action or intervention being considered, the minimum basis needed for that use, the responsibility boundary, and what can be done next.

Entry seed: causal explanation, intervention, responsibility, or model output -> causal-use or counterfactual-use frame with action and responsibility boundary -> return to study, decision, work, evidence, or stop condition under the direct governing pattern.

First inspect: `C.28`, `A.10`, `B.3`, `A.20`, `A.21`, `C.11`, and the domain pattern that governs the affected object.

### 9. Compare descriptions, dashboards, explanations, and views of the same described object

Use this when a project has several descriptions, dashboards, explanations, renderings, model slices, or views and needs a working picture for different roles without losing the described object.

FPF helps name the described object, the description or view being used, the publication or rendering form, the role concern, and the next claim that the description is supposed to support. It also shows what each view preserves, coarsens, omits, or loses.

Typical first result: a description-use note that names what is being described, which description or view is being used, how it is published or rendered, whether the same described object is really being addressed, and what the publication may be used to claim next.

Entry seed: described EntityOfConcern -> description, view, rendering, publication form, correspondence, representation transition, or same-use relation -> return to the governing pattern when the view is used for evidence, architecture, decision, work, or assurance.

First inspect: `E.17`, `E.17.0`, `E.17.EFP`, `A.6.2`, `A.6.3.NAR`, `A.6.3.RT`, `A.6.3.CSC`, `A.6.4`, `A.15.4`, `A.7`, `A.22.CGUS`, `C.30.AD`, `C.30.TFS-REL`, `C.33`, `C.34`, `C.35`, and the pattern that governs the described object.

### 10. Give project objects, relations, and claims better names

Use this when project terms are misleading, overloaded, politically convenient, too broad, too local, or hard to translate between teams.

FPF helps you name products, roles, work processes, architecture elements, standards, document types, claims, characteristics, and project objects without treating a catchy label as ontology.

Typical first result: a naming card or term sheet that says what is being named, which local contexts use the name, which candidate names were rejected, which plain and technical names are allowed, and which alternate names are risky.

Entry seed: object, kind, relation, or use needing a better name -> bounded contexts, candidate names, and name card -> return to bridge, UTS, publication, or subject pattern before the name changes work.

First inspect: `F.17`, `F.18`, `F.19`, `E.10`, `E.10.ARCH`, and the subject pattern that governs the object, relation, or claim being named.

### 11. Clarify wording that drives work

Use this when a standard, specification, contract, policy, dashboard, model card, explanation, or working document contains wording that people or AI agents will use to decide what can be claimed or done.

FPF helps repair the wording after recovering the working object, relation, value, use, and affected claim. The goal is not word-policing; the result should leave a usable claim, a clear use boundary, a revised paragraph, or an exit to the direct pattern that governs a stronger action.

Typical first result: a repaired paragraph, claim register, term sheet row, or use-boundary note that says what the text may now be used for and what stronger claim or action needs another pattern.

Entry seed: wording that may change action -> recovered kind, relation, use, and rewritten claim or use-boundary result -> return to the direct governing pattern for any stronger action.

First inspect: `E.10`, `E.10.ARCH`, `F.18`, `F.19`, `A.6.P`, `C.2.P`, `B.3.5`, `C.13`, `C.3`, `C.16.P`, `C.16.Q`, `C.30.P`, `A.6.F`, and `A.6.M`.

### 12. Decide whether a mathematical model or formal declaration would help

Use this when ordinary prose and intuition no longer hold the needed dependencies, constraints, dynamics, comparison, probability, optimization, or invariants.

FPF helps decide whether a mathematical lens or formal substrate gives a practical gain. It asks what structure the model preserves, what it hides or loses, what claim the model supports, and which validation, measurement, architecture, domain, or work pattern must govern stronger use.

Typical first result: a short modeling note that names what is being modeled, the candidate mathematical lens, any formal declaration that is needed, preserved and lost structure, payoff, validation limit, and next project action.

Entry seed: project difficulty that may need formal structure -> candidate lens or formal substrate with preserved and lost structure -> return to validation, next FPF use, or P2W carry-through.

First inspect: `C.29`, `A.6.0`, `A.6.1`, `E.18.1`, `B.3.5`, `C.13`, `C.3`, `C.16`, `C.27`, `C.30.LCA`, `C.30.ILC`, and the domain pattern that governs the modeled claim.

### 13. Build a state-of-the-art or option portfolio

Use this when the project needs the current field of possible solutions, schools of thought, research lines, technologies, or design options, rather than one recommendation.

FPF helps you harvest alternatives, keep novelty and diversity visible, define comparison characteristics, avoid early collapse to one winner, and refresh the portfolio as the field changes.

Typical first result: a SoTA pack, option portfolio, candidate set, archive, or selector-ready publication with declared scope, comparison characteristics, and refresh condition.

Entry seed: scope and current-front question -> reference harvest, candidate/archive/front, comparison, selection, and publication -> return to `G.11` when a source-currentness relation or reference-edition state changes.

First inspect: `G.0`, `G.1`, `G.2`, `G.5`, `G.11`, `C.18`, `C.19`, `A.19`, and `A.19.ECS`.

### 14. Build a domain or local FPF-grounded framework

Use this when a team needs its own pattern language for a domain, organization, role context, or local practice, such as a hydroponic-cucumber framework, neural-network architecture framework, enterprise architecture-review framework, or Codex-process framework.

FPF helps choose the architecture of that local framework: Core dependency, domain source set, selected pattern set, relation records, edition dependencies, publication or access carrier, quality loop, and refresh trigger. This is the normal adoption path when a group wants FPF for its own field without silently changing Core meaning.

Typical first result: a family-and-structure map or principle-framework architecture decision that names the framework edition, bounded context, FPF Core dependency, selected first patterns, relation and publication carriers, source pack, quality loop, and refresh trigger.

Entry seed: local context and domain reference set -> PFAD, PFR, pattern candidates, source pack, quality loop, publication or access carrier, and refresh trigger -> return to `E.4.DPF` for the full authoring spine.

In the first hour, write the context note, source-pack stub, first PFAD question, provisional naming card, one to three pattern candidates, relation rows, first-entry carrier, quality loop, and refresh trigger. Then open `E.4.DPF` for the full authoring spine.

First inspect: `E.4`, `E.4.FPF` when the form of FPF itself is live, `E.4.PFAD`, `E.4.DPF`, `E.4.DPF.DA`, `E.4.PFR`, `G.2`, `C.24`, `E.8`, `E.11`, `E.17`, `F.18`, and `G.11`.

## One-Minute Example

A platform team asks:

> Should we buy, fine-tune, or build an agent stack for our product?

Without FPF, the conversation often mixes architecture, vendor comparison, safety, evidence, budget responsibility, user value, and implementation planning. The loudest option can win before the team knows what is being compared.

With FPF, the first pass can become a small set of explicit project objects:

- holons in play: the product, the agent stack, and the team or toolchain that will change it are not the same holon;
- architecture flow: what problem pressure should become which candidate, selected, expected, and actual structures;
- comparison frame: which alternatives are in the candidate set;
- evaluation characteristics: cost, latency, controllability, safety, maintainability, time to first use, and other project-specific characteristics;
- evidence gaps: what must be tested before commitment;
- current decision state: whether the team is choosing now, keeping a selected set, making a project architecture decision, or doing more discovery;
- work and feedback: what method, readiness, and performed-work records must later show that the selected structures were actually realized;
- reader reliance: what engineering, management, and assurance readers may responsibly rely on.

That same shape can be used for a factory modernization, laboratory protocol, construction design change, supply-chain decision, safety case, or research program. The point is not the AI topic; the point is one body of reasoning that can be reviewed, improved, and published without changing meaning on the way.

## What FPF Is

FPF is a pattern language for disciplined thinking in projects where ordinary prose, local expert judgment, or one-off AI output is not enough.

It helps teams:

- keep meanings stable when work crosses teams, tools, documents, and time;
- separate the project object being discussed from diagrams, dashboards, explanations, promises, decisions, and actual work;
- state what a claim can responsibly be used for before people rely on it;
- compare options without collapsing too early to one favorite;
- define quality criteria before improvement starts;
- keep evidence, assurance, decisions, and implementation work visible as different questions;
- carry architecture work from problem pressure to real structures and feedback instead of stopping at diagrams or decision prose;
- grow domain or local frameworks from FPF Core without silently changing Core meaning;
- repair confusing wording by first asking what the wording is doing in the project, not by swapping synonyms;
- leave each pass with one useful next result: a clearer question, a better name, a comparison note, an evidence gap, a safer document, or a reason to inspect a specific pattern.

## What FPF Is Not

FPF is not:

- a shrink-wrapped project methodology;
- a checklist bureaucracy;
- a quick-answer cheat sheet;
- a replacement for domain expertise;
- a demand to study the whole specification before useful work begins;
- a promise that every project needs every pattern.

FPF is most useful when the cost of semantic drift, premature convergence, hidden evidence gaps, weak architecture, vague quality, or unreviewable work is higher than the cost of using a disciplined pattern language.

## How to Use This Repository

Start with the first practical entry that matches your project question. Then inspect the named pattern family and apply its Problem frame, Solution, examples, and checklist.

Use the `Preface` for the cross-cutting ideas behind the pattern language. Use the Table of Content when you already know the pattern family or need a search-oriented overview. Use `E.11.PUR` when you need a bounded recommendation or sequence of pattern uses for one concern. Use extended cases only when the compact first entry is not enough.

If you use an AI assistant, attach or index `FPF-Spec.md` and ask for plain-language project help first. Let internal pattern names enter the conversation only when they make the reasoning more precise.

A good first prompt is:

```text
You have the FPF specification as a file.
Help me structure this project:
[short project description]

Use plain language for engineer-managers.
Propose the first useful FPF entry:
architecture, working rules and methods, comparison and choice,
problem shaping, quality improvement, commitment-ready action,
timing and freshness, causal or model-output use, description or view use,
naming, wording that drives work, mathematical modeling,
current options and state of the art,
or a domain/local FPF-grounded framework.
For the selected entry, give:
1. the main project object or claim at stake,
2. the first useful written result,
3. the first FPF patterns to inspect,
4. where the short entry ends, and which stronger claim needs a governing pattern.
```

## Citation

If you use FPF, please cite:

```text
Levenchuk, Anatoly. First Principles Framework (FPF).
GitHub repository: https://github.com/ailev/FPF
```
