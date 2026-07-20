# okf-mcp Store Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "store mode" to the okf-mcp producer server: configure `OKF_STORE_ROOT` once and the server auto-partitions documents into a per-project subfolder named `<project-basename>-<hash8-of-absolute-path>`.

**Architecture:** Two pure, framework-agnostic helpers in `operations.py` compute the folder name and effective bundle root from a project path. The FastMCP server gains a `store_root` setting, discovers the project path from the MCP `roots` capability (falling back to the working directory), and resolves each tool call to `<store_root>/<project-folder>`. The tool wrappers become `async` and take an injected `ctx: Context`; the client-facing tool schemas are unchanged.

**Tech Stack:** Python 3.12, uv workspace, `mcp` SDK (FastMCP), `pydantic-settings`, PyYAML (via okf-core), pytest.

## Global Constraints

- Resolution precedence per tool call: explicit `bundle_root` arg > `OKF_STORE_ROOT` (store mode) > `OKF_BUNDLE_ROOT` (legacy).
- Setting **both** `OKF_STORE_ROOT` and `OKF_BUNDLE_ROOT` raises `ValueError("set OKF_STORE_ROOT or OKF_BUNDLE_ROOT, not both")` — but only when no explicit `bundle_root` arg is given (the arg short-circuits the check).
- Folder name = `<slug(basename)>-<sha256(abs_posix_path)[:8]>`; empty basename falls back to `project`. `slug` maps runs of chars outside `[A-Za-z0-9._-]` to a single `-` and trims.
- `OKF_STORE_ROOT` must be an existing directory; the per-project subfolder is auto-created with `mkdir(parents=True, exist_ok=True)`.
- Project path from `await ctx.session.list_roots()` — first `file://` root; on any exception, empty roots, or no usable file URI, fall back to `Path.cwd()`.
- All new work is TDD: failing test first, minimal implementation, passing test, commit.
- Run tests with `uv run pytest` from the workspace root.

---

### Task 1: Pure folder-derivation helpers in `operations.py`

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py`
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: nothing new (stdlib `hashlib`, `re`, `pathlib`).
- Produces:
  - `derive_project_folder(project_path: str | Path) -> str` — returns `<slug>-<hash8>`.
  - `resolve_store_bundle_root(store_root: str | Path, project_path: str | Path) -> Path` — validates the store root exists, joins the derived folder, `mkdir -p`, returns it.

- [ ] **Step 1: Write the failing tests**

Add to the end of `packages/okf-mcp/tests/test_operations.py` (the file already imports `re`, `pytest`, and `operations`):

```python
def test_derive_project_folder_shape(tmp_path):
    name = operations.derive_project_folder(tmp_path / "web-app")
    assert re.fullmatch(r"web-app-[0-9a-f]{8}", name)


def test_derive_project_folder_is_deterministic(tmp_path):
    project = tmp_path / "web-app"
    assert operations.derive_project_folder(project) == operations.derive_project_folder(
        project
    )


def test_derive_project_folder_distinguishes_same_basename(tmp_path):
    a = tmp_path / "a" / "web-app"
    b = tmp_path / "b" / "web-app"
    assert operations.derive_project_folder(a) != operations.derive_project_folder(b)


def test_derive_project_folder_slugifies_basename(tmp_path):
    name = operations.derive_project_folder(tmp_path / "My App (v2)")
    assert re.fullmatch(r"My-App-v2-[0-9a-f]{8}", name)


def test_derive_project_folder_empty_basename_falls_back(tmp_path):
    # Filesystem root has an empty ``.name``.
    name = operations.derive_project_folder("/")
    assert re.fullmatch(r"project-[0-9a-f]{8}", name)


