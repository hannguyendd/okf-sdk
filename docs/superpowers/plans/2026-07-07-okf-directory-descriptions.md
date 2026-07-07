# OKF Directory Descriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a producer author a one-line **directory description** — a statement of a directory's _purpose_ — stored in that directory's own `_index.md` frontmatter. The index regenerator preserves it across rewrites and lifts it into the parent index's caption; when absent it falls back to a synthesized contents summary. A new `describe` MCP tool sets and clears it.

**Architecture:** `okf-core`'s `regenerate_indexes` changes from _overwrite_ to _read-preserve-rewrite_: before rewriting each `_index.md` it reads the existing frontmatter, keeps an allowlist (`description` at any level, `okf_version` at the bundle root), and re-emits it above the generated body. The parent caption for a subdirectory becomes **authored → synthesized** (the old single-child reuse shortcut is dropped). `okf-core`'s validator relaxes `IDX-01` to permit that same allowlist. In `okf-mcp`, a new `operations.describe_directory` writes/clears the `description` key, reindexes, and appends an `Update` log entry; a thin `@mcp.tool() describe` wrapper exposes it.

**Tech Stack:** Python 3.12, uv workspace, pytest. `okf-core` (pure stdlib + PyYAML), `okf-mcp` (FastMCP / `mcp` SDK, `pydantic-settings`, depends on `okf-core`).

## Design source

The design was settled in a grilling session and recorded in:

- ADR: `docs/adr/0001-directory-description-in-index-frontmatter.md` — storage decision, rejected alternatives (`_dir.md`, body preamble), and the `IDX-01`/`VER-01` relaxation.
- Glossary: `CONTEXT.md` — `Directory description`, `Index`, `Synthesized description`.

Resolved decisions this plan implements:

| #   | Decision                                                                                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Authored description coexists with synthesis; authored wins, synthesis is the fallback.                                               |
| 2   | Term **directory description** = one-line statement of _purpose_, not a contents roll-up.                                             |
| 3   | Stored as a `description` key in the directory's own `_index.md` frontmatter.                                                         |
| 4   | Surfaced in both the parent caption and the child's frontmatter.                                                                      |
| 5   | Tight allowlist: `_index.md` frontmatter = `description` (any level) + `okf_version` (root only); `description` is `SHOULD`.          |
| 6   | New producer tool `describe(dir, description)` — writes frontmatter, reindexes, logs an `Update`, errors if `dir` has no `_index.md`. |
| 7   | Fallback chain **authored → synthesize**; single-child reuse shortcut dropped.                                                        |
| 8   | Empty `description` clears it (reverts to synthesis).                                                                                 |
| 9   | Folded into the OKF v0.1 draft — no version bump.                                                                                     |

## Global Constraints

- `okf-core`'s **only** runtime dependency is PyYAML — no new dependencies. Reuse `OKFDocument.parse`/`.serialize` for frontmatter round-tripping (`OKFDocument` is already imported in `index.py`).
- Target Python 3.12; every module starts with `from __future__ import annotations`.
- `describe` never creates a directory or bootstraps an index from nothing: directories only exist once populated, so `describe` **requires** an existing `_index.md` and errors otherwise.
- The allowlist is enforced on regeneration too: `regenerate_indexes` drops any `_index.md` frontmatter key outside `{description, okf_version}` (self-healing).
- An undescribed directory's `_index.md` stays frontmatter-free (byte-for-byte as today) so existing bundles are untouched until `describe` is used.
- Concept ids / dirs are bundle-relative POSIX paths; returned paths are bundle-relative POSIX strings.
- TDD: write the failing test, watch it fail, implement minimally, watch it pass, commit. Run tests with `uv run pytest` from the workspace root.
- Test files must have unique basenames across the workspace.
- Conventional commits scoped per package (`feat(okf-core): …`, `feat(okf-mcp): …`, `docs: …`); end every commit message with the trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File Structure

