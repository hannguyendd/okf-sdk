# okf-mcp Producer MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `okf-mcp` workspace package exposing an MCP server that lets a producer agent author and maintain OKF bundles (add/patch concepts, read concepts/indexes), keeping indexes and logs in sync after every write.

**Architecture:** A thin FastMCP server (`server.py`) maps five tools to framework-agnostic functions in a `operations.py` module that does all file I/O over an explicit bundle-root `Path`. `okf-core` stays read-only; all authoring/writing lives in `okf-mcp`. Operations are unit-tested directly against `tmp_path` bundles; the server layer carries only a registration smoke test.

**Tech Stack:** Python 3.12, uv workspace, official `mcp` SDK (FastMCP), `pydantic-settings`, `okf-core` (workspace dep), pytest.

## Global Constraints

- Target Python `>=3.12`; this is a uv workspace (`members = ["packages/*"]`).
- `okf-mcp` runtime deps: `mcp`, `pydantic-settings`, and `okf-core` (workspace source). Do **not** add writing logic to `okf-core` — it stays read-only.
- Bundle root resolution order: explicit `bundle_root` arg → `OKF_BUNDLE_ROOT` env var (loaded via `pydantic-settings`). Error if neither resolves to an existing directory.
- Concept IDs are bundle-relative paths without `.md`; reject final segments `index`/`log` (reserved files, RSV-01).
- `add` enforces a non-empty string `type` (FM-01). Timestamps are ISO 8601 UTC with `Z`, seconds precision. Log date headings are ISO `YYYY-MM-DD`.
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit. Run tests with `uv run pytest`.
- Test files must have **unique basenames** across the workspace (okf-core already uses `test_import.py`, `test_api.py`, etc.).

---

### Task 1: Scaffold the okf-mcp package

**Files:**
- Create: `packages/okf-mcp/pyproject.toml`
- Create: `packages/okf-mcp/README.md`
- Create: `packages/okf-mcp/src/okf_mcp/__init__.py`
- Test: `packages/okf-mcp/tests/test_package_import.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installed, importable `okf_mcp` package with `okf_mcp.__version__ == "0.1.0"`.

- [ ] **Step 1: Create `packages/okf-mcp/pyproject.toml`**

```toml
[project]
name = "okf-mcp"
version = "0.1.0"
description = "Producer MCP server for authoring Open Knowledge Format (OKF) bundles"
readme = "README.md"
requires-python = ">=3.12"
dependencies = ["mcp>=1.0", "pydantic-settings>=2.0", "okf-core"]

[project.scripts]
okf-mcp = "okf_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/okf_mcp"]

[tool.uv.sources]
okf-core = { workspace = true }
```

- [ ] **Step 2: Create a minimal `packages/okf-mcp/README.md`** (expanded in Task 10; needed now so the build metadata resolves)

```markdown
# okf-mcp

Producer MCP server for authoring Open Knowledge Format (OKF) bundles.
```

- [ ] **Step 3: Create `packages/okf-mcp/src/okf_mcp/__init__.py`**

```python
"""okf_mcp — producer MCP server for authoring OKF bundles."""
from __future__ import annotations

__version__ = "0.1.0"
```

- [ ] **Step 4: Write the failing test** `packages/okf-mcp/tests/test_package_import.py`

```python
def test_package_imports_with_version():
    import okf_mcp

    assert okf_mcp.__version__ == "0.1.0"
```

- [ ] **Step 5: Sync the workspace and run the test**

Run: `uv sync && uv run pytest packages/okf-mcp/tests/test_package_import.py -v`
Expected: `uv sync` installs `okf-mcp` (editable) plus `mcp`/`pydantic-settings`; the test PASSES.

- [ ] **Step 6: Commit**

```bash
git add packages/okf-mcp/pyproject.toml packages/okf-mcp/README.md \
        packages/okf-mcp/src/okf_mcp/__init__.py \
        packages/okf-mcp/tests/test_package_import.py uv.lock