def test_resolve_store_bundle_root_creates_subfolder(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    project = tmp_path / "proj" / "web-app"
    root = operations.resolve_store_bundle_root(store, project)
    assert root.is_dir()
    assert root == store.resolve() / operations.derive_project_folder(project)


def test_resolve_store_bundle_root_requires_existing_store(tmp_path):
    with pytest.raises(ValueError):
        operations.resolve_store_bundle_root(
            tmp_path / "missing", tmp_path / "web-app"
        )


def test_resolve_store_bundle_root_rejects_file_store(tmp_path):
    f = tmp_path / "store.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        operations.resolve_store_bundle_root(f, tmp_path / "web-app")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k "derive_project_folder or resolve_store_bundle_root" -v`
Expected: FAIL with `AttributeError: module 'okf_mcp.operations' has no attribute 'derive_project_folder'`.

- [ ] **Step 3: Add the imports**

At the top of `packages/okf-mcp/src/okf_mcp/operations.py`, the current import block is:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
```

Change it to add `hashlib` and `re`:

```python
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
```

- [ ] **Step 4: Implement the helpers**

In `packages/okf-mcp/src/okf_mcp/operations.py`, insert the following immediately **after** the existing `resolve_bundle_root` function (it ends at the `return root` on the line before `def _concept_path`):

```python
_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(name: str) -> str:
    """Map any run of filesystem-unsafe characters to a single ``-`` and trim."""
    return _SLUG_RE.sub("-", name).strip("-")


def derive_project_folder(project_path: str | Path) -> str:
    """Per-project subfolder name: ``<slug(basename)>-<hash8-of-absolute-path>``.

    The path is resolved to an absolute, symlink-free form first, so the name is
    stable regardless of how the path was expressed. Two projects sharing a
    basename at different absolute paths hash differently and never collide. An
    empty basename (e.g. the filesystem root) falls back to ``project``.
    """
    p = Path(project_path).resolve()
    base = _slug(p.name) or "project"
    digest = hashlib.sha256(p.as_posix().encode("utf-8")).hexdigest()[:8]
    return f"{base}-{digest}"


def resolve_store_bundle_root(
    store_root: str | Path, project_path: str | Path
) -> Path:
    """Resolve ``<store_root>/<derive_project_folder(project_path)>``.

    Requires ``store_root`` to be an existing directory (fail fast on a misconfigured
    ``OKF_STORE_ROOT``); auto-creates the per-project subfolder on first use.
    """
    store = Path(store_root).resolve()
    if not store.is_dir():
        raise ValueError(f"store root is not a directory: {store}")
    root = store / derive_project_folder(project_path)
    root.mkdir(parents=True, exist_ok=True)
    return root
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k "derive_project_folder or resolve_store_bundle_root" -v`
Expected: PASS (8 tests).

- [ ] **Step 6: Run the full okf-mcp suite to check for regressions**

Run: `uv run pytest packages/okf-mcp -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): add pure store-mode folder derivation helpers"
```

---

### Task 2: Wire store mode into the server

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/server.py` (whole file — Settings, helpers, all nine tool wrappers)
- Test: `packages/okf-mcp/tests/test_server.py`

**Interfaces:**
- Consumes: `operations.derive_project_folder`, `operations.resolve_store_bundle_root`, `operations.resolve_bundle_root` (Task 1 and existing).
- Produces:
  - `Settings.store_root: Path | None` (env `OKF_STORE_ROOT`).
  - `_uri_to_path(uri) -> Path | None`.
  - `async _project_root(ctx: Context) -> Path`.
  - `async _root(bundle_root: str | None, ctx: Context) -> Path`.
  - Nine `async` tool wrappers, each with `ctx: Context` as the first parameter.

**Why the whole file changes together:** making `_root` async requires every tool that calls it to `await` it, so the setting, helpers, async `_root`, and the wrapper conversions are one indivisible change. `ctx: Context` is placed **first** in each wrapper — verified to be excluded from the client-facing schema and required to avoid Python's "non-default argument follows default argument" error.

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `packages/okf-mcp/tests/test_server.py` with:

```python
import asyncio
from types import SimpleNamespace

import pytest
from mcp import types as mcp_types

from okf_mcp import operations, server
from okf_mcp.server import Settings, mcp


class _FakeSession:
    """Stand-in for the MCP ServerSession's ``list_roots``.

    ``root_paths=None`` simulates a client without the roots capability (raises);
    a list yields ``file://`` roots for those paths.
    """

    def __init__(self, root_paths):
        self._root_paths = root_paths

    async def list_roots(self):
        if self._root_paths is None:
            raise RuntimeError("client has no roots capability")
        return mcp_types.ListRootsResult(
            roots=[
                mcp_types.Root(uri=f"file://{p}", name=None) for p in self._root_paths
            ]
        )


def _ctx(root_paths):
    return SimpleNamespace(session=_FakeSession(root_paths))


def _use_settings(monkeypatch, **env):
    """Install a fresh Settings on the server module built only from ``env``."""
    for key in ("OKF_STORE_ROOT", "OKF_BUNDLE_ROOT"):
        monkeypatch.delenv(key, raising=False)
    for key, val in env.items():
        monkeypatch.setenv(key, str(val))
    fresh = Settings(_env_file=None)
    monkeypatch.setattr(server, "settings", fresh)
    return fresh


def test_all_tools_registered():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {
        "add",
        "patch",
        "get",
        "list",
        "read_index",
        "move",
        "reindex",
        "delete",
        "describe",
    } <= names


def test_tool_schema_excludes_ctx():
    add_tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "add")
    assert "ctx" not in add_tool.inputSchema.get("properties", {})


def test_settings_reads_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("OKF_BUNDLE_ROOT", raising=False)
    target = tmp_path / "bundle"
    target.mkdir()
    (tmp_path / ".env").write_text(f"OKF_BUNDLE_ROOT={target}\n")
    monkeypatch.chdir(tmp_path)
    assert Settings().bundle_root == target


def test_settings_reads_store_root(tmp_path, monkeypatch):
    monkeypatch.delenv("OKF_BUNDLE_ROOT", raising=False)
    monkeypatch.setenv("OKF_STORE_ROOT", str(tmp_path))
    assert Settings(_env_file=None).store_root == tmp_path


def test_root_prefers_explicit_arg(tmp_path, monkeypatch):
    _use_settings(monkeypatch, OKF_STORE_ROOT=tmp_path, OKF_BUNDLE_ROOT=tmp_path)
    target = tmp_path / "explicit"
    target.mkdir()
    got = asyncio.run(server._root(str(target), _ctx(["/whatever"])))
    assert got == target.resolve()


def test_root_errors_when_both_env_set(tmp_path, monkeypatch):
    _use_settings(monkeypatch, OKF_STORE_ROOT=tmp_path, OKF_BUNDLE_ROOT=tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(server._root(None, _ctx(["/whatever"])))


def test_root_store_mode_uses_derived_folder(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    project = tmp_path / "proj" / "web-app"
    _use_settings(monkeypatch, OKF_STORE_ROOT=store)
    got = asyncio.run(server._root(None, _ctx([str(project)])))
    assert got == store.resolve() / operations.derive_project_folder(project)
    assert got.is_dir()


def test_root_store_mode_falls_back_to_cwd(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    monkeypatch.chdir(tmp_path)
    _use_settings(monkeypatch, OKF_STORE_ROOT=store)
    got = asyncio.run(server._root(None, _ctx(None)))
    assert got == store.resolve() / operations.derive_project_folder(tmp_path)


def test_root_legacy_bundle_mode(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _use_settings(monkeypatch, OKF_BUNDLE_ROOT=bundle)
    got = asyncio.run(server._root(None, _ctx(None)))
    assert got == bundle.resolve()


def test_root_errors_when_nothing_configured(monkeypatch):
    _use_settings(monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(server._root(None, _ctx(None)))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/okf-mcp/tests/test_server.py -v`
Expected: FAIL/ERROR — the `test_root_*` cases error because the current `_root` is a synchronous one-argument function (`asyncio.run` on its non-awaitable return, plus a `TypeError` from the extra `ctx` argument), and `test_settings_reads_store_root` fails with `AttributeError` because `store_root` is not on `Settings` yet. (`test_all_tools_registered` still passes.)

- [ ] **Step 3: Rewrite `server.py`**

Replace the entire contents of `packages/okf-mcp/src/okf_mcp/server.py` with:

```python
"""FastMCP producer server exposing okf_mcp.operations as MCP tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

from mcp.server.fastmcp import Context, FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict

from okf_mcp import operations


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OKF_", env_file=".env", extra="ignore"
    )

    bundle_root: Path | None = None
    store_root: Path | None = None


settings = Settings()
mcp = FastMCP("okf-producer")


def _uri_to_path(uri: object) -> Path | None:
    """Convert a ``file://`` root URI to a local path; ``None`` if not a file URI."""
    parsed = urlparse(str(uri))
    if parsed.scheme != "file":
        return None
    path = url2pathname(parsed.path)
    return Path(path) if path else None


async def _project_root(ctx: Context) -> Path:
    """Discover the current project directory from the client's MCP roots.

    Returns the first ``file://`` root the client advertises; falls back to the
    process working directory when the client sends no usable roots or lacks the
    ``roots`` capability.
    """
    try:
        result = await ctx.session.list_roots()
        roots = result.roots or []
    except Exception:
        roots = []
    for root in roots:
        path = _uri_to_path(root.uri)
        if path is not None:
            return path
    return Path.cwd()


async def _root(bundle_root: str | None, ctx: Context) -> Path:
    """Resolve the effective bundle root for a tool call.

    Precedence: an explicit ``bundle_root`` arg wins; otherwise store mode
    (``OKF_STORE_ROOT``) partitions per project into ``<store_root>/<project-folder>``;
    otherwise the legacy single bundle (``OKF_BUNDLE_ROOT``). Setting both env
    roots (with no arg) is an error.
    """
    if bundle_root:
        return operations.resolve_bundle_root(bundle_root, None)
    if settings.store_root and settings.bundle_root:
        raise ValueError("set OKF_STORE_ROOT or OKF_BUNDLE_ROOT, not both")
    if settings.store_root:
        project = await _project_root(ctx)
        return operations.resolve_store_bundle_root(settings.store_root, project)
    return operations.resolve_bundle_root(None, settings.bundle_root)


@mcp.tool()
async def add(
    ctx: Context,
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
    appends a Creation entry to the directory's `_log.md`.
    """
    return operations.add_concept(
        await _root(bundle_root, ctx), concept_id, frontmatter, body
    )


@mcp.tool()
async def patch(
    ctx: Context,
    concept_id: str,
    frontmatter: dict[str, Any] | None = None,
    body: str | None = None,
    bundle_root: str | None = None,
) -> dict:
    """Update an existing OKF concept.

    Merges the given `frontmatter` keys (null values are ignored; keys are never
    deleted). Replaces the body only when `body` is provided. `timestamp` is
    refreshed unless you pass one. Fails if the concept does not exist.
    Regenerates indexes and appends an Update entry to `_log.md`.
    """
    return operations.patch_concept(
        await _root(bundle_root, ctx), concept_id, frontmatter, body
    )


@mcp.tool()
async def get(ctx: Context, concept_id: str, bundle_root: str | None = None) -> dict:
    """Read one concept: its frontmatter, body, and resolved outgoing links."""
    return operations.get_concept(await _root(bundle_root, ctx), concept_id)


@mcp.tool(name="list")
async def list_(
    ctx: Context,
    type: str | None = None,
    prefix: str | None = None,
    bundle_root: str | None = None,
) -> list[dict]:
    """List concepts, optionally filtered by exact `type` and/or id `prefix`."""
    return operations.list_concepts(await _root(bundle_root, ctx), type, prefix)


@mcp.tool()
async def read_index(
    ctx: Context,
    dir: str | None = None,
    depth: int = 1,
    bundle_root: str | None = None,
) -> list[dict]:
    """Read `_index.md` files for progressive disclosure.

    `dir` is a bundle-relative directory (root if omitted). `depth` (1-3) sets
    how many directory levels of indexes to return, breadth-first.
    """
    return operations.read_index(await _root(bundle_root, ctx), dir, depth)


@mcp.tool()
async def move(
    ctx: Context,
    from_concept_id: str,
    to_concept_id: str,
    bundle_root: str | None = None,
) -> dict:
    """Move (rename or relocate) an OKF concept to a new id.

    `from_concept_id`/`to_concept_id` are bundle-relative paths without `.md`
    (e.g. `tables/orders` -> `models/orders`). Fails if the source is missing,
    the destination already exists, or the two ids are equal. Rewrites markdown
    links so that inbound links from other concepts and the moved concept's own
    relative links stay valid, then regenerates indexes and appends a Move entry
    to `_log.md`.
    """
    return operations.move_concept(
        await _root(bundle_root, ctx), from_concept_id, to_concept_id
    )


@mcp.tool()
async def delete(
    ctx: Context,
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
    return operations.delete_concept(await _root(bundle_root, ctx), concept_id, force)


@mcp.tool()
async def reindex(ctx: Context, bundle_root: str | None = None) -> dict:
    """Regenerate every `_index.md` in the bundle from current content.

    Use this to repair indexes that have drifted -- for example after editing
    concept files directly instead of through `add`/`patch`/`move`. Rewrites all
    directory `_index.md` files; does not touch `_log.md`. Returns the
    regenerated index paths (bundle-relative) and their count.
    """
    return operations.reindex_bundle(await _root(bundle_root, ctx))


@mcp.tool()
async def describe(
    ctx: Context,
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
    return operations.describe_directory(await _root(bundle_root, ctx), dir, description)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the server tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_server.py -v`
