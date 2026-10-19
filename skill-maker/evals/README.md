# Optional skill quality evaluations

These fixtures test usefulness, not parser correctness. They are deliberately
outside the disposable `skills/` tree. The regular offline regression suite
checks their format; it does not invoke a model or access the network.

## Run manually, with explicit model/usage approval

1. Build the skills. Record the repository commit, corpus snapshot, model,
   client and model settings used for the evaluation.
2. For each case in `cases.json`, use two fresh sessions with the same prompt
   and context: one with the named skill, one without it (or with a previous
   skill version). Do not give the agent the expected-output rubric.
3. Save the output, consulted sources and execution trace for both sessions.
   Record actual tokens, elapsed time and bytes read when the client provides
   them; use `null`, not an estimate, for unavailable measurements.
4. Grade each output against the case assertions with cited evidence. Check
   source IDs and section references mechanically against the built tree.
5. Compare correctness, relevance, unsupported claims and reading cost. A
   structurally valid answer is not automatically a useful one.

For trigger checks, install the skills generated from your current inputs and
use `trigger_queries`.
`should_trigger: false` cases are close alternatives, not random irrelevant
questions. Observe whether the named skill was actually loaded. Report raw
counts initially; repeat runs before drawing reliability conclusions. Keep
fresh holdout prompts when tuning descriptions.

Store results outside the generated skills, for example in the gitignored
`skill-maker/evals/results/iteration-1/` directory. Suggested result fields:

```json
{
  "case": "decision-acquire-or-learn",
  "configuration": "with_skill",
  "snapshot": "local-...",
  "model": "record the actual model",
  "tokens": null,
  "elapsed_ms": null,
  "bytes_read": null,
  "assertions": [
    {"name": "record the assertion", "passed": false, "evidence": "quote or file reference"}
  ],
  "human_feedback": ""
}
```

No quality uplift is claimed until these paired evaluations have actually run.

References: [quality evaluation](https://agentskills.io/skill-creation/evaluating-skills)
and [trigger evaluation](https://agentskills.io/skill-creation/optimizing-descriptions).
