# OpenWiki Reference

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

`okf-sdk` is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
of Open Knowledge Format tooling. The root `pyproject.toml` is a **virtual**
workspace root (no `[project]` of its own); packages live under `packages/*`.

The workspace has three members. **`packages/okf-core`** — a library for
reading, indexing, and validating OKF bundles (`OKFDocument`, `Bundle`,
`regenerate_indexes`, `validate_bundle`). Its only runtime dependency is PyYAML.
See `docs/superpowers/specs/2026-06-25-okf-core-indexing-library-design.md` for
the indexing-library design and
`docs/superpowers/specs/2026-06-26-okf-conformance-rules-design.md` plus
`packages/okf-core/CONFORMANCE.md` for the conformance rules the validator
checks.

`okf_core.workspace` adds the **workspace** concept (`WorkspaceRegistry`,
`Workspace`, `okf_home`): named directories under `~/.okf/workspaces/<name>`
(home overridable via `OKF_HOME`), each holding **indexes** (one bundle per
visible top-level directory) and a hidden `.okf/` metadata folder:
`.okf/workspace.json` stores bundle descriptions (`{"version": 1, "bundles":
{name: {description}}}`, max 1000 chars) and `.okf/vectors.db` is the
workspace's search index. Workspaces use the shared `Storage` interface;
creation does not `git init`. Tests must pass `root=`/set `OKF_HOME` — never
touch the real home. See
`docs/superpowers/specs/2026-10-18-okf-core-workspace-design.md`. Note the
glossary rename: `_index.md` is now a *directory listing*; *index* means a
workspace's collection of concepts (MCP and web call it a *bundle*).

**`packages/okf-mcp`** — a producer MCP server (official `mcp` SDK / FastMCP,
plus `pydantic-settings`) for authoring bundles: tools to `add`, `patch`,
`move`, `delete`, `get`, and `list` concepts, `read_index` (progressive
disclosure), `describe` (set/clear a directory's authored `description` in its
`_index.md` frontmatter), and `reindex` (regenerate all `_index.md` to repair
drift); workspace tools `list_workspaces`, `list_bundles`, `create_bundle`,
`describe_bundle` (no workspace creation over MCP); plus `search` (semantic
search across a workspace's `_index.md` files and bundle descriptions via a local
OpenAI-compatible embedding server and the workspace's sqlite-vec file, synced
lazily at search time, filterable by `bundles`). Write tools re-index and append
a directory-scoped `_log.md` entry after each write. Every tool targets a
**workspace + bundle** resolved by `okf_mcp.target`: tool arg > `X-OKF-Workspace`
/ `X-OKF-Bundle` header (`--transport streamable-http`) > `OKF_WORKSPACE` /
`OKF_BUNDLE` env > the pick remembered for the MCP session > the only candidate
or MCP elicitation; results echo the target. See
`docs/superpowers/specs/2026-10-26-okf-workspace-targeting-design.md` (supersedes
the old `OKF_BUNDLE_ROOT`/`OKF_STORE_ROOT` modes),
`docs/superpowers/specs/2026-06-29-okf-mcp-producer-design.md`, and
`docs/superpowers/specs/2026-10-19-okf-mcp-vector-search-design.md`.

**`packages/okf-web`** — local web UI for browsing, searching, and managing a
bundle: a Starlette HTTP API (`okf_web.app`) that calls `okf_mcp.operations`
directly (all I/O through `Storage`), plus a React/Bun/TypeScript/Tailwind frontend in
`packages/okf-web/frontend` (built into the git-ignored `src/okf_web/static`
and served by the API). Run: `bun install && bun run build` in the frontend
folder, then `uv run okf-web` (serves the workspace registry under `$OKF_HOME`
with a workspace/index picker; `--read-only`, binds 127.0.0.1, no auth). The UI
shows and edits each index's description. Frontend tests: `bun test`. See
`docs/superpowers/specs/2026-10-25-okf-web-ui-design.md`.

**Storage.** All file access in both packages goes through the
`okf_core.Storage` interface (`read_text`/`write_text`/`delete`/`move`/
`list_dir`/`iter_files`/`mkdir`/`lock`, bundle-relative POSIX keys).
`LocalStorage` is the default, `MemoryStorage` the test double; other backends
plug in via `register_backend` or the `okf_core.storage` entry-point group
(optional extras — core stays PyYAML-only). `WorkspaceRegistry(root=...)`
accepts a path or a `Storage`. Don't
do `pathlib` I/O on bundle files directly; go through a `Storage`. See
`docs/superpowers/specs/2026-10-19-okf-storage-interface-design.md`.

## Tooling

This is a [uv](https://docs.astral.sh/uv/)-managed workspace targeting Python 3.12 (pinned in `.python-version`). The shared `.venv`, lockfile (`uv.lock`), and dev dependency group live at the root; each member package carries its own `[project]` metadata.

## Commands

- `uv sync` — create/update the shared `.venv` with all workspace members (installed editable) plus the dev dependency group
- `uv run pytest` — run the full test suite (config in the root `pyproject.toml`)
- `uv run pytest packages/okf-core/tests/test_bundle.py::test_load_collects_concepts_excluding_index -v` — run a single test
- `uv add --package okf-core <package>` — add a runtime dependency to the okf-core member
- `uv add --dev <package>` — add a dev dependency to the workspace root
