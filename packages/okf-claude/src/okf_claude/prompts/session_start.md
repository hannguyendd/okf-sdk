# OKF memory

This session has long-term memory in the OKF bundle `{{bundle}}` (workspace
`{{workspace}}`), served by the `okf` MCP server.

- Before non-trivial work, check what is already known: `mcp__okf__search` for a
  question in plain words (needs embeddings; if it errors, browse with
  `mcp__okf__read_index`, then `mcp__okf__list` / `mcp__okf__get`).
- When you learn something durable (a decision and its reason, a convention, a
  gotcha, how a subsystem works), save it with `mcp__okf__add`, or
  `mcp__okf__patch` the concept that already covers it. Do not save secrets,
  personal data, or short-lived state.
- `episodes/` is written automatically when a session ends; do not write
  episodes yourself.
- The user can run `/okf-remember` and `/okf-recall` for explicit saves and lookups.
{{recent}}
