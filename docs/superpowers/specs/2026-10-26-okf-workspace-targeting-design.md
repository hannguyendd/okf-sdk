# Workspace-targeted MCP, bundle descriptions, workspace-wide search — Design

**Date:** 2026-10-26
**Status:** Approved by user 2026-10-26
**Packages:** okf-core, okf-mcp, okf-web

## 1. Intent

An agent connected to the okf MCP server should be able to see what knowledge
exists and choose where to read and write without anyone wiring a raw path into
its config. Concretely, it should be able to ask "workspace X has bundles A, B,
C — what is each for?", pick one, and search across them semantically.

Today the server knows nothing about workspaces. Every tool targets one bundle
picked by `OKF_BUNDLE_ROOT` / `OKF_STORE_ROOT` / a `bundle_root` argument, and
the only description is the per-directory one in `_index.md`. Workspaces
(`okf_core.workspace`) exist only as a library.

## 2. Goals

1. **Bundle descriptions.** Each bundle in a workspace has an optional short
   description saying what it is for, stored as JSON at the workspace level.
2. **Workspace + bundle targeting** replaces the old root modes everywhere
   (okf-mcp and okf-web). Every MCP tool takes optional `workspace` and `bundle`
   arguments. Defaults come from HTTP request headers or env vars. When the
   needed target is still unknown, the server **asks the user** through MCP
   elicitation.
3. **MCP exposes workspaces and bundles.** Agents can list workspaces, list
   bundles with their descriptions, create bundles, and set bundle descriptions.
4. **Workspace-wide semantic search.** One vector DB per workspace covers all
   of its bundles. Search can be filtered to a subset of bundles, and bundle
   descriptions are searchable too.

## 3. Non-goals and anti-goals

- **Agents cannot create, rename, or delete workspaces** (user decision).
  Workspaces stay a human action. MCP can create **bundles only**. Renaming
  and deleting bundles are also out of scope.
- No backward compatibility for `OKF_BUNDLE_ROOT`, `OKF_STORE_ROOT`, the
  `bundle_root` tool argument, or store-mode per-project partitioning. The user
  will update their MCP config. No migration tool. Old `<bundle>.vectors.db`
  files are simply abandoned.
- No auth on the HTTP transport. It binds 127.0.0.1 by default, like okf-web.
- No bundle switcher in the web UI (see §9). The UI does show and edit the
  served bundle's description.
- Searching concept bodies stays out of scope. Search still covers
  `_index.md` files, plus bundle descriptions.
- Anti-goal: bundle metadata must not live inside a bundle, where it would
  affect conformance or listings, or be mistaken for a bundle.

## 4. On-disk layout

```
<OKF_HOME>/workspaces/<workspace>/
├── .okf/                     # workspace metadata (hidden → never a bundle)
│   ├── workspace.json        # bundle descriptions
│   └── vectors.db            # one sqlite-vec DB for every bundle here
├── <bundle-a>/               # a bundle (== an "index" in okf-core terms)
└── <bundle-b>/
```

### `workspace.json`

```json
{
  "version": 1,
  "bundles": {
    "notes": { "description": "Team meeting notes and decisions" },
    "api":   { "description": null }
  }
}
```

- Written with `indent=2`, sorted keys, trailing newline, UTF-8.
- A missing file counts as `{"version": 1, "bundles": {}}`. It is created on
  the first write.
- A bundle directory without an entry has description `null`. An entry
  whose directory is gone is ignored on read and pruned on the next write.
- Read-modify-write happens under the workspace storage's `lock()`.
- An unknown `version`, or a file that is not valid JSON, raises a clear
  error. The server never overwrites a file it couldn't parse.

## 5. okf-core changes

- `okf_core.workspace` moves onto the shared `okf_core.Storage` interface. Its
  private Path-based `LocalStorage` class is removed, which also ends the name
  clash with `okf_core.LocalStorage`. `WorkspaceRegistry` keeps `root` (default
  `okf_home()/"workspaces"`), opens it through `open_storage`, and each
  `Workspace` uses `registry_storage.child(name)`. A bundle's storage is
  `workspace_storage.child(bundle)`.
- New `Workspace` API:
  - `bundle_storage(name) -> Storage`: storage for an existing bundle.
    Raises `FileNotFoundError` if it is absent.
  - `description(name) -> str | None`
  - `set_description(name, text: str | None)`: `None` or blank clears it. Text
    is stripped and capped at 1000 chars (`ValueError` above that). The bundle
    must exist.
  - `bundles_info() -> list[{"name", "description"}]`, sorted by name.
  - `create_index(name, description=None)` gains the optional description.
- `.okf/` is already excluded from `indexes()` by the existing `.`/`_` prefix
  rule. Add a test that pins this.
- Tests keep using `home=` / `OKF_HOME` / `MemoryStorage`, and never the real
  home.

