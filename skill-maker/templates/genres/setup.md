## What this skill installs

This skill describes how to make a service reachable from a client, and how to
prove that it is. The two are different claims and need different evidence.

## Four layers of evidence

Keep them separate when you report a result. "Configured" is not "working".

| Layer | The claim | The evidence |
| :--- | :--- | :--- |
| Configuration | a setting was added | the snippet, quoted, and where it was written |
| Connection | the client reaches the server | the tool list the client received |
| Runtime | the server answers a real request | one call's actual result |
| Freshness | the answer is current | the snapshot or version the server reported |

A report that stops at configuration is a report about editing a file.

## Setup routes

| Client capability | Route |
| :--- | :--- |
| HTTP or streamable HTTP | point the client at the endpoint; no local process |
| stdio only | run the server as a local command |
| local URL required | run the server locally and point it at the same data |

If a client supports only a local command, do not claim a hosted endpoint solves
that. Choose the route the client actually supports.

## Validation

After any setup, run a first-call check and report which of the four layers it
covers:

1. Call the status tool. It must return a snapshot and a count.
2. Confirm the client lists the expected tools.
3. Run one narrow query and read its result.
4. State the snapshot you saw, so a later reader can tell whether it moved.

## Guardrails

- Do not paste a whole publication into a conversation to prove access.
- Do not treat a successful handshake as proof that a query returns useful
  results.
- Do not invent install commands for a client whose current documentation you
  have not read.