- `packages/okf-core/src/okf_core/index.py` — **modify**: add `_read_index_frontmatter`; make `regenerate_indexes` preserve allowlisted frontmatter and use the authored→synthesize precedence.
- `packages/okf-core/tests/test_index.py` — **modify**: preservation, precedence, drop-of-shortcut, and allowlist-pruning tests.
- `packages/okf-core/src/okf_core/validate.py` — **modify**: relax `_check_index` to the allowlist.
- `packages/okf-core/tests/test_validate.py` — **modify**: `IDX-01` allowlist tests.
- `packages/okf-mcp/src/okf_mcp/operations.py` — **modify**: add `_describe_log` and `describe_directory`.
- `packages/okf-mcp/tests/test_operations.py` — **modify**: `describe_directory` tests.
- `packages/okf-mcp/src/okf_mcp/server.py` — **modify**: add `@mcp.tool() describe`.
- `packages/okf-mcp/tests/test_server.py` — **modify**: include `describe` in the registered-tools smoke set.
- `packages/okf-core/SPEC.md` — **modify**: §6 permits an authored `description` in `_index.md` frontmatter.
- `packages/okf-core/CONFORMANCE.md` — **modify**: `IDX-01` allowlist, `VER-01` note, §5 checklist wording.
- `packages/okf-mcp/README.md` — **modify**: document `describe`.
- `openwiki/packages/okf-core.md`, `openwiki/packages/okf-mcp.md` — **modify**: note directory descriptions / the `describe` tool.
- `CLAUDE.md` — **modify**: add `describe` to the okf-mcp summary.

---

### Task 1: `regenerate_indexes` preserves authored descriptions (okf-core)

**Files:**

- Modify: `packages/okf-core/src/okf_core/index.py`
- Test: `packages/okf-core/tests/test_index.py`

**Interfaces:**

- Add `_read_index_frontmatter(index_path: Path) -> dict` — returns the existing `_index.md` frontmatter mapping, or `{}` when the file is absent/frontmatter-free/unparseable.
- `regenerate_indexes(bundle_root, *, synthesize=fallback_synthesizer) -> list[Path]` — unchanged signature. New behavior: preserves `description` (any level) and `okf_version` (root only) across regeneration; a subdirectory's caption in its parent is its **authored** description when present, else `synthesize(...)`; the single-child reuse shortcut is removed.

- [ ] **Step 1: Write the failing tests**

Append to `packages/okf-core/tests/test_index.py`:

```python
def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_authored_description_preserved_across_reindex(tmp_path):
    _write(tmp_path / "tables" / "orders.md", "---\ntype: Table\ntitle: Orders\n---\n\nx\n")
    regenerate_indexes(tmp_path)  # creates tables/_index.md (no frontmatter)
    idx = tmp_path / "tables" / "_index.md"
    idx.write_text("---\ndescription: Sales tables.\n---\n\n" + idx.read_text(), encoding="utf-8")

    regenerate_indexes(tmp_path)

    from okf_core import OKFDocument
    fm = OKFDocument.parse((tmp_path / "tables" / "_index.md").read_text()).frontmatter
    assert fm == {"description": "Sales tables."}


def test_authored_description_lifted_into_parent_caption(tmp_path):
    _write(tmp_path / "tables" / "orders.md", "---\ntype: Table\ntitle: Orders\n---\n\nx\n")
    regenerate_indexes(tmp_path)
    idx = tmp_path / "tables" / "_index.md"
    idx.write_text("---\ndescription: Sales tables.\n---\n\n" + idx.read_text(), encoding="utf-8")

    regenerate_indexes(tmp_path)

    root = (tmp_path / "_index.md").read_text()
    assert "[tables](tables/_index.md) - Sales tables." in root


def test_single_child_shortcut_dropped_synthesizes_instead(tmp_path):
    _write(
        tmp_path / "solo" / "only.md",
        "---\ntype: Doc\ntitle: Only\ndescription: The only child.\n---\n\nx\n",
    )
    regenerate_indexes(tmp_path)
    root = (tmp_path / "_index.md").read_text()
    # Old behavior reused "The only child."; new behavior synthesizes a summary.
    assert "The only child." not in root
    assert "Contains 1 entries: Only." in root


def test_root_okf_version_preserved(tmp_path):
    _write(tmp_path / "a.md", "---\ntype: Doc\ntitle: A\n---\n\nx\n")
    regenerate_indexes(tmp_path)
    root_idx = tmp_path / "_index.md"
    root_idx.write_text('---\nokf_version: "0.1"\n---\n\n' + root_idx.read_text(), encoding="utf-8")

    regenerate_indexes(tmp_path)

    from okf_core import OKFDocument
    fm = OKFDocument.parse((tmp_path / "_index.md").read_text()).frontmatter
    assert fm == {"okf_version": "0.1"}


def test_non_allowlisted_index_frontmatter_pruned(tmp_path):
    _write(tmp_path / "d" / "c.md", "---\ntype: Doc\ntitle: C\n---\n\nx\n")
    regenerate_indexes(tmp_path)
    idx = tmp_path / "d" / "_index.md"
    idx.write_text(
        "---\ndescription: Keep me.\nbogus: drop me\n---\n\n" + idx.read_text(),
        encoding="utf-8",
    )

    regenerate_indexes(tmp_path)

    from okf_core import OKFDocument
    fm = OKFDocument.parse((tmp_path / "d" / "_index.md").read_text()).frontmatter
    assert fm == {"description": "Keep me."}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-core/tests/test_index.py -k "authored or shortcut or okf_version or pruned" -v`
