# okf-mcp `delete` Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe-by-default `delete` MCP tool that removes an OKF concept, drops it from the index, and either blocks on inbound references or (with `force`) unlinks them.

**Architecture:** A new pure `strip_links` primitive in `okf-core` removes markdown links to a set of target concept ids while keeping the link label. A new `operations.delete_concept` orchestrator in `okf-mcp` collects inbound referrers in one pass, branches on `force` (abort-and-report vs. unlink-and-delete), removes the file, appends a `_log.md` Deletion entry, and regenerates indexes. A thin `@mcp.tool() delete` wrapper exposes it.

**Tech Stack:** Python 3.12, uv workspace, pytest. `okf-core` (pure stdlib + PyYAML), `okf-mcp` (FastMCP / `mcp` SDK, depends on `okf-core`).

## Global Constraints

- `okf-core`'s **only** runtime dependency is PyYAML — `strip_links` must be pure stdlib (`re`, `os`, `pathlib`). Do **not** add dependencies.
- Target Python 3.12; every module starts with `from __future__ import annotations`.
- Reserved final id segments are `_index` / `_log`; rejection is already handled by `operations._concept_path` — reuse it, don't reimplement.
- Concept ids are bundle-relative POSIX paths without `.md` (e.g. `tables/orders`); all returned paths are bundle-relative POSIX strings.
- Run tests with `uv run pytest` from the workspace root.
- Conventional commits scoped per package (`feat(okf-core): …`, `feat(okf-mcp): …`, `docs: …`); end every commit message with the `Co-Authored-By` trailer shown in the commit steps.
- Spec: `docs/superpowers/specs/2026-06-30-okf-mcp-delete-tool-design.md`.

## File Structure

- `packages/okf-core/src/okf_core/links.py` — **modify**: add `_FULL_LINK_RE` and `strip_links()`.
- `packages/okf-core/src/okf_core/__init__.py` — **modify**: import & export `strip_links`.
- `packages/okf-core/tests/test_links.py` — **modify**: add `strip_links` unit tests.
- `packages/okf-mcp/src/okf_mcp/operations.py` — **modify**: import `strip_links`; add `_append_log_deletion()` and `delete_concept()`.
- `packages/okf-mcp/tests/test_operations.py` — **modify**: add `delete_concept` tests.
- `packages/okf-mcp/src/okf_mcp/server.py` — **modify**: add `@mcp.tool() delete()`.
- `packages/okf-mcp/tests/test_server.py` — **modify**: include `delete` in the registered-tools smoke set.
- `packages/okf-mcp/README.md` — **modify**: document the `delete` tool.
- `CLAUDE.md` — **modify**: add `delete` to the okf-mcp summary.

## Known limitation (in scope to document, not fix)

Deleting the **last** concept in a *non-root* directory leaves a stale `_index.md`: `regenerate_indexes` only rewrites a directory's index when it still contains at least one concept (`packages/okf-core/src/okf_core/index.py:101-102`), so an emptied directory's old index is neither rewritten nor removed. This is a pre-existing core behavior that `move` shares. It is **out of scope** for this plan (the spec leaves empty directories in place). The common case — deleting a concept that has siblings — correctly removes it from the regenerated index, and Task 2 tests that case.

---

### Task 1: `strip_links` primitive in okf-core

**Files:**
- Modify: `packages/okf-core/src/okf_core/links.py`
- Modify: `packages/okf-core/src/okf_core/__init__.py`
- Test: `packages/okf-core/tests/test_links.py`

**Interfaces:**
- Consumes: existing `_resolve_target_id(target, doc_dir, bundle_root)` and `_LINK_RE` in `links.py`.
- Produces: `strip_links(body: str, doc_dir: Path, bundle_root: Path, target_ids: set[str]) -> str` — exported from `okf_core`. Removes every markdown link whose resolved target id is in `target_ids`, replacing the full `[label](target.md#anchor)` span with bare `label`; returns an equal body when nothing matches.

