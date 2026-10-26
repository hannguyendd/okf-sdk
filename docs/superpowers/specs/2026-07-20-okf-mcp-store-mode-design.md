# okf-mcp — Store Mode Design

**Date:** 2026-07-20
**Status:** Approved (brainstorming) — ready for implementation plan
**Depends on:** `okf-mcp` producer server (§ patterns from `2026-06-29-okf-mcp-producer-design.md`); the MCP `roots` client capability
**Superseded by:** `2026-10-26-okf-workspace-targeting-design.md` — store mode and `OKF_BUNDLE_ROOT` were removed in favour of workspace + bundle targeting.

## 1. Motivation

Today the producer server edits exactly **one** bundle: `OKF_BUNDLE_ROOT` (or a
per-call `bundle_root`) names a directory, and every tool writes into it. To
author OKF docs for several code projects you must reconfigure the server (or
pass `bundle_root` on every call) as you move between them.

This spec adds a **store mode**: you configure a single base directory
(`OKF_STORE_ROOT`) once, and the server automatically partitions documents into a
**per-project subfolder** under it. The subfolder is derived from the current
project's path — a readable prefix (the project's own folder name) plus a short
hash of the absolute path for uniqueness — so one central store can hold the OKF
bundles of many projects without collisions and without per-project
configuration.

### Goals

- A new setting **`OKF_STORE_ROOT`** whose presence activates store mode.
- Automatic per-project partitioning: the effective bundle root becomes
  `<store_root>/<project-folder>`, where `<project-folder>` is
  `<project-basename>-<hash8-of-absolute-path>` (e.g. `web-app-3f9a1c7b`).
- **Zero per-project config**: the project path is discovered from the MCP
  `roots` capability, falling back to the process working directory.
- The per-project subfolder is **auto-created** on first use; a brand-new project
  just works.
- Preserve every existing behavior: legacy single-bundle mode
  (`OKF_BUNDLE_ROOT`) and the per-call `bundle_root` override are unchanged.

### Non-goals

- No folder→project-path mapping index in the store root, and no recording of the
  project path inside the bundle (both deferred; see §8).
- No migration when a project moves: a new absolute path yields a new folder; the
  old folder is orphaned in place, not moved or merged.
- No change to how bundles are read, indexed, or validated — store mode only
  changes **which directory** a tool resolves to.
- No pruning of empty per-project folders (consistent with the rest of the
  server, which never prunes directories).

## 2. Architecture

Follows the existing **thin-server-over-operations** split. Store mode touches
only bundle-root resolution; the tool bodies and all `operations.*` orchestration
are unchanged.

```
packages/okf-mcp/src/okf_mcp/
├── operations.py   # + derive_project_folder(), resolve_store_bundle_root() — pure
└── server.py       # Settings.store_root; async _root(); async tool wrappers with ctx
```

- **`operations.derive_project_folder`** and **`operations.resolve_store_bundle_root`**
  are pure, framework-agnostic functions (no MCP, no context). They compute the
  folder name and the effective bundle root from a project path. Unit-tested
  directly, like the existing `resolve_bundle_root`.
- **`server.Settings`** gains `store_root: Path | None = None` (env `OKF_STORE_ROOT`).
- **`server._root`** becomes `async` and implements the resolution precedence
  (§3). In store mode it discovers the project path via the MCP context and
  delegates the folder math to `operations`.
- **Tool wrappers** (`add`, `patch`, `get`, `list`, `read_index`, `move`,
  `delete`, `reindex`, `describe`) gain an injected `ctx: Context` parameter and
  become `async` so they can `await _root(...)`. The extra parameter is injected
  by FastMCP and is invisible to clients — the tool schemas are unchanged.

## 3. Bundle-root resolution

`server._root(bundle_root: str | None, ctx: Context) -> Path` resolves the
effective bundle root for a call. Precedence, in order:

1. **Explicit `bundle_root` arg** → `operations.resolve_bundle_root(bundle_root, None)`.
   The per-call override always wins — even over a misconfigured env — and is the
   escape hatch for both modes.
2. **Both `OKF_STORE_ROOT` and `OKF_BUNDLE_ROOT` set** →
   `ValueError("set OKF_STORE_ROOT or OKF_BUNDLE_ROOT, not both")`. Ambiguous
   configuration is rejected rather than silently preferring one.
3. **`OKF_STORE_ROOT` set** (store mode) → discover the project path
   (§4), then `operations.resolve_store_bundle_root(store_root, project_path)`
   (§5), which returns `<store_root>/<project-folder>` and creates it.
4. **Otherwise** (legacy) → `operations.resolve_bundle_root(None, OKF_BUNDLE_ROOT)`,
   which returns `OKF_BUNDLE_ROOT` if set or raises the existing
   "no bundle root" error.

The "both set" check (step 2) fires only when falling back to the environment;
an explicit `bundle_root` arg (step 1) short-circuits it, so the override stays
usable regardless of env state.

## 4. Project-path discovery (`server.py`)

`_project_root(ctx: Context) -> Path` returns the current project directory:

1. `result = await ctx.session.list_roots()` — request the client's advertised
   workspace roots via the MCP `roots` capability.
2. Take the **first** root and convert its `file://` URI to a filesystem `Path`
   (via a small `_uri_to_path` helper using `urllib.parse` / `url2pathname`, so
   percent-encoding and platform path separators are handled).
3. **Fallback:** if `list_roots()` raises (client lacks the capability), returns
   no roots, or the first root has no usable `file://` path, return `Path.cwd()`.

Only the first root is used; multi-root workspaces resolve to their first
advertised folder. The result is passed to `resolve_store_bundle_root`, which
resolves it to an absolute path before deriving the folder name.

## 5. Folder-name derivation (`operations.py`)

Two pure functions, no MCP dependency.

### 5.1 `derive_project_folder`

```python
def derive_project_folder(project_path: str | Path) -> str
```

Compute the per-project subfolder **name** from a project path:

1. `p = Path(project_path).resolve()` — normalize (absolute, symlinks resolved),
   so the hash is stable regardless of how the path was expressed.
2. `base = _slug(p.name) or "project"` — the readable prefix. `_slug` maps any run
   of characters outside `[A-Za-z0-9._-]` to a single `-` and trims leading/
   trailing `-`. An empty basename (e.g. filesystem root `/`) falls back to the
   literal `project`.
3. `digest = hashlib.sha256(p.as_posix().encode("utf-8")).hexdigest()[:8]` — 8 hex
   chars of the absolute POSIX path, for uniqueness.
4. Return `f"{base}-{digest}"` (e.g. `web-app-3f9a1c7b`).

Properties:

- **Deterministic** — the same absolute path always yields the same name.
- **Collision-free across same-basename projects** — two projects both named
  `web-app` at different absolute paths hash differently, so they never share a
  folder.
- **Path-move behavior** — relocating a project changes its absolute path and thus
  its folder; the old folder is orphaned (documented, not handled).

### 5.2 `resolve_store_bundle_root`

```python
def resolve_store_bundle_root(store_root: str | Path, project_path: str | Path) -> Path
```

1. `store = Path(store_root).resolve()`; raise `ValueError` if it is not an
   existing directory (fail fast on a misconfigured `OKF_STORE_ROOT`, mirroring
   `resolve_bundle_root`'s directory check).
2. `root = store / derive_project_folder(project_path)`.
3. `root.mkdir(parents=True, exist_ok=True)` — auto-create the per-project
   subfolder on first use.
4. Return `root`.

The store root itself must pre-exist (typo protection); only the per-project
subfolder is created automatically.

## 6. Error handling

Preconditions raise `ValueError` with actionable messages (FastMCP surfaces them
as tool errors):

- **Both env roots set** — `set OKF_STORE_ROOT or OKF_BUNDLE_ROOT, not both`
  (raised in `_root`, step 2).
- **`OKF_STORE_ROOT` missing or not a directory** — raised by
  `resolve_store_bundle_root`.
- **Neither env root nor arg** — the existing "no bundle root" error from
  `resolve_bundle_root`.

`list_roots()` failures are **not** errors: they are caught and fall back to the
working directory (§4). This keeps store mode usable with clients that do not
implement the `roots` capability.

## 7. Testing (TDD)

**`okf-mcp` — pure operations (against `tmp_path`):**

- `derive_project_folder`: deterministic for a fixed path; `<slug>-<hash>` shape
  (8 hex chars); two different absolute paths sharing a basename produce different
  names; unsafe characters in the basename are slugified; an empty/root basename
  falls back to `project-<hash>`.
- `resolve_store_bundle_root`: returns `<store>/<derived-name>` and creates the
  subfolder (`is_dir()` afterwards); a nonexistent or non-directory store root
  raises `ValueError`; the subfolder name matches `derive_project_folder`.

**`okf-mcp` — resolution precedence (`server._root`):**

- explicit `bundle_root` arg wins even when both env roots are set;
- both env roots set (no arg) → `ValueError`;
- `OKF_STORE_ROOT` only → resolves to `<store_root>/<derived-folder>` using a
  fake session whose `list_roots()` returns a stub `file://` root;
- empty/failed `list_roots()` → falls back to `Path.cwd()`;
- `OKF_BUNDLE_ROOT` only → unchanged legacy behavior;
- neither → the existing "no bundle root" error.

**`test_server.py`:** the existing smoke tests (`list_tools`, `Settings` dotenv)
still pass; add a `Settings` test that `OKF_STORE_ROOT` populates `store_root`.

## 8. Housekeeping & deferred work

- Update `packages/okf-mcp/README.md`: document `OKF_STORE_ROOT`, the resolution
  precedence, folder naming, roots-based discovery, and the "both set" error.
- Update the root `CLAUDE.md` "Project status" okf-mcp summary to note store mode.
- **Deferred (YAGNI):** a `_projects` mapping index in the store root (folder →
  project path) for human discoverability, and recording the originating project
  path inside the bundle. Either can be added later without changing this design.
