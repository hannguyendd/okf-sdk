# OpenWiki Reference

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

`okf-sdk` is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
of Open Knowledge Format tooling. The root `pyproject.toml` is a **virtual**
workspace root (no `[project]` of its own); packages live under `packages/*`.

The model is **workspace + nodes**. A workspace is one OKF bundle (in the spec's
sense) on disk; a *node* is a directory or a concept, addressed by a path
relative to the workspace root. There is no bundle or index level below the
workspace: top-level directories are ordinary directories. "Bundle" survives
only as the OKF *spec* term. The uv workspace has four Python members (core,
backend, mcp, claude) plus the bun-only portal (`okf-web`).

**`packages/okf-core`** — a library for
reading, indexing, and validating OKF bundles (`OKFDocument`, `Bundle`,
`regenerate_indexes`, `validate_bundle`). Its only runtime dependency is PyYAML.
See `docs/superpowers/specs/2026-06-25-okf-core-indexing-library-design.md` for
the indexing-library design and
`docs/superpowers/specs/2026-06-26-okf-conformance-rules-design.md` plus
`packages/okf-core/CONFORMANCE.md` for the conformance rules the validator
checks.

`okf_core.workspace` adds the **workspace** concept (`WorkspaceRegistry`,
`Workspace`, `okf_home`): named directories under `~/.okf/workspaces/<name>`
(home overridable via `OKF_HOME`), each one OKF bundle (`Workspace.load()`
returns it, `.okf/` excluded) plus a hidden `.okf/` metadata folder:
`.okf/workspace.json` is `{"version": 2, "color"?}` (reading version 1 fails
and points to `okf-migrate-v2`) and `.okf/vectors.db` is the workspace's search
index. Concept ids, `/abs/link.md` links and `_index.md` placement are relative
to the workspace root. Directory descriptions live in each directory's
`_index.md` `description`; the workspace's description is the root
`_index.md`'s. `okf_core.export_subtree(storage, path, dest)` copies a
directory out as a standalone bundle (rewriting absolute links) and
`map_absolute_links` rewrites links. Workspaces use the shared `Storage`
interface; creation does not `git init`. Tests must pass `root=`/set
`OKF_HOME` — never touch the real home. See
`docs/superpowers/specs/2026-10-18-okf-core-workspace-design.md` and
`docs/superpowers/specs/2026-11-18-okf-remove-bundles-and-package-split-design.md`
(which supersedes its bundle parts). Glossary: `_index.md` is a *directory
listing*; *index* and *bundle* no longer name a top-level directory.

**`packages/okf-backend`** — the shared backend: `okf_backend.operations`
(add, patch, move, delete, describe, mkdir, reindex, get/list/read_index),
semantic search (embeddings + sqlite-vec in `.okf/vectors.db`, synced lazily
at search time), `BackendSettings` (`OKF_EMBEDDING_*`; env > `./.env` >
`<OKF_HOME>/.env`), and the Starlette REST
API under `/api/workspaces/{ws}/...` (no index segment: `concepts/...`,
`dirs/...`, `search?paths=`, `color`). Run: `uv run okf-backend [--read-only]
[--host] [--port 8765] [--static DIR]` (binds 127.0.0.1, no auth). It also
ships `okf-migrate-v2 [--dry-run]`, which upgrades bundle-era workspaces to
version 2 (rewrites links, moves descriptions and `okf_version`, drops
`vectors.db`; idempotent).

**`packages/okf-mcp`** — a producer MCP server (official `mcp` SDK / FastMCP)
that is a thin adapter over `okf_backend.operations`, **one workspace per
server**: `okf-mcp --workspace <name>` (stdio, required) or
`okf-mcp --transport streamable-http` with the `X-OKF-Workspace` header on
every request (`--workspace` with http is an error). There is no elicitation
and no `workspace`/`bundle` tool argument; configure several servers for
several workspaces. Tools: `add`, `patch`, `get`, `list`, `read_index`
(progressive disclosure), `move`, `delete`, `reindex` (regenerate all
`_index.md` to repair drift), `describe` (set/clear a directory's authored
`description` in its `_index.md`), `mkdir` (create an empty directory), and
`search(query, top_k, paths)` (semantic search over `_index.md` files via a
local OpenAI-compatible embedding server; `paths` is a list of directory
prefixes). Write tools re-index and append a directory-scoped `_log.md` entry
after each write; results echo `{"workspace": name}`. See
`docs/superpowers/specs/2026-11-18-okf-remove-bundles-and-package-split-design.md`
(supersedes the old workspace-targeting design),
`docs/superpowers/specs/2026-06-29-okf-mcp-producer-design.md`, and
`docs/superpowers/specs/2026-10-19-okf-mcp-vector-search-design.md`.