- [ ] **Step 1: Write the failing tests**

Edit the import on line 1 of `packages/okf-core/tests/test_links.py` from `from okf_core import rewrite_links` to:

```python
from okf_core import rewrite_links, strip_links
```

Append these tests to `packages/okf-core/tests/test_links.py`:

```python
def test_strip_relative_link_keeps_label(tmp_path):
    out = strip_links("see [Orders](orders.md) now", tmp_path, tmp_path, {"orders"})
    assert out == "see Orders now"


def test_strip_absolute_link_keeps_label(tmp_path):
    out = strip_links(
        "[Orders](/tables/orders.md)", tmp_path, tmp_path, {"tables/orders"}
    )
    assert out == "Orders"


def test_strip_drops_anchor(tmp_path):
    out = strip_links("[Orders](orders.md#schema)", tmp_path, tmp_path, {"orders"})
    assert out == "Orders"


def test_strip_only_targets_in_set(tmp_path):
    body = "[O](orders.md) and [C](customers.md)"
    out = strip_links(body, tmp_path, tmp_path, {"orders"})
    assert out == "O and [C](customers.md)"


def test_strip_id_not_in_set_untouched(tmp_path):
    body = "[C](customers.md)"
    assert strip_links(body, tmp_path, tmp_path, {"orders"}) == body


def test_strip_external_and_out_of_bundle_untouched(tmp_path):
    body = "[x](https://e.com/page.md) [y](../outside.md)"
    assert strip_links(body, tmp_path, tmp_path, {"orders"}) == body


def test_strip_multiple_occurrences(tmp_path):
    body = "[O](orders.md) ... [Orders again](orders.md#x)"
    out = strip_links(body, tmp_path, tmp_path, {"orders"})
    assert out == "O ... Orders again"


def test_strip_from_subdir_resolves_parent_target(tmp_path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    out = strip_links(
        "[o](../tables/orders.md)", metrics, tmp_path, {"tables/orders"}
    )
    assert out == "o"


def test_strip_noop_returns_equal_body(tmp_path):
    body = "no md links [text](http://x) here"
    assert strip_links(body, tmp_path, tmp_path, {"orders"}) == body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-core/tests/test_links.py -k strip -v`
Expected: collection/import error or FAIL — `ImportError: cannot import name 'strip_links'`.

- [ ] **Step 3: Implement `strip_links`**

Append to `packages/okf-core/src/okf_core/links.py` (after `rewrite_links`):

```python
# Mirrors _LINK_RE but also captures the [label] so the whole link can be
# replaced by its label. Keep the target/anchor groups in sync with _LINK_RE.
_FULL_LINK_RE = re.compile(
    r"\[(?P<label>[^\]]*)\]\((?P<target>[^)\s]+\.md)(?P<anchor>#[A-Za-z0-9_\-]*)?\)"
)


def strip_links(
    body: str,
    doc_dir: Path,
    bundle_root: Path,
    target_ids: set[str],
) -> str:
    """Remove markdown links pointing at any id in ``target_ids``, keeping text.

    Resolves each ``[label](target.md)`` link in ``body`` (against ``doc_dir``
    and ``bundle_root``, using the same rules as ``extract_links`` /
    ``rewrite_links``). When the resolved target concept id is in
    ``target_ids``, the entire link -- brackets, target, and any ``#anchor`` --
    is replaced by its bare ``label`` text. External (``scheme://``) and
    out-of-bundle links, and links whose target is not in ``target_ids``, are
    left untouched. Returns an equal body when nothing applies.
    """
    bundle_root = bundle_root.resolve()
    doc_dir = doc_dir.resolve()

    def _sub(m: re.Match[str]) -> str:
        target_id = _resolve_target_id(m.group("target"), doc_dir, bundle_root)
        if target_id is None or target_id not in target_ids:
            return m.group(0)
        return m.group("label")

    return _FULL_LINK_RE.sub(_sub, body)
```

