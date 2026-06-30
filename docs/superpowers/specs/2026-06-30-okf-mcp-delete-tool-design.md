# okf-mcp — `delete` Tool Design

**Date:** 2026-06-30
**Status:** Approved (brainstorming) — ready for implementation plan
**Depends on:** `okf-core` (link extraction/resolution, indexing, path APIs), `okf-mcp` producer server (§ patterns from `2026-06-29-okf-mcp-producer-design.md` and `2026-06-29-okf-mcp-move-tool-design.md`)

## 1. Motivation

The producer server can `add`, `patch`, and `move` concepts but cannot **remove**
one. Deleting a concept today means manual file surgery plus a stale bundle: the
directory's `_index.md` still lists the gone concept, and every markdown link
that pointed at it silently dangles.

This spec adds a **`delete`** tool that removes a concept by id, drops it from
the index (via re-index), records the change in `_log.md`, and — crucially —
**cleans up the inbound references** so the bundle stays internally consistent.
Because deletion is destructive and can ripple into other documents, the tool is
**safe by default**: it refuses to delete a concept that other concepts still
reference, returning the referrers, unless the caller passes `force=True`.

### Goals

- A `delete(concept_id, force=False, bundle_root=None)` MCP tool, backed by a
  framework-agnostic `operations.delete_concept`.
- **Safe by default** (`force=False`): if other concepts reference `concept_id`,
  delete nothing and return the referrers; if nothing references it, delete it.
- **Forced** (`force=True`): delete regardless, **unlinking** every inbound
  reference — a markdown link `[label](target.md)` becomes the plain text
  `label`, keeping prose readable.
- Regenerate indexes and append a `_log.md` entry, matching `add`/`patch`/`move`.
- Add one reusable link-*stripping* primitive to `okf-core` (the single home for
  "how OKF links resolve"), keeping okf-mcp free of duplicated resolution logic.

### Non-goals

- No multi-concept / recursive directory deletes (delete one concept per call).
- No removal of now-empty directories — left in place, consistent with `move`
  (which does not prune the source directory). They keep a regenerated
  `_index.md` and their `_log.md`.
- No rewriting of `_log.md` history (append-only) or hand-editing of `_index.md`
  (regenerated).
- No rewriting of external `scheme://` links or non-markdown link targets.
- No bundle-wide conformance validation inside the tool (re-index only, as with
  the other write tools). Dangling links are conformant anyway (`LNK-02`); the
  unlinking is an authoring convenience, not a conformance fix.
- No undo. Deletion is irreversible (recover via version control if needed).

## 2. Architecture

Follows the existing **thin-server-over-operations** split:

```
packages/okf-core/src/okf_core/
└── links.py                    # + strip_links() pure primitive; re-exported from __init__
packages/okf-mcp/src/okf_mcp/
├── operations.py               # + delete_concept() orchestrator
└── server.py                   # + @mcp.tool() delete() thin wrapper
```

- **`okf_core.strip_links`** (new pure function) removes from a document body
  every markdown link that resolves to one of a set of target concept ids,
  leaving the link's label text in place. No I/O. Unit-tested directly.
  Re-exported from `okf_core/__init__.py` and listed in `__all__`, alongside the
  existing `rewrite_links`.
- **`operations.delete_concept`** orchestrates: validate id, read the source for
  its label, collect inbound referrers (one pass), branch on `force`, then either
  abort with the referrers or unlink them, delete the file, regenerate indexes,
  append a log entry, and return a summary.
- **`server.delete`** is a thin `@mcp.tool()` wrapper that resolves the bundle
  root and delegates, like the other tools.

## 3. Tool: `delete`

The identifier is a **concept ID** — the bundle-relative path with no `.md`
suffix (e.g. `tables/orders`). It is validated via the existing
`operations._concept_path`, so invalid segments and reserved final segments
(`_index`/`_log`, RSV-01) are rejected.

### 3.1 Parameters

- `concept_id: str` — the concept to delete (e.g. `tables/orders`).
- `force: bool = False` — when `False`, refuse to delete a referenced concept and
  report the referrers; when `True`, delete and unlink inbound references.