**`packages/okf-web`** — "OK, Fine Memory", the **Memory portal**: Vite +
React 19 + wouter (hash routes) + TanStack Query + Radix Dialog +
react-hook-form + sonner, drawn with rough.js / rough-notation on a
lined-notebook theme. It consumes the okf-backend REST API and is scoped to
workspaces (no index picker): routes `#/`, `#/w/:ws/`, `#/w/:ws/d/<dir>`,
`#/w/:ws/c/<id>`, `#/w/:ws/search/<q>`. It is bun-only (no `pyproject.toml`),
so the root uv workspace excludes it. Dev: `bun run dev` (proxies `/api` to
`okf-backend` on 8765); prod: `bun run build` then
`uv run okf-backend --static packages/okf-web/dist`. Tests: `bun run test`
(Vitest + MSW). Brand and voice: `packages/okf-web/brand/BRAND.md`. A second
Vite entry, `landing.html` (`src/landing/`), is the marketing page;
`okf-backend --static` serves it at `/landing.html`. The root `README.md` is
the fun, Okie-voiced intro; technical docs live in `docs/TECHNICAL.md`.
Workspaces carry an optional crayon `color` in `.okf/workspace.json`
(`Workspace.color()`/`set_color()`, `okf_core.WORKSPACE_COLORS`); empty
directories are created with `operations.create_directory` (writes the
directory's `_index.md`).

**`packages/okf-claude`** — Claude Code integration (`okf-claude` CLI):
`setup --workspace <ws> [--workspace <ws2> ...] [--episodes <ws>] [--no-create]
[--scope local|project|user]` and `uninstall` register one MCP server per
workspace (`okf` for a single workspace, `okf-<ws>` for several; naming in
`okf_claude.servers`), write SessionStart/SessionEnd hooks into a Claude
Code settings file, and copy the `/okf-remember` and `/okf-recall` slash
commands. SessionStart injects the root `_index.md` (workspace description +
top-level listing, so the agent can judge whether the memory is relevant) of
each workspace, guidance, and recent **episodes** from the episodes workspace
(first `--workspace` unless `--episodes`); SessionEnd
spawns a detached `claude -p` summarizer that writes an
`episodes/<date>-<session8>` concept (type `episode`) at the workspace root.
Hooks never fail a session — errors go to `<OKF_HOME>/logs/okf-claude.log`;
`OKF_CLAUDE_CHILD=1` stops recursion. Prompts live in
`src/okf_claude/prompts/`. Entry script: `scripts/setup-claude-code.sh`. See
`docs/superpowers/specs/2026-11-13-okf-claude-code-integration-design.md` and
`docs/superpowers/specs/2026-11-24-okf-claude-multi-workspace-design.md`.

**Storage.** All file access in every package goes through the
`okf_core.Storage` interface (`read_text`/`write_text`/`delete`/`move`/
`list_dir`/`iter_files`/`mkdir`/`lock`, workspace-relative POSIX keys).
`LocalStorage` is the default, `MemoryStorage` the test double; other backends
plug in via `register_backend` or the `okf_core.storage` entry-point group
(optional extras — core stays PyYAML-only).
`WorkspaceRegistry(root=...)` accepts a path or a `Storage`. Don't
do `pathlib` I/O on workspace files directly; go through a `Storage`. See
`docs/superpowers/specs/2026-10-19-okf-storage-interface-design.md`.

## Tooling

This is a [uv](https://docs.astral.sh/uv/)-managed workspace targeting Python 3.12 (pinned in `.python-version`). The shared `.venv`, lockfile (`uv.lock`), and dev dependency group live at the root; each member package carries its own `[project]` metadata.

## Commands

- `uv sync` — create/update the shared `.venv` with all workspace members (installed editable) plus the dev dependency group
- `uv run pytest` — run the full test suite (config in the root `pyproject.toml`)
- `uv run pytest packages/okf-core/tests/test_bundle.py::test_load_collects_concepts_excluding_index -v` — run a single test
- `uv add --package okf-core <package>` — add a runtime dependency to the okf-core member
- `uv add --dev <package>` — add a dev dependency to the workspace root
