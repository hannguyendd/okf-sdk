---
description: Save durable knowledge from this session to OKF memory
argument-hint: [what to remember]
---

Save this to OKF memory: $ARGUMENTS

If nothing is given above, pick the most important durable knowledge from this
conversation so far (decisions and their reasons, conventions, gotchas, how
something works) and save that.

1. Look for a concept that already covers it: `mcp__okf__search` with a short
   query (if search is unavailable, use `mcp__okf__read_index` and
   `mcp__okf__list`). If one fits, `mcp__okf__get` it and update it with
   `mcp__okf__patch` instead of creating a duplicate.
2. Otherwise create it with `mcp__okf__add`. Choose a `concept_id` that fits the
   bundle's existing layout (`read_index` shows it; segments use letters,
   digits, `_`, `.`, `-`), e.g. `decisions/use-sqlite-vec`. Frontmatter: `type`
   (e.g. `decision`, `convention`, `howto`, `gotcha`, `reference`), `title`, a
   one-sentence `description`, and `tags`. Write the body as standalone
   markdown that makes sense without this conversation; link related concepts
   with relative markdown links.
3. Never save secrets, credentials, or personal data. Do not write under
   `episodes/` (those are written automatically).

Finish with one line per concept: the id, and whether it was added or updated.
