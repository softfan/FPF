## What this skill maintains

This skill keeps a derived artefact in step with its source. The source is
authoritative; everything else is regenerated. Editing a generated file is
always the wrong move.

## The cycle

```
check source -> rebuild -> verify -> report
```

| Step | Question | Evidence |
| :--- | :--- | :--- |
| Check | did the source change? | the digest of the source, before and after |
| Rebuild | what did the rebuild produce? | written / skipped counts |
| Verify | does the result still match the source? | the audit and the test results |
| Report | what changed, in the reader's terms? | counts and named differences |

## Early exit

If the source digest is unchanged and the derived artefact is complete, stop.
Rebuilding identical output is not maintenance.

The exception is a local edit to a template or a generator: the source has not
changed, but the output must. The build stamp covers the engine as well as the
sources for exactly this reason, so a template edit still triggers a rebuild.

## Guardrails

- Never edit a generated file; change its source or its template.
- Never report a rebuild that wrote nothing as a refresh.
- Verify before reporting: a rebuild that produced output has not thereby
  produced *correct* output.
