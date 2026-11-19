# Remove bundles, one workspace per MCP server, package split — Design

**Date:** 2026-11-18
**Status:** Draft. Decisions in §2 were made by the user on 2026-11-18.
**Packages:** all (okf-core, okf-mcp, okf-web, okf-web2, okf-claude); adds
okf-backend.
**Supersedes:** the bundle parts of
`2026-10-18-okf-core-workspace-design.md`, and all of
`2026-10-26-okf-workspace-targeting-design.md` (targeting, bundle descriptions,
the bundle search filter).

## 1. Intent

The product has three nested concepts: **workspace → bundle → nodes**. A bundle
is just a top-level directory that has extra metadata and its own name, and the
name isn't even used consistently: core calls it *index*, MCP and web call it
*bundle*. Choosing a bundle adds a second targeting step to every MCP tool, an
extra URL segment in the web API, and a second description store next to
`_index.md`.

After this change there are two concepts:

- **Workspace**: one OKF bundle on disk (in the spec's sense), plus `.okf/`
  metadata.
- **Node**: a directory or a concept, addressed by a path relative to the
  workspace root.

The packages are also split so that each one does one job (§6).

## 2. Decisions

1. **Remove bundles as a concept.** Top-level directories are ordinary
   directories. "Bundle" stays only as the OKF *spec* term for the on-disk
   unit, which is now the workspace.
2. **One MCP server = one workspace.** The workspace is fixed when the server
   is configured:
   - **stdio**: the `--workspace <name>` command-line parameter (required).
   - **streamable-http**: the `X-OKF-Workspace` request header (required on
     every request).
   An agent that needs several workspaces gets several MCP servers configured.
3. **Remove every leftover bundle setting**: `OKF_BUNDLE`, `--bundle`,
   `X-OKF-Bundle`, the `bundle`/`bundles` tool arguments, and the `bundles` map
   in `.okf/workspace.json`.
4. **Split the packages** into core / backend / mcp / web (§6).

## 3. Non-goals

- No backward compatibility for the removed variables or tool arguments. A
  one-time migration script handles data (§7). Nothing translates old
  configurations.
- No workspace create, rename, or delete over MCP (unchanged).
- No authentication on HTTP (unchanged: binds 127.0.0.1).

## 4. Data model (okf-core)

- `Workspace` loses `indexes()`, `create_index()`, `bundle_storage()`,
  `index_root()`, `load_index()`, `description()`/`set_description()`, and
  `bundles_info()`.
- `Workspace` gains `load() -> Bundle` (the whole workspace, `.okf/` excluded)
  and keeps `storage`, `path`, `meta_storage()`, `color()`/`set_color()`.
- `.okf/workspace.json` becomes `{"version": 2, "color"?: "<crayon>"}`.
  Reading version 1 fails with a message that points to the migration script.
- Concept IDs, `/abs/link.md` links, `_index.md` placement, and `okf_version`
  are all relative to the **workspace root**. Hidden `.`/`_`-prefixed
  top-level entries (`.okf/`, `_log.md`, …) follow the existing skip rules.
- Directory descriptions live in each directory's `_index.md` `description`
  frontmatter. This was already true and is now the only place they live.
- New `okf_core.export_subtree(storage, path, dest)` copies a directory out as
  a standalone OKF bundle and rewrites its absolute links to start from the new
  root. This replaces "ship one bundle as a git repo".

## 5. MCP (okf-mcp)

### Targeting

`okf_mcp/target.py` is deleted. That removes elicitation, per-session picks,
and the env/header/argument precedence chain. The server resolves the workspace
like this:

| Transport | Source | Missing / unknown |
|---|---|---|
| stdio | `--workspace` parameter, read once at startup | Exit at startup with the list of existing workspaces |
| streamable-http | `X-OKF-Workspace` header, read on each request | That tool call fails with the list of existing workspaces |

`--workspace` together with `--transport streamable-http` is an error, so a
setting is never silently ignored. `OKF_WORKSPACE` is removed: the parameter is
the only way to set it on stdio.

### Tools

- **Removed:** `list_workspaces`, `list_bundles`, `create_bundle`,
  `describe_bundle`, and the `workspace`/`bundle` arguments on every tool.
- **Changed:** `search(query, top_k, paths: list[str] | None)`: `paths` is a
  list of directory prefixes that replaces both `bundles` and `dir` (one prefix
  does what `dir` did). Hits are `{kind: "index", dir, path, score, excerpt}`,
  and bundle-description hits are gone.
- **Added:** `mkdir(dir, description?)` creates an empty directory (wraps
  `operations.create_directory`). It replaces `create_bundle`.
- `add`, `patch`, `get`, `list`, `read_index`, `move`, `delete`, `reindex`,
  and `describe` keep their shapes, take workspace-relative paths, and echo
  `{"workspace": <name>}` in their results.

## 6. Packages

```
okf-core      OKF format (document, _index, links, validate, export_subtree),
              the Storage interface + LocalStorage/MemoryStorage, Workspace and
              WorkspaceRegistry. Runtime deps: PyYAML only.
okf-backend   NEW. operations (add/patch/move/delete/describe/mkdir/reindex),
              search (embeddings + sqlite-vec vector store), Settings
              (pydantic-settings, OKF_EMBEDDING_*), and the REST API (today's
              okf_web.app + server, CLI `okf-backend`). Storage plugins are
              extras, e.g. `okf-backend[s3]`, registered through the
              `okf_core.storage` entry-point group.
okf-mcp       Thin FastMCP adapter: tools call okf_backend.operations in-process.
              Transports: stdio, streamable-http. Depends on okf-backend.
okf-web       The "Memory portal": today's okf-web2 moved here (bun only, no
              pyproject). Consumes the okf-backend REST API.
okf-claude    Depends on okf-backend (for operations) instead of okf-mcp.
```

What moves where:

| From | To |
|---|---|
| `okf_mcp/operations.py`, `embeddings.py`, `vector_store.py` | `okf_backend/` |
| `okf_mcp/server.py` `Settings` | `okf_backend/settings.py` |
| `okf_web/app.py`, `okf_web/server.py` | `okf_backend/api.py`, `okf_backend/server.py` |
| `packages/okf-web2/*` | `packages/okf-web/*` |
| `packages/okf-web/frontend` (old UI) | deleted |

The `okf-web` command becomes `okf-backend` (`--static <dir>` serves the
portal build, `--read-only`).

### REST API

The `/indexes/{index}` segment is removed:

```
GET  /api/info
GET  /api/workspaces                      POST /api/workspaces
PUT  /api/workspaces/{ws}/color
     /api/workspaces/{ws}/concepts/...    (was …/indexes/{index}/concepts/...)
     /api/workspaces/{ws}/dirs/...        GET  /api/workspaces/{ws}/search?paths=
```

The portal drops its index picker and `IndexLayout` and gets a workspace-level
tree. Index descriptions are edited as root-directory descriptions.

## 7. Migration

`uv run okf-migrate-v2 [--dry-run]` runs over `$OKF_HOME/workspaces/*`. For
each workspace:

1. Rewrite absolute links in every concept from `/x.md` to `/<old-bundle>/x.md`.
   Relative links stay as they are.
2. Copy each bundle description from `workspace.json` into
   `<old-bundle>/_index.md` `description` when that `_index.md` has none.
   Otherwise report the conflict and keep the `_index.md` text.
3. Move `okf_version` from each `<old-bundle>/_index.md` to the root
   `_index.md`. Use the highest version found, and warn if they differ.
4. Write `workspace.json` version 2 (keep `color`), delete `.okf/vectors.db`
   (it is rebuilt lazily), and run `reindex` on the workspace.

The script is idempotent: a workspace already at version 2 is skipped.

## 8. okf-claude

- `setup --workspace <ws> [--create]`: `--bundle` is removed. It registers
  `claude mcp add okf -- okf-mcp --workspace <ws>`, with no `OKF_*` target env.
- Episodes are written to `episodes/<date>-<session8>` at the workspace root.
- SessionStart reads recent episodes from the same place.

## 9. Config files

- `packages/okf-mcp/.env.example`, the root `.env.example`, and
  `packages/okf-web/frontend/.env.example`: remove `OKF_WORKSPACE`,
  `OKF_BUNDLE`, and the "default target" block. Keep `OKF_EMBEDDING_*`. The
  embedding settings move to an `okf-backend/.env.example`.
- `CLAUDE.md`, `docs/TECHNICAL.md`, `README.md`: replace bundle/index wording
  with workspace + node, and update the package list.

## 10. Rollout

Two PRs, so that each diff can be reviewed on its own:

1. **Package split** (mechanical): create okf-backend, move the modules, move
   web2 to okf-web, and delete the old frontend. Behaviour does not change, so
   the existing tests are the proof.
2. **Bundle removal + MCP targeting**: §4, §5, §7, §8, §9.

## 11. Testing

- core: `Workspace.load`, the v1 `workspace.json` error, `export_subtree` link
  rewriting.
- mcp: stdio without `--workspace` exits; http without the header fails the
  call; an unknown workspace lists the existing ones; `--workspace` together
  with http is an error; `search(paths=…)` filtering.
- migration: a fixture with two bundles that have absolute links, descriptions,
  and `okf_version`. Check the output and that a second run changes nothing.
- backend REST: routes without the index segment. Portal: Vitest/MSW fakes
  updated to the new routes.
- All tests use `root=` / `OKF_HOME` and never the real home.