## 6. Target resolution (okf-mcp)

Each tool call resolves a `workspace` and, when the tool needs one, a `bundle`:

1. the tool argument (`workspace=`, `bundle=`), else
2. the HTTP request header `X-OKF-Workspace` / `X-OKF-Bundle` (streamable-HTTP
   transport only; read from the request on the FastMCP context), else
3. the env var `OKF_WORKSPACE` / `OKF_BUNDLE` (via `Settings`), else
4. **ask**:
   - Workspace unresolved: if exactly one workspace exists, use it. Otherwise
     call `ctx.elicit` with the workspace names as choices.
   - Bundle unresolved, for a tool that needs one: if the workspace has
     exactly one bundle, use it. Otherwise elicit with the bundle names as
     choices, showing each description next to its name.
   - If the client lacks elicitation, or the user declines or cancels, the
     tool fails with a clear error that lists the available choices so the
     agent can retry with an argument.
   - If no workspace exists at all, the error says to create one (a human
     action).

**Remembered picks (user decision).** A workspace or bundle the user picks in
an elicitation prompt is remembered for the rest of that MCP session and acts
as a default from then on. The resolution order becomes arg > header > env >
remembered pick > ask. Picks are kept per session: the resolver keys them by
the FastMCP `ServerSession` object in a `WeakKeyDictionary`, so they are
dropped when the session ends. This works for both stdio and streamable-HTTP.
A remembered bundle belongs to its remembered workspace and follows the same
pair rule as the defaults below. An auto-pick (only one candidate) is not
remembered, because it is recomputed for free on each call.

**Echoed target (user decision).** Every tool result names the target it
used. Concept tools that return a dict (`add`, `patch`, `get`, `move`,
`delete`, `describe`, `reindex`, `read_index`) gain top-level `workspace` and
`bundle` keys. Tools that return a list (`list`) instead return
`{workspace, bundle, items: [...]}`. `search` returns
`{workspace, bundles: [scope], hits: [...]}`. This echo happens only in the
MCP layer. The `okf_mcp.operations` return shapes do not change, so okf-web
is unaffected.

Each level resolves on its own. For example, the workspace can come from a
header while the bundle comes from an argument. A named workspace or bundle
that does not exist is an error, never a prompt. Default workspace and default
bundle act as a pair (my call): the default bundle (header or env) applies only
when the resolved workspace *is* the default workspace, or when no default
workspace is set. So `OKF_WORKSPACE=A, OKF_BUNDLE=notes` with `workspace="B"`
ignores `notes` and falls through to auto-pick / elicit, and a `search` on B
covers all of B's bundles.

The resolver returns the bundle `Storage` that the existing
`okf_mcp.operations` functions already accept, so those functions don't change
beyond removing the root-mode helpers (`resolve_store_bundle_root`,
`derive_project_folder`, `_slug`, and the `OKF_*_ROOT` handling in
`resolve_bundle_root`).

## 7. MCP tools

### Transport

`okf-mcp` gains `--transport {stdio,streamable-http}` (default `stdio`), plus
`--host` (default `127.0.0.1`) and `--port`. Headers only exist over HTTP. In
stdio mode, the env vars are the defaults.

### Existing concept tools

`add`, `patch`, `get`, `list`, `read_index`, `move`, `delete`, `describe`, and
`reindex` drop `bundle_root` and gain optional `workspace` and `bundle`. All of
them need a bundle. Their behavior is otherwise unchanged.

### New workspace/bundle tools

| Tool | Args | Returns |
|---|---|---|
| `list_workspaces` | — | `[{name, bundles: int}]`. Never elicits. |
| `list_bundles` | `workspace?` | `[{name, description}]`. Elicits the workspace if unresolved. |
| `create_bundle` | `name`, `description?`, `workspace?` | `{workspace, bundle, description}`. Creates the empty directory and records the description. (Implementation note: no root `_index.md` is seeded, because okf-core only indexes directories that contain documents; `read_index`/`list` return `[]` for an empty bundle.) `FileExistsError` if it already exists. |
| `describe_bundle` | `description` (string or null to clear), `bundle?`, `workspace?` | `{workspace, bundle, description}` |

The description of `create_bundle`/`describe_bundle` invalidates that bundle's
description vector. The next search re-embeds it.

### `search`

```
search(query, top_k=5, bundles: list[str] | None = None, dir: str | None = None,
       workspace: str | None = None)
```

- Bundle scope: explicit `bundles` if given, otherwise the default bundle
  (header/env) if set, otherwise **every bundle in the workspace**. Search
  never elicits a bundle. It does elicit the workspace when that's unresolved.
- `dir` is only allowed when the scope is exactly one bundle. Otherwise it's a
  `ValueError`.