- [ ] **Step 4: Export `strip_links` from the package**

In `packages/okf-core/src/okf_core/__init__.py`, change the links import line from:

```python
from okf_core.links import rewrite_links
```

to:

```python
from okf_core.links import rewrite_links, strip_links
```

Then add `"strip_links",` to `__all__` immediately after the `"rewrite_links",` entry.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/okf-core/tests/test_links.py -v`
Expected: PASS (all existing `rewrite_links` tests plus the 9 new `strip_links` tests).

- [ ] **Step 6: Commit**

```bash
git add packages/okf-core/src/okf_core/links.py \
        packages/okf-core/src/okf_core/__init__.py \
        packages/okf-core/tests/test_links.py
git commit -m "feat(okf-core): add strip_links to unlink references by target id" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `delete_concept` operation in okf-mcp

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: `strip_links` (Task 1); existing `_concept_path`, `_append_log`, `_today_iso`, `regenerate_indexes`, `Bundle.load`, `OKFDocument`, `concept_id_to_path`, `parse_concept_id`, `LOG_FILENAME`.
- Produces:
  - `delete_concept(bundle_root: Path, concept_id: str, force: bool = False) -> dict`. Returns the **blocked** shape `{"concept_id", "action": "blocked", "referenced_by": [sorted ids]}` when referrers exist and `not force`; otherwise the **deleted** shape `{"concept_id", "path", "action": "deleted", "unlinked": [sorted ids], "log", "indexes": [...]}`.
  - `_append_log_deletion(concept_path: Path, label: str) -> Path` helper.

- [ ] **Step 1: Write the failing tests**

Append to `packages/okf-mcp/tests/test_operations.py` (the file already imports `pytest`, `OKFDocument`, and `operations`):

```python
def test_delete_unreferenced_removes_file_and_index(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table", "title": "Customers"}, ""
    )
    res = operations.delete_concept(tmp_path, "tables/orders")
    assert not (tmp_path / "tables" / "orders.md").exists()
    assert res["action"] == "deleted"
    assert res["concept_id"] == "tables/orders"
    assert res["unlinked"] == []
    idx = (tmp_path / "tables" / "_index.md").read_text()
    assert "Customers" in idx
    assert "orders.md" not in idx


def test_delete_blocked_when_referenced(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table"}, "see [O](orders.md)"
    )
    res = operations.delete_concept(tmp_path, "tables/orders")
    assert res["action"] == "blocked"
    assert res["referenced_by"] == ["tables/customers"]
    assert (tmp_path / "tables" / "orders.md").exists()
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert "(orders.md)" in cust.body  # untouched


def test_delete_force_unlinks_relative_reference(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table"}, "see [O](orders.md) now"
    )
    res = operations.delete_concept(tmp_path, "tables/orders", force=True)
    assert not (tmp_path / "tables" / "orders.md").exists()
    assert res["unlinked"] == ["tables/customers"]
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert "see O now" in cust.body
    assert "(orders.md)" not in cust.body


def test_delete_force_unlinks_absolute_reference(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "metrics/rev", {"type": "Metric"}, "[O](/tables/orders.md)"
    )
    operations.delete_concept(tmp_path, "tables/orders", force=True)
    rev = OKFDocument.parse((tmp_path / "metrics" / "rev.md").read_text())
    assert rev.body.strip() == "O"


def test_delete_force_unlinks_anchored_reference(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table"}, "[O](orders.md#schema)"
    )
    operations.delete_concept(tmp_path, "tables/orders", force=True)
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert cust.body.strip() == "O"


def test_delete_logs_deletion_entry(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    res = operations.delete_concept(tmp_path, "tables/orders")
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert "* **Deletion**: Removed `Orders`." in log
    assert "(orders.md)" not in log  # backticked label, not a markdown link
    assert res["log"] == "tables/_log.md"


def test_delete_force_unreferenced_behaves_like_default(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    res = operations.delete_concept(tmp_path, "tables/orders", force=True)
    assert res["action"] == "deleted"
    assert res["unlinked"] == []


def test_delete_missing_errors(tmp_path):
    with pytest.raises(ValueError):
        operations.delete_concept(tmp_path, "nope")


def test_delete_rejects_reserved(tmp_path):
    with pytest.raises(ValueError):
        operations.delete_concept(tmp_path, "tables/_index")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k delete -v`
