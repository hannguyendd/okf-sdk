# okf-mcp — `move` Tool Design

**Date:** 2026-06-29
**Status:** Approved (brainstorming) — ready for implementation plan
**Depends on:** `okf-core` (link extraction, indexing, path APIs), `okf-mcp` producer server (§ patterns from `2026-06-29-okf-mcp-producer-design.md`)

## 1. Motivation

The producer server can `add` and `patch` concepts but cannot **relocate**
one. Renaming a concept (`tables/orders` → `models/orders`) or moving it to a
different directory today means manual file surgery plus a stale bundle:
`index.md` files drift and every relative markdown link that pointed at the old
path silently breaks.

This spec adds a **`move`** tool that relocates a concept by id, regenerates
indexes, records the change in `log.md`, and — crucially — **rewrites the
markdown links** so the bundle stays internally consistent after the move.

### Goals

- A `move(from_concept_id, to_concept_id, bundle_root=None)` MCP tool, backed by
  a framework-agnostic `operations.move_concept`.
- Move the underlying `.md` file from the source path to the destination path.
- Regenerate indexes and append a `log.md` entry, matching `add`/`patch`.
- **Rewrite links** so no internal link breaks:
  - inbound links from other concepts that point at the moved concept;
  - the moved concept's own relative outbound links, when its directory changes.
- Add one reusable link-rewriting primitive to `okf-core` (the single home for
  "how OKF links resolve"), keeping okf-mcp free of duplicated resolution logic.

### Non-goals

- No multi-concept / directory moves (move one concept per call).
- No deletion tool (a move removes the source file as part of relocating it, but
  there is no standalone `delete`).
- No rewriting of `log.md` history or `index.md` (index is regenerated; logs are
  append-only historical records — see §5).
- No rewriting of external `scheme://` links or non-markdown link targets.
- No bundle-wide conformance validation inside the tool (re-index only, as with
  the other write tools).

## 2. Architecture

Follows the existing **thin-server-over-operations** split:

```
packages/okf-core/src/okf_core/
└── links.py (new)              # rewrite_links() pure primitive; re-exported from __init__
packages/okf-mcp/src/okf_mcp/
├── operations.py               # + move_concept() orchestrator
└── server.py                   # + @mcp.tool() move() thin wrapper
```

- **`okf_core.rewrite_links`** (new pure function) recomputes the link text in a
  document body for a possibly-changed source directory and a remap of target
  concept ids. No I/O. Unit-tested directly. Re-exported from
  `okf_core/__init__.py` and listed in `__all__`.
- **`operations.move_concept`** orchestrates: validate ids, read the source,
  rewrite the moved doc's own links, write to the destination, delete the
  source, rewrite inbound links across the rest of the bundle, regenerate
  indexes, append log entries, return a summary.
- **`server.move`** is a thin `@mcp.tool()` wrapper that resolves the bundle root
  and delegates, like the other tools.

## 3. Tool: `move`

All identifiers are **concept IDs** — the bundle-relative path with no `.md`
suffix (e.g. `tables/orders`). Both ids are validated via the existing
`operations._concept_path`, so invalid segments and reserved final segments
(`index`/`log`, RSV-01) are rejected on **both** the source and destination.

### 3.1 Parameters

- `from_concept_id: str` — the concept to move (e.g. `tables/orders`).
- `to_concept_id: str` — its new id (e.g. `models/orders` or `tables/sales`).
- `bundle_root: str | None = None` — override (§ producer-design §3).

### 3.2 Behavior

1. Resolve bundle root; compute `from_path` and `to_path` via `_concept_path`
   (validates ids; rejects reserved/invalid segments).
2. **Error if `from_path` does not exist** (`concept not found`).
3. **Error if `to_path` already exists** (`destination already exists` — `move`
   never clobbers, mirroring `add`).
4. **No-op guard:** error if `from_concept_id == to_concept_id`.
5. Parse the source with `OKFDocument.parse`.
6. Rewrite the moved doc's **own body** with `rewrite_links` (§4) for the
   directory change `from_path.parent → to_path.parent` and the id remap
   `{from_id: to_id}`. When the directory is unchanged (pure in-dir rename) this
   is a no-op for the body.
7. Create destination parent dirs; write the (possibly relinked) document to
   `to_path`; delete `from_path`.
8. **Timestamp:** left unchanged — a move/rename is not a content edit, so the
   concept keeps its existing `timestamp`. (If absent, it is *not* synthesized.)
9. **Rewrite inbound links:** load the bundle (`Bundle.load`), and for every
   other concept whose body links to `from_id`, rewrite its body with
   `rewrite_links` using its own (unchanged) directory and the remap
   `{from_id: to_id}`, then write it back only if the text actually changed.
10. `regenerate_indexes(bundle_root)` — covers source dir, destination dir, and
    every dir whose links were rewritten.
11. Append **Move** log entries (§5).
12. Return the summary (§6).

## 4. Link rewriting (`okf_core.rewrite_links`)

The core primitive. Signature:

```python
def rewrite_links(
    body: str,
    doc_dir_old: Path,
    doc_dir_new: Path,
    bundle_root: Path,
    id_map: dict[str, str],
) -> str
```

Recompute each markdown link in `body` so that, after the document moves from
`doc_dir_old` to `doc_dir_new` and targets are remapped per `id_map`
(old concept id → new concept id), every internal link still resolves to the
intended concept. Returns the rewritten body (unchanged string when nothing
applies).

It reuses the **exact resolution rules** of `okf_core.extract_links`:

- The same link regex (`](target.md)` with optional `#anchor`), so only true
  markdown links are touched.