Expected: FAIL (frontmatter stripped on reindex; caption still reuses the single child).

- [ ] **Step 3: Implement the preservation + precedence change**

In `packages/okf-core/src/okf_core/index.py`, add near the other helpers:

```python
def _read_index_frontmatter(index_path: Path) -> dict:
    """Return an existing ``_index.md``'s frontmatter, or ``{}`` if none/unparseable."""
    if not index_path.is_file():
        return {}
    try:
        return OKFDocument.parse(index_path.read_text(encoding="utf-8")).frontmatter or {}
    except Exception:
        return {}
```

Replace the body of the `for directory in directories:` loop in `regenerate_indexes` so it reads the existing frontmatter first, preserves the allowlist on write, and uses authored→synthesize precedence:

```python
    for directory in directories:
        index_path = directory / INDEX_FILENAME
        existing_fm = _read_index_frontmatter(index_path)
        authored = str(existing_fm.get("description") or "").strip()

        entries: list[tuple[str, str, str, str, list[str]]] = []
        for child in sorted(directory.iterdir()):
            if child.name in RESERVED_FILENAMES:
                continue
            if child.is_file() and child.suffix == ".md":
                doc = _load_doc(child)
                if doc is None:
                    continue
                fm = doc.frontmatter
                title = str(fm.get("title") or child.stem)
                desc = str(fm.get("description") or "")
                typ = str(fm.get("type") or "")
                entries.append((typ, title, child.name, desc, _doc_tags(fm)))
            elif child.is_dir():
                desc = dir_descriptions.get(child, "")
                entries.append(
                    ("Subdirectories", child.name, f"{child.name}/{INDEX_FILENAME}", desc, [])
                )

        if not entries:
            continue

        kept_fm: dict = {}
        if directory == bundle_root and existing_fm.get("okf_version"):
            kept_fm["okf_version"] = existing_fm["okf_version"]
        if authored:
            kept_fm["description"] = authored

        body = _build_index_text(entries)
        text = OKFDocument(frontmatter=kept_fm, body=body).serialize() if kept_fm else body
        index_path.write_text(text, encoding="utf-8")
        written.append(index_path)

        if directory == bundle_root:
            continue

        if authored:
            dir_descriptions[directory] = authored
        else:
            rel = str(directory.relative_to(bundle_root))
            pairs = [(title, desc) for _, title, _, desc, _ in entries]
            dir_descriptions[directory] = synthesize(rel, pairs)

    return written
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-core/tests/test_index.py -v`
Expected: PASS (new tests plus all existing index tests; update any existing test that asserted the old single-child-reuse caption).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-core/src/okf_core/index.py packages/okf-core/tests/test_index.py
git commit -m "feat(okf-core): preserve authored _index.md description across reindex" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Relax `IDX-01` in the validator (okf-core)