Expected: PASS (all tests, including the new `_root` precedence and `store_root` settings tests).

- [ ] **Step 5: Run the full workspace suite for regressions**

Run: `uv run pytest -q`
Expected: all pass (okf-core and okf-mcp).

- [ ] **Step 6: Smoke-test the tools/list handshake**

Run:

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
| uv run okf-mcp
```

Expected: an `initialize` result naming `okf-producer`, then a `tools/list` listing `add, patch, get, list, read_index, move, reindex, delete, describe`, none of them exposing a `ctx` property in `inputSchema`.

- [ ] **Step 7: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/server.py packages/okf-mcp/tests/test_server.py
git commit -m "feat(okf-mcp): store mode — per-project bundle roots via OKF_STORE_ROOT"
```

---

### Task 3: Documentation

**Files:**
- Modify: `packages/okf-mcp/README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the behavior delivered in Tasks 1-2. No code.
- Produces: user-facing docs for store mode.

- [ ] **Step 1: Document store mode in the okf-mcp README**

In `packages/okf-mcp/README.md`, find the `## Configuration` section (starts at line 6). Immediately **after** the existing configuration paragraph and the JSON code block that ends with:

```
      "env": { "OKF_BUNDLE_ROOT": "/path/to/bundle" }
    }
  }
}
```

insert this new subsection:

````markdown
### Store mode (`OKF_STORE_ROOT`)

Instead of pointing at a single bundle, set `OKF_STORE_ROOT` to a base directory
and the server partitions documents into a **per-project subfolder** under it —
no per-project configuration:

```json
{
  "mcpServers": {
    "okf-producer": {
      "command": "okf-mcp",
      "env": { "OKF_STORE_ROOT": "/path/to/store" }
    }
  }
}
```

The subfolder is named `<project-basename>-<hash8>`, e.g. a project at
`/Users/you/dev/acme/web-app` resolves to `/path/to/store/web-app-3f9a1c7b/`. The
basename is the readable prefix; the 8-hex-char SHA-256 of the absolute path keeps
two same-named projects from colliding. The subfolder is created on first write.

The **project path** comes from the client's MCP `roots` capability (the first
advertised workspace folder); if the client sends no roots, the server falls back
to its working directory.

**Resolution precedence** (per call): an explicit `bundle_root` argument wins;
otherwise `OKF_STORE_ROOT` (store mode); otherwise `OKF_BUNDLE_ROOT` (single
bundle). Setting **both** `OKF_STORE_ROOT` and `OKF_BUNDLE_ROOT` is an error
(`set OKF_STORE_ROOT or OKF_BUNDLE_ROOT, not both`). `OKF_STORE_ROOT` must be an
existing directory.
````

- [ ] **Step 2: Note store mode in CLAUDE.md**

In `CLAUDE.md`, find this sentence in the `packages/okf-mcp` paragraph:

```
The bundle root comes from `OKF_BUNDLE_ROOT` (overridable per call). See
```

Replace it with:

```
The bundle root comes from `OKF_BUNDLE_ROOT` (overridable per call), or set
`OKF_STORE_ROOT` for **store mode** — a base directory the server auto-partitions
into a per-project subfolder `<project-basename>-<hash8>` (project path from the
MCP `roots` capability, cwd fallback); setting both env vars is an error. See
```

- [ ] **Step 3: Verify the docs render and cross-check the claims**

Run: `uv run pytest packages/okf-mcp -q`
Expected: still all pass (docs-only change; confirms nothing else broke).

Manually confirm the README precedence wording matches the `_root` implementation in `server.py` (arg > store > bundle; both-set error).

- [ ] **Step 4: Commit**

```bash
git add packages/okf-mcp/README.md CLAUDE.md
git commit -m "docs(okf-mcp): document store mode (OKF_STORE_ROOT)"
```

---

## Notes for the implementer

- **`_env_file=None` in tests:** `Settings(_env_file=None)` disables `.env` reading so store-mode tests are deterministic regardless of any `.env` in the working directory.
- **`ctx: Context` first, always:** every tool wrapper takes `ctx` as its first parameter. It is injected by FastMCP and excluded from the client-facing schema (verified). Do not give it a default.
- **Do not touch `operations.resolve_bundle_root`:** legacy and per-call-arg behavior must stay byte-for-byte identical; store mode is additive.
- **The store root must pre-exist:** only the per-project subfolder is auto-created. This is intentional (typo protection).
