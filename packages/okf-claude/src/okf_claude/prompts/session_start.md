# OKF memory

{{intro}}{{overview}}
## When to use it

Read the overview above first and decide whether this memory is relevant to the
task. If the task touches a topic it covers, consult it before non-trivial work;
if the task is unrelated (a one-off question, a different project), skip it and
do not call OKF tools just to look.
{{choose}}
- To look something up: `{{prefix}}search` for a question in plain words (needs
  embeddings; if it errors, browse with `{{prefix}}read_index` on a directory
  from the overview, then `{{prefix}}list` / `{{prefix}}get`).
- When you learn something durable (a decision and its reason, a convention, a
  gotcha, how a subsystem works), save it with `{{prefix}}add`, or
  `{{prefix}}patch` the concept that already covers it. Do not save secrets,
  personal data, or short-lived state.
- `episodes/` in {{episodes}} is written automatically when a session ends; do
  not write episodes yourself.
- The user can run `/okf-remember` and `/okf-recall` for explicit saves and lookups.
{{recent}}