- `bundle_root: str | None = None` — override (§ producer-design §3).

### 3.2 Behavior

1. Resolve the bundle root; compute the concept path via `_concept_path`
   (validates the id; rejects reserved/invalid segments).
2. **Error if the path does not exist** (`concept not found: <id>`).
3. Parse the document with `OKFDocument.parse` to read its `title` (the log
   label; falls back to the last id segment).
4. **Collect inbound referrers** in a single pass over the bundle
   (`Bundle.load`): for every *other* concept, compute
   `strip_links(body, its_dir, bundle_root, {deleted_id})`; if the result differs
   from the original body, the concept references `deleted_id` — remember the
   tuple `(concept, path, new_body)`. (The to-be-deleted concept is skipped by id;
   resolution is pure path math and does not require the file to still exist, so
   collecting *before* unlinking is safe.)
5. **Branch on referrers and `force`:**
   - **Referrers exist and `force=False`** → abort. Delete nothing, write nothing.
     Return the *blocked* shape (§6).
   - **Otherwise** (no referrers, or `force=True`) → proceed:
     1. For each remembered referrer, write back its unlinked `new_body` (via
        `OKFDocument(frontmatter=<unchanged>, body=new_body).serialize()`).
        This is silent — **no `timestamp` bump and no per-file log entry** —
        exactly like `move`'s inbound relink. Collect the ids into `unlinked`
        (sorted). When there are no referrers, `unlinked` is `[]`.
     2. `path.unlink()` — remove the concept file.
     3. Append a **Deletion** entry to the concept's directory `_log.md` (§5).
     4. `regenerate_indexes(bundle_root)` — drops the concept from its directory
        `_index.md` and refreshes any directory whose links were rewritten.
     5. Return the *deleted* shape (§6).

`force` only matters when referrers exist; deleting an unreferenced concept
behaves identically for `force=False` and `force=True`.

## 4. Link stripping (`okf_core.strip_links`)

The core primitive. Signature:

```python
def strip_links(
    body: str,
    doc_dir: Path,
    bundle_root: Path,
    target_ids: set[str],
) -> str
```

Remove from `body` every markdown link whose target resolves to a concept id in
`target_ids`, replacing the whole `[label](target.md#anchor)` span with just its
`label` text. Returns the modified body (the original string when nothing
applies — equality, not identity).

It reuses the **exact resolution rules** of `okf_core.extract_links` /
`rewrite_links` via the existing `_resolve_target_id`:

- Relative targets resolve against `doc_dir`; absolute targets (`/…`) resolve
  against `bundle_root`; `scheme://` targets are skipped untouched.
- Targets that escape the bundle root are left untouched.

Because the label must be removed along with the link, `strip_links` needs a
**full-link regex** that captures the label too — the existing `_LINK_RE` only
captures the `](target.md)` half (sufficient for `rewrite_links`, which keeps the
label). Add a sibling pattern, kept in sync with `_LINK_RE`:

```python
_FULL_LINK_RE = re.compile(
    r"\[(?P<label>[^\]]*)\]\((?P<target>[^)\s]+\.md)(?P<anchor>#[A-Za-z0-9_\-]*)?\)"
)
```

For each matched link:

1. Resolve `target` to a concept id with `_resolve_target_id(target, doc_dir, bundle_root)`.
2. If the resolved id is `None` (external / out-of-bundle) or **not** in
   `target_ids`, return the match verbatim.
3. Otherwise return the captured `label` only — dropping the `[`, `]`, `(target)`,
   and any `#anchor`.

Only the link span is altered; surrounding text is preserved verbatim. Empty
labels (`[](target.md)`) collapse to an empty string, which is acceptable and
rare.

## 5. Log appending

Reuses the existing `_append_log` machinery (newest-first `## YYYY-MM-DD` groups,
LOG-01/LOG-02). A single **Deletion** entry is appended to the deleted concept's
directory `_log.md`:

```
* **Deletion**: Removed `<label>`.
```

