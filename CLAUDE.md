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
visible top-level directory). Filesystem access goes through an injectable
`LocalStorage`; creation does not `git init`. Tests must pass `home=`/set
`OKF_HOME` — never touch the real home. See
`docs/superpowers/specs/2026-10-18-okf-core-workspace-design.md`. Note the
glossary rename: `_index.md` is now a *directory listing*; *index* means a
workspace's collection of concepts.

**`packages/okf-mcp`** — a producer MCP server (official `mcp` SDK / FastMCP,
plus `pydantic-settings`) for authoring bundles: tools to `add`, `patch`,
`move`, `delete`, `get`, and `list` concepts, `read_index` (progressive
disclosure), `describe` (set/clear a directory's authored `description` in its
`_index.md` frontmatter), and `reindex` (regenerate all `_index.md` to repair
drift), plus `search` (semantic search over `_index.md` files via a local
OpenAI-compatible embedding server and a sqlite-vec file kept outside the bundle;
synced lazily at search time, see
`docs/superpowers/specs/2026-10-19-okf-mcp-vector-search-design.md`). Write tools
re-index and append a directory-scoped `_log.md` entry after each write. The bundle root comes from `OKF_BUNDLE_ROOT` (overridable per call), or set
`OKF_STORE_ROOT` for **store mode** — a base directory the server auto-partitions
into a per-project subfolder `<project-basename>-<hash8>` (project path from the
MCP `roots` capability, cwd fallback); setting both env vars is an error. See
`docs/superpowers/specs/2026-06-29-okf-mcp-producer-design.md`,
`docs/superpowers/specs/2026-07-20-okf-mcp-store-mode-design.md`, and
`docs/superpowers/plans/2026-06-29-okf-mcp-producer.md`.

**`packages/okf-web`** — local web UI for browsing, searching, and managing a
bundle: a Starlette HTTP API (`okf_web.app`) that calls `okf_mcp.operations`
directly (all I/O through `Storage`), plus a React/Vite/TypeScript frontend in
`packages/okf-web/frontend` (built into the git-ignored `src/okf_web/static`
and served by the API). Run: `pnpm install && pnpm build` in the frontend
folder, then `uv run okf-web --bundle-root <dir>` (same root env vars as okf-mcp,
`--read-only`, binds 127.0.0.1, no auth). Frontend tests: `pnpm test`. See
`docs/superpowers/specs/2026-10-25-okf-web-ui-design.md`.

**Storage.** All file access in both packages goes through the
`okf_core.Storage` interface (`read_text`/`write_text`/`delete`/`move`/
`list_dir`/`iter_files`/`mkdir`/`lock`, bundle-relative POSIX keys).
`LocalStorage` is the default, `MemoryStorage` the test double; other backends
plug in via `register_backend` or the `okf_core.storage` entry-point group
(optional extras — core stays PyYAML-only). `OKF_BUNDLE_ROOT` /
`OKF_STORE_ROOT` / `bundle_root` accept a path or a `scheme://` location. Don't
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