**Files:**

- Modify: `packages/okf-core/src/okf_core/validate.py`
- Test: `packages/okf-core/tests/test_validate.py`

**Interfaces:**

- `_check_index(rel, text, is_root)` now permits an allowlisted frontmatter: `{"description"}` for any `_index.md`, plus `{"okf_version"}` at the bundle root. Any other key (or malformed block) is an `IDX-01` violation.

- [ ] **Step 1: Write the failing tests**

Append to `packages/okf-core/tests/test_validate.py`:

```python
def test_idx01_allows_description_in_subdir_index(tmp_path):
    _write(tmp_path / "tables" / "orders.md", "---\ntype: Table\n---\n\nx\n")
    _write(tmp_path / "tables" / "_index.md", "---\ndescription: Sales tables.\n---\n\n# T\n\n* [O](orders.md)\n")
    assert [v.rule for v in validate_bundle(tmp_path) if v.rule == "IDX-01"] == []


def test_idx01_allows_description_and_okf_version_at_root(tmp_path):
    _write(tmp_path / "a.md", "---\ntype: Doc\n---\n\nx\n")
    _write(tmp_path / "_index.md", '---\nokf_version: "0.1"\ndescription: The bundle.\n---\n\n# A\n\n* [A](a.md)\n')
    assert [v.rule for v in validate_bundle(tmp_path) if v.rule == "IDX-01"] == []


def test_idx01_rejects_non_allowlisted_key(tmp_path):
    _write(tmp_path / "tables" / "orders.md", "---\ntype: Table\n---\n\nx\n")
    _write(tmp_path / "tables" / "_index.md", "---\nbogus: nope\n---\n\n# T\n\n* [O](orders.md)\n")
    assert any(v.rule == "IDX-01" for v in validate_bundle(tmp_path))


def test_idx01_rejects_okf_version_in_subdir(tmp_path):
    _write(tmp_path / "tables" / "orders.md", "---\ntype: Table\n---\n\nx\n")
    _write(tmp_path / "tables" / "_index.md", '---\nokf_version: "0.1"\n---\n\n# T\n\n* [O](orders.md)\n')
    assert any(v.rule == "IDX-01" for v in validate_bundle(tmp_path))
```