`<label>` is the concept's `title` if present, else the last id segment. The
label is rendered in **backticks, not as a markdown link** — the file is gone, so
a `[label](file.md)` entry would itself be a dangling link (precisely what this
tool removes elsewhere). A small dedicated helper is used (rather than the
existing `_append_log_for`, which renders a link).

Inbound-link unlinks do **not** add log entries (they would be noisy and are
implied by the deletion), matching `move`'s treatment of relinks. The *blocked*
branch writes no log entry (nothing changed).

## 6. Return value

Two shapes, distinguished by `action`. All paths are bundle-relative POSIX
strings.

**Deleted** (no referrers, or `force=True`):

```json
{
  "concept_id": "tables/orders",
  "path": "tables/orders.md",
  "action": "deleted",
  "unlinked": ["docs/overview", "metrics/revenue"],
  "log": "tables/_log.md",
  "indexes": ["_index.md", "tables/_index.md", "docs/_index.md"]
}
```

- `unlinked` — bundle-relative ids of **other** concepts whose bodies were
  rewritten to drop the link. Empty list when none.
- `log` — bundle-relative path of the `_log.md` written.
- `indexes` — bundle-relative paths returned by `regenerate_indexes`.

**Blocked** (`force=False` and referrers exist):

```json
{
  "concept_id": "tables/orders",
  "action": "blocked",
  "referenced_by": ["docs/overview", "metrics/revenue"]
}
```

- `referenced_by` — bundle-relative ids of concepts that link to `concept_id`
  (sorted). Nothing was deleted or modified.

## 7. Error handling

Preconditions raise `ValueError` with actionable messages (FastMCP surfaces them
as tool errors):

- bundle root unresolved or not a directory (shared resolver);
- `concept_id` invalid or a reserved final segment (`_index`/`_log`);
- concept does not exist.

A referenced concept under `force=False` is **not** an error — it returns the
*blocked* shape so the caller can decide. I/O and YAML errors propagate as-is
(`OKFDocumentError` / `OSError`).

## 8. Testing (TDD)

**`okf-core` — `strip_links` unit tests** (against `tmp_path` / synthetic bodies):

- a relative link to a target id is replaced by its bare label;
- an absolute (`/…`) link to a target id is stripped to its label;
- a link with a `#anchor` is stripped (label kept, anchor dropped);
- multiple targets in `target_ids`: only matching links are stripped, others kept;
- a link whose id is **not** in `target_ids` is untouched;
- external `scheme://` and out-of-bundle (`../outside.md`) links are untouched;
- surrounding prose is preserved; the no-match case returns an equal body.

**`okf-mcp` — `delete_concept` unit tests** (against `tmp_path` bundles):

- unreferenced concept, `force=False`: file removed, dropped from `_index.md`,
  Deletion entry in `_log.md`, indexes regenerated, `unlinked == []`;
- referenced concept, `force=False`: nothing deleted/modified; returns
  `action="blocked"` with the sorted `referenced_by`;
- referenced concept, `force=True`: file removed; each referrer's
  `[label](target.md)` becomes `label`; referrers listed in `unlinked`; the
  referenced files no longer contain the link;
- anchored and absolute inbound links are both unlinked under `force=True`;
- a referrer linking the deleted concept twice has both occurrences stripped;
- the deletion `_log.md` entry uses the backticked label (no markdown link);
- errors: missing concept, reserved/invalid id;
- `force=True` on an unreferenced concept behaves like `force=False` (deletes,
  `unlinked == []`).

**`test_server.py`** smoke: the `delete` tool is registered alongside the existing
seven (`add`, `patch`, `get`, `list`, `read_index`, `move`, `reindex`).

## 9. Housekeeping

- Export `strip_links` from `okf_core/__init__.py` (add to `__all__`).
- Update `packages/okf-mcp/README.md` to document the `delete` tool.
- Update the root `CLAUDE.md` "Project status" okf-mcp summary to include
  `delete`.
- The producer design's and move design's "Non-goals" notes about there being no
  delete tool are superseded by this spec (no edit required; cross-referenced
  here).