- Each hit: `{bundle, kind, dir, path, score, excerpt}`. `kind` is `"index"`
  for an `_index.md` hit, or `"bundle"` for a bundle-description hit. A
  bundle-description hit has `dir: ""`, `path: null`, and `excerpt` set to the
  description.
- Hits from all bundles in scope are ranked together. `top_k` (1–20) applies
  to the merged list.

## 8. Vector store

- One DB per workspace at `<workspace>/.okf/vectors.db`. The `OKF_VECTOR_DB`
  override goes away. A workspace on non-local storage has no DB location and
  raises a clear `VectorStoreError` (my call: workspaces are local in
  practice).
- The existing `vectors(root, key, …)` table already partitions rows. `root`
  becomes the **bundle name** (today it's the storage location). The
  bundle-description row uses the reserved key `""`, which can't collide
  because real keys end in `_index.md`.
- Sync stays lazy and per bundle. A search syncs only the bundles in scope,
  embedding changed `_index.md` files and that bundle's description if it
  changed. Rows of bundles that no longer exist are pruned when a sync runs.
- Model/dimension metadata stays DB-wide, because hits from different bundles
  are ranked against each other and must come from the same model. A model or
  dimension change wipes **all** rows (every bundle) plus meta, then
  re-embeds the bundles in the current search's scope. Other bundles
  re-embed on their next sync, since they have no rows left. This matches
  today's whole-DB rebuild (my call: model changes are rare, so the one-time
  cost is fine, and it rules out stale vectors from an older model of the
  same dimension).
- Keep the current properties: embed outside the write transaction, one
  transaction per sync, never answer from a store that failed to sync.

## 9. okf-web

- `--bundle-root` and `--project` are replaced by `--workspace` and `--bundle`,
  falling back to `OKF_WORKSPACE` / `OKF_BUNDLE`. There's no elicitation in a
  CLI: if one is missing, use it when exactly one candidate exists, otherwise
  exit with an error listing the choices.
- The web app still serves one bundle per process (my call; a bundle switcher
  in the UI is a follow-up). Its search uses the workspace DB, scoped to that
  bundle.
- `/api/info` adds `workspace`, `bundle`, and the bundle description.
- **Showing and editing the description (user decision).** A new
  `POST /api/bundle/describe` route takes a body of `{description: string | null}`
  and calls `Workspace.set_description` for the served bundle. It's registered
  with `write=True`, so `--read-only` rejects it the same way it rejects
  `/api/describe`. It returns the same shape as `/api/info`'s bundle fields.
- Frontend: the header or root view shows `workspace / bundle` and the bundle
  description. An edit control saves through the new endpoint, matching how
  `DirView` edits a directory description today, and it's hidden when the
  server is read-only. `api.ts` and `fakeApi.ts` gain the call, and
  `App.test.tsx` covers view, edit, clear, and read-only.
- Web search includes bundle-description hits (`kind: "bundle"`, `path: null`).
  `SearchView` renders one as a link to the bundle root rather than to a
  concept or directory.

## 10. Docs and tests

- Update `CLAUDE.md`, the package READMEs, and the store-mode and
  vector-search specs' "superseded by" notes to describe the new targeting.
- Tests:
  - core workspace JSON and description behavior (`MemoryStorage` and
    `tmp_path`)
  - resolution order arg > header > env > elicit, including single-candidate
    auto-pick, decline/cancel, and no-elicitation fallback (fake `Context`)
  - each new tool
  - multi-bundle search: filtering, merged ranking, description hits, `dir`
    with multiple bundles rejected, per-bundle lazy sync, rebuild
  - okf-web CLI resolution
- Remove the store-mode and `bundle_root` tests.

## 11. Decisions

**User's:** descriptions are stored as JSON. Workspace/bundle are optional on
every tool, with header defaults, and the server asks when neither is
provided. A picked workspace/bundle is remembered for the session, and every
tool result echoes the target it used. The web UI shows and edits the bundle
description, through a write endpoint that respects `--read-only`. The old root
modes can be replaced. One vector DB for all bundles,
with a bundle filter on search. MCP can create bundles but not workspaces.

**Author's calls (open to change):**
- File locations `.okf/workspace.json` and `.okf/vectors.db`.
- Header and env names `X-OKF-Workspace`/`X-OKF-Bundle` and
  `OKF_WORKSPACE`/`OKF_BUNDLE`.
- Resolution order arg > header > env.
- Auto-pick when exactly one candidate exists.
- One DB per workspace rather than global.
- Search defaults to all bundles instead of asking.
- `dir` requires a single bundle.
- Description cap of 1000 chars.
- okf-web stays one bundle per process.
- `OKF_VECTOR_DB` removed.
- MCP and web say "bundle", while okf-core keeps its "index" method names
  (`indexes()`, `create_index`) for the same thing.