Expected: FAIL — `AttributeError: module 'okf_mcp.operations' has no attribute 'delete_concept'`.

- [ ] **Step 3: Add `strip_links` to the okf-core import**

In `packages/okf-mcp/src/okf_mcp/operations.py`, add `strip_links,` to the `from okf_core import (...)` block (alphabetically it sits right after `rewrite_links,`):

```python
    rewrite_links,
    strip_links,
)
```

- [ ] **Step 4: Implement `_append_log_deletion` and `delete_concept`**

Append to `packages/okf-mcp/src/okf_mcp/operations.py` (after `move_concept`):

```python
def _append_log_deletion(concept_path: Path, label: str) -> Path:
    """Append a Deletion entry to the directory's log.

    The label is backticked (not a markdown link) because the file is gone --
    a link entry would itself be a dangling link.
    """
    log_path = concept_path.parent / LOG_FILENAME
    _append_log(log_path, f"* **Deletion**: Removed `{label}`.", _today_iso())
    return log_path


def delete_concept(
    bundle_root: Path, concept_id: str, force: bool = False
) -> dict:
    """Delete a concept; safe by default, ``force`` unlinks inbound references.

    Collects every other concept whose body links to ``concept_id``. When such
    referrers exist and ``force`` is false, deletes nothing and returns the
    referrers (``action="blocked"``). Otherwise unlinks each inbound reference
    (``[label](target.md)`` -> ``label``), removes the file, appends a Deletion
    entry to the directory ``_log.md``, regenerates indexes, and returns a
    summary (``action="deleted"``). Fails if the concept does not exist or the
    id collides with a reserved file name.
    """
    path = _concept_path(bundle_root, concept_id)
    if not path.exists():
        raise ValueError(f"concept not found: {concept_id}")
    deleted_id = "/".join(parse_concept_id(concept_id))
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    label = str(doc.frontmatter.get("title") or path.stem)

    # One pass: find every other concept whose body links to the deleted id.
    referrers: list[tuple[str, Path, dict, str]] = []  # (id, path, fm, new_body)
    for c in Bundle.load(bundle_root).concepts:
        if c.id == deleted_id:
            continue
        c_path = concept_id_to_path(bundle_root, parse_concept_id(c.id))
        new_body = strip_links(c.body, c_path.parent, bundle_root, {deleted_id})
        if new_body != c.body:
            referrers.append((c.id, c_path, c.document.frontmatter, new_body))

    if referrers and not force:
        return {
            "concept_id": deleted_id,
            "action": "blocked",
            "referenced_by": sorted(rid for rid, _, _, _ in referrers),
        }

    unlinked: list[str] = []
    for rid, c_path, fm, new_body in referrers:
        c_path.write_text(
            OKFDocument(frontmatter=fm, body=new_body).serialize(),
            encoding="utf-8",
        )
        unlinked.append(rid)

    path.unlink()
    log_path = _append_log_deletion(path, label)
    indexes = regenerate_indexes(bundle_root)
    return {
        "concept_id": deleted_id,
        "path": path.relative_to(bundle_root).as_posix(),
        "action": "deleted",
        "unlinked": sorted(unlinked),
        "log": log_path.relative_to(bundle_root).as_posix(),
        "indexes": [Path(p).relative_to(bundle_root).as_posix() for p in indexes],
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k delete -v`
Expected: PASS (all 9 delete tests).