- Relative targets resolve against `doc_dir_old`; absolute targets (`/…`)
  resolve against `bundle_root`; `scheme://` targets are skipped untouched.
- Targets that escape the bundle root are left untouched.

For each matched link:

1. Resolve the old target to a concept id (using `doc_dir_old` / `bundle_root`).
2. Compute the **new target id** = `id_map.get(old_id, old_id)`.
3. Compute the new target path = `concept_id_to_path(bundle_root, new_id)`.
4. Re-render the link text from `doc_dir_new` to that path, **preserving**:
   - the `#anchor` suffix, if any;
   - the **absolute (`/…`) vs relative** style of the original link — an
     absolute link stays absolute (`/models/orders.md`); a relative link is
     recomputed relative to `doc_dir_new` (e.g. `../models/orders.md`).
5. Replace the matched target only when the newly rendered text differs (to
   minimize churn). Everything outside `](…)` is preserved verbatim.

Relative path computation uses POSIX-style segment math (e.g.
`os.path.relpath` over bundle-relative posix paths), yielding forms like
`orders.md`, `sub/orders.md`, or `../models/orders.md`. A leading `./` is not
re-synthesized (a same-dir target renders as a bare `name.md`).

### 4.1 How the two cases use it

| Case | `doc_dir_old` | `doc_dir_new` | `id_map` | Effect |
|------|---------------|---------------|----------|--------|
| Moved doc's own body | old dir | new dir | `{from_id: to_id}` | When the dir changes, all its relative links are recomputed so they still resolve to the same targets; absolute links unchanged. |
| Each inbound concept | its dir | its dir (same) | `{from_id: to_id}` | Only links resolving to `from_id` change (re-pointed at `to_id`'s path); all other links render identically and are left as-is. |

Only concept documents are rewritten. `index.md` is regenerated by
`regenerate_indexes`; `log.md` is append-only history and is **not** rewritten.

## 5. Log appending

Reuses the existing `_append_log` machinery (newest-first `## YYYY-MM-DD`
groups, LOG-01/LOG-02). A move can touch two directories, so:

- **Destination dir** `log.md` gets an arrival entry:
  `* **Move**: Moved [<label>](<new-name>.md) from \`<from_id>\`.`
- **When the source directory differs**, the source dir `log.md` also gets a
  departure entry:
  `* **Move**: Moved [<label>](<from-name>.md) to \`<to_id>\`.`
  (For a pure in-directory rename, only the single destination entry is written.)

`<label>` is the concept's `title` if present, else the destination's last id
segment. Inbound-link rewrites do **not** add log entries (they would be noisy
and are implied by the move).

## 6. Return value

```json
{
  "from": "tables/orders",
  "to": "models/orders",
  "action": "moved",
  "relinked": ["tables/customers", "metrics/revenue"],
  "logs": ["models/log.md", "tables/log.md"],
  "indexes": ["index.md", "models/index.md", "tables/index.md"]
}
```

- `relinked` — bundle-relative ids of **other** concepts whose bodies were
  rewritten (excludes the moved concept itself). Empty list when none.
- `logs` — bundle-relative paths of the `log.md` files written (one or two).
- `indexes` — bundle-relative paths returned by `regenerate_indexes`.

All paths are bundle-relative POSIX strings.

## 7. Error handling

Preconditions raise `ValueError` with actionable messages (FastMCP surfaces them
as tool errors):

- bundle root unresolved or not a directory (shared resolver);
- `from_concept_id` / `to_concept_id` invalid or a reserved final segment
  (`index`/`log`);
- `from_concept_id == to_concept_id` (nothing to move);
- source concept does not exist;
- destination already exists.

I/O and YAML errors propagate as-is (`OKFDocumentError` / `OSError`).

## 8. Testing (TDD)

**`okf-core` — `rewrite_links` unit tests** (against `tmp_path` / synthetic
bodies):

- relative inbound link to the moved id is re-pointed to the new path
  (same-dir, deeper-dir, and `../` cases);
- absolute (`/…`) inbound link stays absolute, re-pointed to the new path;
- `#anchor` is preserved across the rewrite;
- external `scheme://` and out-of-bundle (`../outside.md`) links are untouched;
- links not in `id_map` are untouched when `doc_dir` is unchanged;
- moved doc's own relative links are recomputed when its dir changes; absolute
  ones are not;
- no-op returns the body unchanged (string identity not required, equality is).

**`okf-mcp` — `move_concept` unit tests** (against `tmp_path` bundles):

- pure in-dir rename: file relocates, old path gone, in-dir log entry written,
  single destination log, indexes regenerated;
- cross-dir move: file relocates, both source and destination `log.md` updated,
  destination dir index created;
- inbound rewrite: another concept linking `[..](orders.md)` / `[..](/tables/orders.md)`
  is rewritten to the new path and listed in `relinked`;
- moved doc outbound rewrite: a relative link in the moved doc still resolves to
  the same target after a cross-dir move;
- errors: missing source, existing destination, `from == to`, reserved/invalid
  ids;
- timestamp is preserved (not refreshed) by a move.

**`test_server.py`** smoke: the `move` tool is registered alongside the existing
five.

## 9. Housekeeping

- Export `rewrite_links` from `okf_core/__init__.py` (add to `__all__`).
- Update `packages/okf-mcp/README.md` to document the `move` tool.
- Update the root `CLAUDE.md` "Project status" okf-mcp summary to include
  `move`.
- The producer design's "Out of scope" note about move/rename is superseded by
  this spec (no edit required, but cross-referenced here).
