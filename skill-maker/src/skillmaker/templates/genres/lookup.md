## Choosing what to read

A unit is one file, but not one reading. Each file carries working sections --
problem frame, solution, conformance checklist, consequences, relations -- and
depth sections -- worked cases, rationale, source comparison. {{CONTRACT_NOTE}}

Three ways to read less:

| You have | Do this |
| :--- | :--- |
| An ID and a question | `read_pattern(id, tier="contract")` -- working sections only |
| A section name | `read_pattern(id, section="solution")` |
| No tooling | Read the line range from `reference/sections.json` |

`reference/pattern-index.md` gives the byte cost of each unit before you open
it. `reference/sections.json` gives the line range and anchor of every section.
`reference/<framework>/contract/<ID>.md` holds the working sections as a file, when the
build emitted views.

## Stop rule

Read the working sections. Open the depth sections only when the working
sections leave a real question: a condition you cannot evaluate, or a claim you
must check against its grounding. Reading a whole publication is almost never
the right move.