git commit -m "feat(okf-mcp): scaffold producer MCP package"
```

---

### Task 2: Operations foundations — root resolution, concept paths, time helpers

**Files:**
- Create: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: `okf_core.parse_concept_id`, `okf_core.concept_id_to_path`.
- Produces:
  - `resolve_bundle_root(arg: str | None, env_default: Path | None) -> Path`
  - `_concept_path(bundle_root: Path, concept_id: str) -> Path`
  - `_now_iso() -> str`, `_today_iso() -> str`

- [ ] **Step 1: Write the failing tests** in `packages/okf-mcp/tests/test_operations.py`

```python
from pathlib import Path

import pytest

from okf_mcp import operations


def test_resolve_prefers_arg(tmp_path):
    other = tmp_path / "b"
    other.mkdir()
    assert operations.resolve_bundle_root(str(other), tmp_path) == other.resolve()


def test_resolve_falls_back_to_env_default(tmp_path):
    assert operations.resolve_bundle_root(None, tmp_path) == tmp_path.resolve()


def test_resolve_requires_a_root():
    with pytest.raises(ValueError):
        operations.resolve_bundle_root(None, None)


def test_resolve_rejects_non_directory(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        operations.resolve_bundle_root(str(f), None)


def test_concept_path_builds_nested_path(tmp_path):
    assert operations._concept_path(tmp_path, "tables/orders") == tmp_path / "tables" / "orders.md"


def test_concept_path_rejects_reserved(tmp_path):
    with pytest.raises(ValueError):
        operations._concept_path(tmp_path, "tables/index")


def test_concept_path_rejects_bad_segment(tmp_path):
    with pytest.raises(ValueError):
        operations._concept_path(tmp_path, "tables/bad name")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'okf_mcp.operations'`.

- [ ] **Step 3: Create `packages/okf-mcp/src/okf_mcp/operations.py`**

```python
"""Producer operations over an OKF bundle (framework-agnostic)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from okf_core import concept_id_to_path, parse_concept_id

_RESERVED = ("index", "log")


def resolve_bundle_root(arg: str | None, env_default: Path | None) -> Path:
    """Resolve the bundle root from a call arg, falling back to the env default.

    Raises ``ValueError`` when neither is set or the path is not a directory.
    """
    chosen = arg or env_default
    if not chosen:
        raise ValueError("no bundle root: pass bundle_root or set OKF_BUNDLE_ROOT")
    root = Path(chosen).resolve()
    if not root.is_dir():
        raise ValueError(f"bundle root is not a directory: {root}")
    return root


def _concept_path(bundle_root: Path, concept_id: str) -> Path:
    parts = parse_concept_id(concept_id)
    if parts[-1] in _RESERVED:
        raise ValueError(
            f"concept_id {concept_id!r} collides with a reserved file name"
        )
    return concept_id_to_path(bundle_root, parts)


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _today_iso() -> str:
    return date.today().isoformat()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add bundle-root and concept-path helpers"
```

---

### Task 3: Log appending

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_append_log(log_path: Path, entry: str, today: str) -> None` — appends a bullet under a `## <today>` ISO date heading, newest-first, creating the file if absent.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_operations.py`)

```python
def test_append_log_creates_file(tmp_path):
    log = tmp_path / "log.md"
    operations._append_log(log, "* **Creation**: Added [A](a.md).", "2026-06-29")
    text = log.read_text()
    assert "# Update Log" in text
    assert "## 2026-06-29" in text
    assert "* **Creation**: Added [A](a.md)." in text


def test_append_log_prepends_under_existing_today(tmp_path):
    log = tmp_path / "log.md"
    log.write_text("# Update Log\n\n## 2026-06-29\n* **Creation**: Added [A](a.md).\n")
    operations._append_log(log, "* **Update**: Updated [B](b.md).", "2026-06-29")
    lines = log.read_text().splitlines()
    i = lines.index("## 2026-06-29")
    assert lines[i + 1] == "* **Update**: Updated [B](b.md)."  # newest first
    assert lines[i + 2] == "* **Creation**: Added [A](a.md)."


def test_append_log_inserts_new_today_above_older(tmp_path):
    log = tmp_path / "log.md"
    log.write_text("# Update Log\n\n## 2026-06-01\n* **Creation**: Added [A](a.md).\n")
    operations._append_log(log, "* **Update**: Updated [A](a.md).", "2026-06-29")
    lines = log.read_text().splitlines()
    assert lines.index("## 2026-06-29") < lines.index("## 2026-06-01")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k append_log -v`
Expected: FAIL with `AttributeError: module 'okf_mcp.operations' has no attribute '_append_log'`.

- [ ] **Step 3: Add `_append_log` to `operations.py`** (after `_today_iso`)

```python
def _append_log(log_path: Path, entry: str, today: str) -> None:
    """Append ``entry`` under a ``## <today>`` group in ``log_path`` (newest-first).

    Creates the file with a ``# Update Log`` title when absent; prepends the
    entry under an existing today group; otherwise inserts a new today group
    above older date groups.
    """
    heading = f"## {today}"
    if not log_path.exists():
        log_path.write_text(f"# Update Log\n\n{heading}\n{entry}\n", encoding="utf-8")
        return
    lines = log_path.read_text(encoding="utf-8").splitlines()
    first_h2 = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), None)
    if first_h2 is not None and lines[first_h2].strip() == heading:
        new_lines = lines[: first_h2 + 1] + [entry] + lines[first_h2 + 1 :]
    elif first_h2 is not None:
        new_lines = lines[:first_h2] + [heading, entry, ""] + lines[first_h2:]
    else:
        new_lines = lines + ["", heading, entry]
    log_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k append_log -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add dated log appending"
```

---

### Task 4: `add_concept`

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: `_concept_path`, `_now_iso`, `_append_log`, `okf_core.OKFDocument`, `okf_core.regenerate_indexes`.
- Produces:
  - `_append_log_for(concept_path: Path, label: str, action: str, verb: str) -> Path`
  - `_summary(bundle_root, concept_id, path, action, log_path, indexes) -> dict`
  - `add_concept(bundle_root: Path, concept_id: str, frontmatter: dict, body: str) -> dict` returning `{concept_id, path, action, log, indexes}` (bundle-relative paths; `action == "created"`).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_operations.py`; also add the import below to the top of the file)

```python
# add to the imports at the top of tests/test_operations.py:
from okf_core import OKFDocument
```

```python
def test_add_writes_concept(tmp_path):
    res = operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "# Schema\n"
    )
    f = tmp_path / "tables" / "orders.md"
    assert f.exists()
    doc = OKFDocument.parse(f.read_text())
    assert doc.frontmatter["type"] == "Table"
    assert doc.frontmatter["title"] == "Orders"
    assert "timestamp" in doc.frontmatter
    assert "# Schema" in doc.body
    assert res["action"] == "created"
    assert res["path"] == "tables/orders.md"


def test_add_rejects_existing(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    with pytest.raises(ValueError):
        operations.add_concept(tmp_path, "a", {"type": "X"}, "")


def test_add_requires_type(tmp_path):
    with pytest.raises(ValueError):
        operations.add_concept(tmp_path, "a", {"title": "no type"}, "")


def test_add_rejects_reserved_id(tmp_path):
    with pytest.raises(ValueError):
        operations.add_concept(tmp_path, "tables/index", {"type": "X"}, "")


def test_add_preserves_caller_timestamp(tmp_path):
    operations.add_concept(
        tmp_path, "a", {"type": "X", "timestamp": "2020-01-01T00:00:00Z"}, ""
    )
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["timestamp"] == "2020-01-01T00:00:00Z"


def test_add_writes_log_and_index(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    log = tmp_path / "tables" / "log.md"
    assert "Added [Orders](orders.md)" in log.read_text()
    assert (tmp_path / "tables" / "index.md").exists()
    assert (tmp_path / "index.md").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k add -v`
Expected: FAIL with `AttributeError: module 'okf_mcp.operations' has no attribute 'add_concept'`.

- [ ] **Step 3: Update imports and add the functions in `operations.py`**

Change the `okf_core` import line to:

```python
from okf_core import (
    OKFDocument,
    concept_id_to_path,
    parse_concept_id,
    regenerate_indexes,
)
```

Append:

```python
def _append_log_for(concept_path: Path, label: str, action: str, verb: str) -> Path:
    log_path = concept_path.parent / "log.md"
    entry = f"* **{action}**: {verb} [{label}]({concept_path.name})."
    _append_log(log_path, entry, _today_iso())
    return log_path


def _summary(
    bundle_root: Path,
    concept_id: str,
    path: Path,
    action: str,
    log_path: Path,
    indexes: list[Path],
) -> dict:
    return {
        "concept_id": concept_id,
        "path": path.relative_to(bundle_root).as_posix(),
        "action": action,
        "log": log_path.relative_to(bundle_root).as_posix(),
        "indexes": [Path(p).relative_to(bundle_root).as_posix() for p in indexes],
    }


def add_concept(
    bundle_root: Path, concept_id: str, frontmatter: dict, body: str
) -> dict:
    """Create a new concept document, then reindex and log the creation."""
    path = _concept_path(bundle_root, concept_id)
    if path.exists():
        raise ValueError(f"concept already exists: {concept_id}")
    fm = dict(frontmatter or {})
    type_val = fm.get("type")
    if not isinstance(type_val, str) or not type_val.strip():
        raise ValueError("frontmatter must include a non-empty string 'type'")
    if not fm.get("timestamp"):
        fm["timestamp"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        OKFDocument(frontmatter=fm, body=body or "").serialize(), encoding="utf-8"
    )
    label = str(fm.get("title") or path.stem)
    log_path = _append_log_for(path, label, "Creation", "Added")
    indexes = regenerate_indexes(bundle_root)
    return _summary(bundle_root, concept_id, path, "created", log_path, indexes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k add -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add add_concept with logging and reindex"
```

---

### Task 5: `patch_concept`

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: `_concept_path`, `_now_iso`, `_append_log_for`, `_summary`, `OKFDocument.parse`, `regenerate_indexes`.
- Produces: `patch_concept(bundle_root: Path, concept_id: str, frontmatter: dict | None = None, body: str | None = None) -> dict` (`action == "updated"`). Merges only non-`None` frontmatter keys (no deletion); replaces body only when given; refreshes `timestamp` unless the caller passed one.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_operations.py`)

```python
def test_patch_merges_only_given_keys(tmp_path):
    operations.add_concept(
        tmp_path, "a", {"type": "X", "title": "Old", "description": "keep"}, "body"
    )
    operations.patch_concept(tmp_path, "a", {"title": "New"})
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["title"] == "New"
    assert doc.frontmatter["description"] == "keep"
    assert doc.frontmatter["type"] == "X"


def test_patch_ignores_none_values(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X", "title": "Old"}, "")
    operations.patch_concept(tmp_path, "a", {"title": None})
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["title"] == "Old"


def test_patch_replaces_body_only_when_given(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "original")
    operations.patch_concept(tmp_path, "a", {"title": "T"})
    assert OKFDocument.parse((tmp_path / "a.md").read_text()).body.strip() == "original"
    operations.patch_concept(tmp_path, "a", body="replaced")
    assert OKFDocument.parse((tmp_path / "a.md").read_text()).body.strip() == "replaced"


def test_patch_refreshes_timestamp(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X", "timestamp": "2020-01-01T00:00:00Z"}, "")
    operations.patch_concept(tmp_path, "a", {"title": "T"})
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["timestamp"] != "2020-01-01T00:00:00Z"


def test_patch_keeps_caller_timestamp(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    operations.patch_concept(tmp_path, "a", {"timestamp": "2030-01-01T00:00:00Z"})
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["timestamp"] == "2030-01-01T00:00:00Z"


def test_patch_missing_errors(tmp_path):
    with pytest.raises(ValueError):
        operations.patch_concept(tmp_path, "nope", {"title": "X"})


def test_patch_logs_update(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X", "title": "A"}, "")
    operations.patch_concept(tmp_path, "a", {"title": "A2"})
    assert "Updated [A2](a.md)" in (tmp_path / "log.md").read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k patch -v`
Expected: FAIL with `AttributeError: ... has no attribute 'patch_concept'`.

- [ ] **Step 3: Add `patch_concept` to `operations.py`**

```python
def patch_concept(
    bundle_root: Path,
    concept_id: str,
    frontmatter: dict | None = None,
    body: str | None = None,
) -> dict:
    """Update an existing concept (merge frontmatter, optional body), reindex, log."""
    path = _concept_path(bundle_root, concept_id)
    if not path.exists():
        raise ValueError(f"concept not found: {concept_id}")
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    fm = dict(doc.frontmatter)
    caller_ts = False
    for key, value in (frontmatter or {}).items():
        if value is not None:
            fm[key] = value
            if key == "timestamp":
                caller_ts = True
    new_body = doc.body if body is None else body
    if not caller_ts:
        fm["timestamp"] = _now_iso()
    path.write_text(
        OKFDocument(frontmatter=fm, body=new_body).serialize(), encoding="utf-8"
    )
    label = str(fm.get("title") or path.stem)
    log_path = _append_log_for(path, label, "Update", "Updated")
    indexes = regenerate_indexes(bundle_root)
    return _summary(bundle_root, concept_id, path, "updated", log_path, indexes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k patch -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add patch_concept with merge semantics"
```

---

### Task 6: `get_concept`

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: `_concept_path`, `OKFDocument.parse`, `okf_core.extract_links`.
- Produces: `get_concept(bundle_root: Path, concept_id: str) -> dict` returning `{id, frontmatter, body, links_to}`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_operations.py`)

```python
def test_get_returns_doc(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "see [c](customers.md)"
    )
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    res = operations.get_concept(tmp_path, "tables/orders")
    assert res["id"] == "tables/orders"
    assert res["frontmatter"]["type"] == "Table"
    assert "tables/customers" in res["links_to"]


def test_get_missing_errors(tmp_path):
    with pytest.raises(ValueError):
        operations.get_concept(tmp_path, "nope")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k get -v`
Expected: FAIL with `AttributeError: ... has no attribute 'get_concept'`.

- [ ] **Step 3: Update imports and add `get_concept` in `operations.py`**

Change the `okf_core` import line to add `extract_links`:

```python
from okf_core import (
    OKFDocument,
    concept_id_to_path,
    extract_links,
    parse_concept_id,
    regenerate_indexes,
)
```

Append:

```python
def get_concept(bundle_root: Path, concept_id: str) -> dict:
    """Read one concept: frontmatter, body, and resolved outgoing links."""
    path = _concept_path(bundle_root, concept_id)
    if not path.exists():
        raise ValueError(f"concept not found: {concept_id}")
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    links = extract_links(doc.body or "", path.parent, bundle_root)
    return {
        "id": concept_id,
        "frontmatter": doc.frontmatter,
        "body": doc.body,
        "links_to": links,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k get -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add get_concept"
```

---

### Task 7: `list_concepts`

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: `okf_core.Bundle`.
- Produces: `list_concepts(bundle_root: Path, type: str | None = None, prefix: str | None = None) -> list[dict]` returning `{id, type, title, description, tags}` per concept, filtered by exact `type` and/or id `prefix`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_operations.py`)

```python
def test_list_all(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    operations.add_concept(tmp_path, "metrics/mau", {"type": "Metric", "title": "MAU"}, "")
    ids = {c["id"] for c in operations.list_concepts(tmp_path)}
    assert ids == {"tables/orders", "metrics/mau"}


def test_list_filters_by_type(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(tmp_path, "metrics/mau", {"type": "Metric"}, "")
    res = operations.list_concepts(tmp_path, type="Metric")
    assert [c["id"] for c in res] == ["metrics/mau"]


def test_list_filters_by_prefix(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(tmp_path, "metrics/mau", {"type": "Metric"}, "")
    res = operations.list_concepts(tmp_path, prefix="tables/")
    assert [c["id"] for c in res] == ["tables/orders"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k list -v`
Expected: FAIL with `AttributeError: ... has no attribute 'list_concepts'`.

- [ ] **Step 3: Update imports and add `list_concepts` in `operations.py`**

Change the `okf_core` import line to add `Bundle`:

```python
from okf_core import (
    Bundle,
    OKFDocument,
    concept_id_to_path,
    extract_links,
    parse_concept_id,
    regenerate_indexes,
)
```

Append:

```python
def list_concepts(
    bundle_root: Path, type: str | None = None, prefix: str | None = None
) -> list[dict]:
    """List concepts, optionally filtered by exact ``type`` and/or id ``prefix``."""
    bundle = Bundle.load(bundle_root)
    out: list[dict] = []
    for c in bundle.concepts:
        if type is not None and c.type != type:
            continue
        if prefix is not None and not c.id.startswith(prefix):
            continue
        out.append(
            {
                "id": c.id,
                "type": c.type,
                "title": c.title,
                "description": c.description,
                "tags": c.tags,
            }
        )
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k list -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add list_concepts"
```

---

### Task 8: `read_index`

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `_rel_dir(bundle_root: Path, directory: Path) -> str`
  - `read_index(bundle_root: Path, dir: str | None = None, depth: int = 1) -> list[dict]` returning depth-ordered `{dir, path, content}` for each `index.md` within `depth` levels.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_operations.py`)

```python
def test_read_index_depth_one(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    res = operations.read_index(tmp_path)
    assert len(res) == 1
    assert res[0]["dir"] == ""
    assert res[0]["path"] == "index.md"
    assert "tables" in res[0]["content"]


def test_read_index_depth_two_descends(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    res = operations.read_index(tmp_path, depth=2)
    dirs = {r["dir"] for r in res}
    assert "" in dirs and "tables" in dirs


def test_read_index_specific_dir(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    res = operations.read_index(tmp_path, dir="tables")
    assert res[0]["dir"] == "tables"
    assert "Orders" in res[0]["content"]


def test_read_index_bad_depth(tmp_path):
    with pytest.raises(ValueError):
        operations.read_index(tmp_path, depth=4)


def test_read_index_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        operations.read_index(tmp_path, dir="../outside")


def test_read_index_missing_is_empty(tmp_path):
    assert operations.read_index(tmp_path) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k read_index -v`
Expected: FAIL with `AttributeError: ... has no attribute 'read_index'`.

- [ ] **Step 3: Add `_rel_dir` and `read_index` to `operations.py`**

```python
def _rel_dir(bundle_root: Path, directory: Path) -> str:
    if directory == bundle_root:
        return ""
    return directory.relative_to(bundle_root).as_posix()


def read_index(
    bundle_root: Path, dir: str | None = None, depth: int = 1
) -> list[dict]:
    """Return ``index.md`` files for progressive disclosure, breadth-first.

    Starts at ``dir`` (bundle root if omitted) and descends ``depth`` levels
    (1..3). Missing ``index.md`` files are skipped; read-only.
    """
    if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= 3:
        raise ValueError("depth must be an integer in 1..3")
    root = bundle_root.resolve()
    start = root if not dir else (root / dir).resolve()
    if start != root and root not in start.parents:
        raise ValueError(f"dir escapes the bundle root: {dir}")
    results: list[dict] = []
    level = [start]
    for _ in range(depth):
        nxt: list[Path] = []
        for d in level:
            index_file = d / "index.md"
            if index_file.is_file():
                results.append(
                    {
                        "dir": _rel_dir(root, d),
                        "path": index_file.relative_to(root).as_posix(),
                        "content": index_file.read_text(encoding="utf-8"),
                    }
                )
            if d.is_dir():
                nxt.extend(sorted(p for p in d.iterdir() if p.is_dir()))
        level = nxt
        if not level:
            break
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k read_index -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the full operations suite and commit**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -v`
Expected: PASS (all operations tests).

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add read_index progressive disclosure"
```

---

### Task 9: FastMCP server wiring

**Files:**
- Create: `packages/okf-mcp/src/okf_mcp/server.py`
- Test: `packages/okf-mcp/tests/test_server.py`

**Interfaces:**
- Consumes: `okf_mcp.operations` (all functions), `mcp.server.fastmcp.FastMCP`, `pydantic_settings.BaseSettings`/`SettingsConfigDict`.
- Produces: a module-level `mcp` FastMCP app registering tools `add`, `patch`, `get`, `list`, `read_index`; a `Settings` model reading `OKF_BUNDLE_ROOT`; a `main()` entry point running stdio transport.

- [ ] **Step 1: Write the failing test** `packages/okf-mcp/tests/test_server.py`

```python
import asyncio

from okf_mcp.server import mcp


def test_all_tools_registered():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"add", "patch", "get", "list", "read_index"} <= names
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/okf-mcp/tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'okf_mcp.server'`.

- [ ] **Step 3: Create `packages/okf-mcp/src/okf_mcp/server.py`**

```python
"""FastMCP producer server exposing okf_mcp.operations as MCP tools."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict

from okf_mcp import operations


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OKF_")

    bundle_root: Path | None = None


settings = Settings()
mcp = FastMCP("okf-producer")


def _root(bundle_root: str | None) -> Path:
    return operations.resolve_bundle_root(bundle_root, settings.bundle_root)


@mcp.tool()
def add(
    concept_id: str,
    frontmatter: dict[str, Any],
    body: str,
    bundle_root: str | None = None,
) -> dict:
    """Create a new OKF concept document.

    `concept_id` is the bundle-relative path without `.md` (e.g. `tables/orders`).
    `frontmatter` must include a non-empty `type`; recommended keys: `title`,
    `description`, `resource`, `tags`. `timestamp` is set automatically when
    omitted. Fails if the concept already exists. Regenerates indexes and
    appends a Creation entry to the directory's `log.md`.
    """
    return operations.add_concept(_root(bundle_root), concept_id, frontmatter, body)


@mcp.tool()
def patch(
    concept_id: str,
    frontmatter: dict[str, Any] | None = None,
    body: str | None = None,
    bundle_root: str | None = None,
) -> dict:
    """Update an existing OKF concept.

    Merges the given `frontmatter` keys (null values are ignored; keys are never
    deleted). Replaces the body only when `body` is provided. `timestamp` is
    refreshed unless you pass one. Fails if the concept does not exist.
    Regenerates indexes and appends an Update entry to `log.md`.
    """
    return operations.patch_concept(_root(bundle_root), concept_id, frontmatter, body)


@mcp.tool()
def get(concept_id: str, bundle_root: str | None = None) -> dict:
    """Read one concept: its frontmatter, body, and resolved outgoing links."""
    return operations.get_concept(_root(bundle_root), concept_id)


@mcp.tool(name="list")
def list_(
    type: str | None = None,
    prefix: str | None = None,
    bundle_root: str | None = None,
) -> list[dict]:
    """List concepts, optionally filtered by exact `type` and/or id `prefix`."""
    return operations.list_concepts(_root(bundle_root), type, prefix)


@mcp.tool()
def read_index(
    dir: str | None = None,
    depth: int = 1,
    bundle_root: str | None = None,
) -> list[dict]:
    """Read `index.md` files for progressive disclosure.

    `dir` is a bundle-relative directory (root if omitted). `depth` (1-3) sets
    how many directory levels of indexes to return, breadth-first.
    """
    return operations.read_index(_root(bundle_root), dir, depth)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/okf-mcp/tests/test_server.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/server.py packages/okf-mcp/tests/test_server.py
git commit -m "feat(okf-mcp): wire FastMCP server with five tools"
```

---

### Task 10: Documentation

**Files:**
- Modify: `packages/okf-mcp/README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing.
- Produces: user-facing docs for configuration and tools; updated workspace project status.

- [ ] **Step 1: Replace `packages/okf-mcp/README.md` with the full version**

````markdown
# okf-mcp

Producer MCP server for authoring and maintaining Open Knowledge Format (OKF)
bundles. Built on the official `mcp` SDK (FastMCP); depends on `okf-core`.

## Configuration

Set the bundle root via the `OKF_BUNDLE_ROOT` environment variable, or pass
`bundle_root` to any tool to override per call. Example MCP client config:

```json
{
  "mcpServers": {
    "okf-producer": {
      "command": "okf-mcp",
      "env": { "OKF_BUNDLE_ROOT": "/path/to/bundle" }
    }
  }
}
```

## Tools

- `add(concept_id, frontmatter, body, bundle_root?)` — create a concept (fails if it exists; `type` required).
- `patch(concept_id, frontmatter?, body?, bundle_root?)` — update a concept (merge-only frontmatter; body replaced only when given).
- `get(concept_id, bundle_root?)` — read one concept (frontmatter, body, outgoing links).
- `list(type?, prefix?, bundle_root?)` — enumerate concepts, optionally filtered.
- `read_index(dir?, depth=1, bundle_root?)` — read `index.md` files for progressive disclosure (depth 1-3).

Every `add`/`patch` regenerates indexes and appends a dated entry to the changed
concept's directory `log.md`. `timestamp` frontmatter is managed automatically.

## Development

```bash
uv sync
uv run pytest packages/okf-mcp
```
````

- [ ] **Step 2: Update `CLAUDE.md` project status**

Read `CLAUDE.md`, then update the "Project status" paragraph that currently
describes `okf-core` as the only member. Replace the sentence beginning
"The first and currently only member is" with:

```markdown
The workspace has two members. **`packages/okf-core`** — a library for
reading, indexing, and validating OKF bundles (`OKFDocument`, `Bundle`,
`regenerate_indexes`, `validate_bundle`); its only runtime dependency is PyYAML.
**`packages/okf-mcp`** — a producer MCP server (official `mcp` SDK / FastMCP)
for authoring bundles: tools to add, patch, get, list concepts and read indexes,
re-indexing and appending log entries after each write. See
`docs/superpowers/specs/2026-06-29-okf-mcp-producer-design.md` and
`docs/superpowers/plans/2026-06-29-okf-mcp-producer.md`.
```

Keep the surrounding references to the okf-core design/conformance specs intact.

- [ ] **Step 3: Run the full workspace suite**

Run: `uv run pytest`
Expected: PASS (okf-core suite plus all okf-mcp tests).

- [ ] **Step 4: Commit**

```bash
git add packages/okf-mcp/README.md CLAUDE.md
git commit -m "docs(okf-mcp): document configuration, tools, and workspace status"
```

---

## Self-Review

**Spec coverage:**
- New `okf-mcp` package, FastMCP, depends on okf-core — Task 1, Task 9. ✔
- Bundle root: arg → `OKF_BUNDLE_ROOT` via pydantic-settings — Task 2 (`resolve_bundle_root`), Task 9 (`Settings`). ✔
- `add` (exists-check, type-enforce, auto-timestamp, log, reindex) — Task 4. ✔
- `patch` (exists-check, merge-only non-None, optional body, timestamp refresh, log, reindex) — Task 5. ✔
- `get` (frontmatter, body, links_to) — Task 6. ✔
- `list` (type/prefix filters) — Task 7. ✔
- `read_index` (depth 1-3, breadth-first, raw content, escape rejection) — Task 8. ✔
- Auto-timestamp rules (add: set iff absent; patch: refresh unless passed) — Tasks 4/5 with tests. ✔
- Directory-scoped log, newest-first, ISO headings, relative link + title label — Task 3 (`_append_log`) + Task 4 (`_append_log_for`). ✔
- Return summary shape (concept_id, path, action, log, indexes) — Task 4 (`_summary`). ✔
- Reserved-name rejection (RSV-01) — Task 2 (`_concept_path`). ✔
- No bundle validation in tools (re-index only) — none added. ✔
- Packaging, console script, README, CLAUDE.md — Tasks 1, 10. ✔

**Placeholder scan:** No TODO/TBD; every code/test step shows full code; commands have expected output. ✔

**Type consistency:** `operations` function names/signatures defined in early tasks match their use in `server.py` (Task 9) and across tests: `resolve_bundle_root`, `_concept_path`, `_append_log`, `_append_log_for`, `_summary`, `add_concept`, `patch_concept`, `get_concept`, `list_concepts`, `read_index`. The `okf_core` import line grows monotonically (Tasks 2→4→6→7) and is shown in full at each change. ✔
