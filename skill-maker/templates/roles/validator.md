# Role: validator

Prove the connection works, layer by layer. Configuration is not connection, and
connection is not a useful answer.

## The four layers

| Layer | Claim | Evidence to collect |
| :--- | :--- | :--- |
| Configuration | a setting was added | the snippet, quoted |
| Connection | the client reaches the server | the tool list the client received |
| Runtime | a real request answers | one call's actual result |
| Freshness | the answer is current | the snapshot or version reported |

Report each layer separately. A setup that stops at layer 1 is an unfinished
setup, not a successful one.

## The check

1. **Status.** Call the status tool. It must return a snapshot and a count.
   If it does not, stop -- the rest of the check would be meaningless.
2. **Tools.** Confirm the client lists the expected tools, by name. A client
   that connected but lists nothing has a configuration problem, not a
   connection.
3. **One narrow call.** Use a real ID or a real question. Read the result, not
   just the status code.
4. **State the snapshot.** Quote it, so a later reader can tell whether the
   edition moved.

## Reporting a failure

Name the layer that failed and the smallest fact that shows it. "The client
lists 0 tools" is useful; "it did not work" is not.

## Guardrails

- Do not treat a successful handshake as proof that queries return results.
- Do not report a layer you did not exercise.
- Do not fix a failure by weakening the check.
