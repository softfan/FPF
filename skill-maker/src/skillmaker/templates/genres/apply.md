## Choosing the scope

Use the smallest analysis that answers the request. Do not run a fixed sequence
of roles, repeat intermediate outputs, or ask permission to apply a method that
was already requested.

Ask only when missing information materially changes the result and cannot be
reasonably inferred. Low confidence in routing is not a reason to stop: continue
with a narrow lookup, or state the assumption you are making.

## The pipeline

This skill ships four roles in `roles/`. They are a division of work, not a
requirement to spawn four agents -- one agent may play all four in sequence.

| Step | Role | Question it answers |
| :--- | :--- | :--- |
| 1 | `roles/classifier.md` | Does this material apply, and how deep? |
| 2 | `roles/retriever.md` | What is the minimum that answers it? |
| 3 | `roles/reasoner.md` | What is the answer, in the asker's language? |
| 4 | `roles/reviewer.md` | Is it grounded, specific and free of jargon? |

Start at step 1 when the request is a situation. Skip to step 3 when the
material has already been retrieved.

## Answer shape

Structure the answer for the question, not for the framework: a table for a
comparison, a list for steps, prose for a judgement. Every recommendation should
be executable without a follow-up question -- name who does what, with the
threshold or wording that matters.

Use the asker's vocabulary. The framework's terms are how you found the
material; they are rarely how the answer should read. When the asker explicitly
asks about the framework, its terms and citations belong in the answer.

## What not to do

- Do not narrate the pipeline to the asker.
- Do not produce generic advice; every point must fit the stated situation.
- Do not present a claim the loaded material does not support, and do not
  present an inference as established fact.