- [ ] **Step 6: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py \
        packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add delete_concept operation (safe-by-default + force)" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `delete` MCP tool in server

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/server.py`
- Test: `packages/okf-mcp/tests/test_server.py`

**Interfaces:**
- Consumes: `operations.delete_concept` (Task 2); existing `_root(bundle_root)` helper and `mcp` app.
- Produces: an MCP tool named `delete` registered on the FastMCP app.

- [ ] **Step 1: Update the registered-tools smoke test (failing)**

In `packages/okf-mcp/tests/test_server.py`, change the assertion in `test_all_tools_registered` to include `delete`:

```python
    assert {
        "add", "patch", "get", "list", "read_index", "move", "reindex", "delete"
    } <= names
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/okf-mcp/tests/test_server.py::test_all_tools_registered -v`
Expected: FAIL — the set assertion fails because `delete` is not registered.

- [ ] **Step 3: Add the `delete` tool**

In `packages/okf-mcp/src/okf_mcp/server.py`, add this after the `move` tool (before `reindex` or `main`):

```python
@mcp.tool()
def delete(
    concept_id: str,
    force: bool = False,
    bundle_root: str | None = None,
) -> dict:
    """Delete an OKF concept document.

    Safe by default: if other concepts reference `concept_id`, deletes nothing
    and returns `action="blocked"` with `referenced_by` listing them. Pass
    `force=True` to delete anyway -- this unlinks every inbound reference
    (`[label](target.md)` becomes plain `label`), removes the file, regenerates
    indexes, and appends a Deletion entry to `_log.md`. Irreversible. Fails if
    the concept does not exist.
    """
    return operations.delete_concept(_root(bundle_root), concept_id, force)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/okf-mcp/tests/test_server.py -v`
Expected: PASS (both server tests).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/server.py \
        packages/okf-mcp/tests/test_server.py
git commit -m "feat(okf-mcp): expose delete tool" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Documentation

**Files:**
- Modify: `packages/okf-mcp/README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing (docs only).
- Produces: nothing code-facing.

- [ ] **Step 1: Document the tool in the README**

In `packages/okf-mcp/README.md`, add this bullet to the `## Tools` list immediately after the `move(...)` bullet (line 105):

```markdown
- `delete(concept_id, force=False, bundle_root?)` — delete a concept; safe by default (returns `action="blocked"` with `referenced_by` when other concepts link to it). `force=True` deletes anyway, unlinking inbound references (`[label](target.md)` → `label`), then regenerates indexes and logs a Deletion entry. Irreversible; fails if the concept does not exist.
```

Then update the two tool-list recitations so they include `delete`:

- Line 86 (`tools/list` expectation): change `add, patch, get, list, read_index, move, reindex` to `add, patch, get, list, read_index, move, reindex, delete`.
- Line 108 (write-tools note): change `Every write tool (`add`/`patch`/`move`)` to `Every write tool (`add`/`patch`/`move`/`delete`)`.

- [ ] **Step 2: Update the okf-mcp summary in CLAUDE.md**

In `CLAUDE.md`, replace the okf-mcp tool sentence (lines 21-23) so `delete` is listed:

```markdown
plus `pydantic-settings`) for authoring bundles: tools to `add`, `patch`,
`move`, `delete`, `get`, and `list` concepts, `read_index` (progressive
disclosure), and `reindex` (regenerate all `_index.md` to repair drift). Write
tools re-index and append a directory-scoped `_log.md` entry after each write.
```

- [ ] **Step 3: Verify the full suite still passes**

Run: `uv run pytest`
Expected: PASS (entire workspace suite, no regressions).

- [ ] **Step 4: Commit**

```bash
git add packages/okf-mcp/README.md CLAUDE.md
git commit -m "docs(okf-mcp): document the delete tool" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