(If `_write` is not already a helper in this test module, add the same 3-line helper used in Task 1.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-core/tests/test_validate.py -k idx01 -v`
Expected: FAIL — a subdir `_index.md` with `description` currently violates `IDX-01`.

- [ ] **Step 3: Implement the allowlist**

In `packages/okf-core/src/okf_core/validate.py`, replace the `has_block` branch of `_check_index` with:

```python
    if has_block:
        status, fm = _split_frontmatter(text)
        allowed = {"description", "okf_version"} if is_root else {"description"}
        if status != "ok" or set(fm) - allowed:
            allowed_str = "', '".join(sorted(allowed))
            out.append(
                Violation(
                    "IDX-01",
                    rel,
                    f"{INDEX_FILENAME} frontmatter may declare only '{allowed_str}'",
                )
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-core/tests/test_validate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/okf-core/src/okf_core/validate.py packages/okf-core/tests/test_validate.py
git commit -m "feat(okf-core): relax IDX-01 to allow authored _index.md description" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `describe_directory` operation (okf-mcp)

**Files:**

- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**

- Consumes: existing `INDEX_FILENAME`, `LOG_FILENAME`, `OKFDocument`, `regenerate_indexes`, `_append_log`, `_now_utc`, `_utc_date`, `_utc_time`, `_rel_dir`.
- Produces: `describe_directory(bundle_root: Path, dir: str, description: str) -> dict`. Sets `description` in `dir/_index.md` frontmatter (clears it when `description` is empty/whitespace), reindexes, and appends an `Update` `_log.md` entry. Errors if `dir` escapes the root, is not a directory, or has no `_index.md`. Returns `{"dir", "action" ("described"|"cleared"), "description", "log", "indexes"}`.

- [ ] **Step 1: Write the failing tests**

Append to `packages/okf-mcp/tests/test_operations.py` (reuse the module's existing bundle fixture/helpers):

```python
def test_describe_sets_description_and_logs(tmp_path):
    add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "x")
    res = describe_directory(tmp_path, "tables", "Sales tables.")

    assert res["action"] == "described"
    assert res["description"] == "Sales tables."
    from okf_core import OKFDocument
    fm = OKFDocument.parse((tmp_path / "tables" / "_index.md").read_text()).frontmatter
    assert fm["description"] == "Sales tables."
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert "**Update**" in log and "description" in log.lower()


def test_describe_lifts_into_parent_caption(tmp_path):
    add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "x")
    describe_directory(tmp_path, "tables", "Sales tables.")
    assert "[tables](tables/_index.md) - Sales tables." in (tmp_path / "_index.md").read_text()


def test_describe_empty_clears(tmp_path):
    add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "x")
    describe_directory(tmp_path, "tables", "Sales tables.")
    res = describe_directory(tmp_path, "tables", "   ")

    assert res["action"] == "cleared"
    from okf_core import OKFDocument
    fm = OKFDocument.parse((tmp_path / "tables" / "_index.md").read_text()).frontmatter
    assert "description" not in fm


def test_describe_errors_without_index(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError):
        describe_directory(tmp_path, "empty", "nope")


def test_describe_rejects_escaping_dir(tmp_path):
    with pytest.raises(ValueError):
        describe_directory(tmp_path, "../outside", "nope")
```

Add `describe_directory` to the module's imports from `okf_mcp.operations`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k describe -v`
Expected: import/collection error — `describe_directory` does not exist yet.

- [ ] **Step 3: Implement `describe_directory`**

Append to `packages/okf-mcp/src/okf_mcp/operations.py`:

```python
def _log_describe(index_path: Path, cleared: bool) -> Path:
    log_path = index_path.parent / LOG_FILENAME
    dt = _now_utc()
    what = "Cleared" if cleared else "Set"
    _append_log(
        log_path,
        f"* **{_utc_time(dt)}** **Update**: {what} description for this directory.",
        _utc_date(dt),
    )
    return log_path


def describe_directory(bundle_root: Path, dir: str, description: str) -> dict:
    """Set or clear a directory's authored description in its ``_index.md`` frontmatter.

    An empty/whitespace ``description`` clears the key (reverting to the
    synthesized summary). Reindexes so the value reaches the parent's caption,
    and appends an Update entry to the directory's ``_log.md``. Fails if ``dir``
    escapes the bundle root, is not a directory, or has no ``_index.md``.
    """
    root = bundle_root.resolve()
    target = root if not dir else (root / dir).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"dir escapes the bundle root: {dir}")
    if not target.is_dir():
        raise ValueError(f"directory not found: {dir}")
    index_path = target / INDEX_FILENAME
    if not index_path.is_file():
        raise ValueError(f"directory has no {INDEX_FILENAME}: {dir}")

    doc = OKFDocument.parse(index_path.read_text(encoding="utf-8"))
    fm = dict(doc.frontmatter)
    desc = description.strip()
    cleared = not desc
    if cleared:
        fm.pop("description", None)
    else:
        fm["description"] = desc

    if fm:
        index_path.write_text(
            OKFDocument(frontmatter=fm, body=doc.body).serialize(), encoding="utf-8"
        )
    else:
        body = doc.body if doc.body.endswith("\n") else doc.body + "\n"
        index_path.write_text(body, encoding="utf-8")

    log_path = _log_describe(index_path, cleared)
    indexes = regenerate_indexes(root)
    return {
        "dir": _rel_dir(root, target),
        "action": "cleared" if cleared else "described",
        "description": None if cleared else desc,
        "log": log_path.relative_to(root).as_posix(),
        "indexes": [Path(p).relative_to(root).as_posix() for p in indexes],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add describe_directory operation" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `describe` MCP tool (okf-mcp)

**Files:**

- Modify: `packages/okf-mcp/src/okf_mcp/server.py`
- Test: `packages/okf-mcp/tests/test_server.py`

**Interfaces:**

- `@mcp.tool() describe(dir: str, description: str, bundle_root: str | None = None) -> dict` — delegates to `operations.describe_directory(_root(bundle_root), dir, description)`.

- [ ] **Step 1: Write the failing test**

In `packages/okf-mcp/tests/test_server.py`, add `describe` to the expected registered-tools set (match the existing smoke-test pattern), e.g.:

```python
def test_describe_tool_registered():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert "describe" in names
```

(Use whatever list-tools helper the existing tests already use.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_server.py -k describe -v`
Expected: FAIL — `describe` not registered.

- [ ] **Step 3: Implement the tool**

Add to `packages/okf-mcp/src/okf_mcp/server.py` (after `reindex`):

```python
@mcp.tool()
def describe(
    dir: str,
    description: str,
    bundle_root: str | None = None,
) -> dict:
    """Set or clear a directory's authored description.

    Writes `description` into the directory's `_index.md` frontmatter, regenerates
    indexes so it appears in the parent's caption, and appends an Update entry to
    that directory's `_log.md`. Pass an empty string to clear it (reverting to the
    synthesized contents summary). `dir` is a bundle-relative directory that must
    already have an `_index.md`.
    """
    return operations.describe_directory(_root(bundle_root), dir, description)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_server.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/server.py packages/okf-mcp/tests/test_server.py
git commit -m "feat(okf-mcp): expose describe tool for directory descriptions" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Documentation

**Files:**

- Modify: `packages/okf-core/SPEC.md`, `packages/okf-core/CONFORMANCE.md`, `packages/okf-mcp/README.md`, `openwiki/packages/okf-core.md`, `openwiki/packages/okf-mcp.md`, `CLAUDE.md`.

- [ ] **Step 1: SPEC.md §6 (Index Files)**

Note that an `_index.md` MAY carry a single frontmatter key, `description`, giving the directory's purpose; consumers surface it and producers lift it into the parent listing. Keep the "index files contain no [other] frontmatter" spirit — state the allowlist (`description` any level; `okf_version` root only).

- [ ] **Step 2: CONFORMANCE.md**

- Rewrite `IDX-01` to: _an `_index.md` frontmatter block, when present, declares only `description` (any level) and, at the bundle root, `okf_version`; any other key is a violation._
- Update the `VER-01` note (frontmatter is no longer "the only place" — cross-reference `IDX-01`).
- Add a `SHOULD` row (e.g. `IDX-04`): a directory _should_ carry an authored `description`.
- Update the §5 checklist wording for `IDX-01`.

- [ ] **Step 3: okf-mcp README + CLAUDE.md**

Document the `describe` tool (set/clear, reindex, log). Add `describe` to the tool list in `CLAUDE.md`'s okf-mcp summary.

- [ ] **Step 4: openwiki**

In `openwiki/packages/okf-core.md` note the authored-vs-synthesized directory description in `regenerate_indexes`; in `openwiki/packages/okf-mcp.md` add `describe` to the tool inventory.

- [ ] **Step 5: Full test sweep + commit**

Run: `uv run pytest`
Expected: PASS across the workspace.

```bash
git add packages/okf-core/SPEC.md packages/okf-core/CONFORMANCE.md \
        packages/okf-mcp/README.md openwiki/packages/okf-core.md \
        openwiki/packages/okf-mcp.md CLAUDE.md
git commit -m "docs: document authored directory descriptions and describe tool" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
