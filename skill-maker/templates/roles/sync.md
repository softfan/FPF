# Role: sync

Keep this skill's derived artefacts in step with their source. The source is
authoritative; everything else is regenerated.

## Cycle

```
1. Check    -- has the source changed since the last build?
2. Rebuild  -- regenerate only what the change affects.
3. Verify   -- does the result still match the source?
4. Report   -- what changed, in a reader's terms.
```

## 1. Check

Compare the source digest with the one recorded in the build stamp
(`.<skill>_build.json`). If they match, and the manifest's files all exist, the
skill is current: stop.

A change to a template or to the generator is also a change: the stamp covers
the engine as well as the sources, so a template edit triggers a rebuild even
when the source is untouched.

## 2. Rebuild

```
{{REBUILD_CMD}}
```

The build reports `Written` and `Skipped`. A rebuild that writes nothing is a
no-op, not a refresh -- say so rather than reporting it as an update.

## 3. Verify

Run the checks that exist for this tree:

- the audit, which compares the skill with its source;
- the tests, which pin the invariants (counts, file set, idempotency);
- a rebuild round-trip, when the source must be recoverable.

## 4. Report

Describe the change from the reader's side: which units are new, which moved,
which disappeared. Do not paste commit messages.

## Guardrails

- Never edit a generated file; edit the source or the template.
- Never report a refresh that wrote nothing.
- Verify before reporting: output is not correctness.
