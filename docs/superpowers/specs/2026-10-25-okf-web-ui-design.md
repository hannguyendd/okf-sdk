# okf-web — React web UI for browsing and managing OKF memory (design)

Status: implemented as TODO item 5. Date 2026-10-25.

## Goal

A local web app to browse a bundle's directory tree, read concepts, search, and
manage concepts (add, patch, move, delete, describe, reindex) — the same
capabilities `okf-mcp` exposes to agents, for a person.

## Decisions (own calls, easy to revisit)

| Point | Decision | Why |
|---|---|---|
| Data access | Small Starlette HTTP API in Python that calls `okf_mcp.operations` directly | Reuses write semantics (reindex, `_log.md`, link rewriting, locking) and the `Storage` interface; no second implementation, no raw pathlib I/O. Starlette/uvicorn already ship with `mcp`. |
| Where it lives | New workspace member `packages/okf-web` (`src/okf_web` API + `frontend/` Vite/React/TS app) | One package = one command to run; built assets are served by the API from `src/okf_web/static`. |
| Scope v1 | Full management, not staged | The write operations already exist and are tested; the UI is a thin layer. A `--read-only` flag disables writes (API returns 403) for safe viewing. |
| Target root | Same resolution as okf-mcp: `--bundle-root` / `OKF_BUNDLE_ROOT`, or store mode (`OKF_STORE_ROOT` + project from `--project`, default cwd). Path or `scheme://` location. | Consistent with the MCP server so both see the same memory. Workspace/index picker is out of scope (follow-up). |
| Auth / hosting | Local only: binds `127.0.0.1`, no auth | Writes are unauthenticated, so it must not be exposed. Hosting needs auth first (follow-up). |
| Search | `GET /api/search` calls `operations.search_indexes` with the okf-mcp `OKF_EMBEDDING_*` settings; unconfigured returns a clear 400 and the UI shows it | Semantic search over `_index.md` only, same as the MCP tool. |
| `okf-core` | Unchanged (PyYAML-only) | |

## HTTP API (all JSON, bundle root fixed at server start)

- `GET /api/info` → `{location, read_only, search_enabled}`
- `GET /api/tree?dir=` → `{dir, description, directories:[{name,dir,description}], concepts:[{id,type,title,description,tags}]}` — one directory level (progressive disclosure), built from `Storage.list_dir` plus each `_index.md`'s authored `description`.
- `GET /api/index?dir=&depth=` → `operations.read_index`
- `GET /api/concepts?type=&prefix=` → `operations.list_concepts`
- `GET /api/concepts/{id}` → `operations.get_concept`
- `POST /api/concepts` `{concept_id, frontmatter, body}` → add (201)
- `PATCH /api/concepts/{id}` `{frontmatter?, body?}` → patch
- `POST /api/move` `{from_concept_id, to_concept_id}` → move
- `DELETE /api/concepts/{id}?force=` → delete (`action:"blocked"` + `referenced_by` when referenced and not forced)
- `POST /api/describe` `{dir, description}` → describe
- `POST /api/reindex` → reindex
- `GET /api/search?q=&top_k=&dir=` → hits

Errors: `{"error": msg}` with 404 when the message says "not found", 403 when
read-only, 400 for other `ValueError`s.

## Frontend

React + TypeScript + Vite; tests with Vitest + Testing Library. Layout: left
pane = lazy directory tree (expand a directory fetches `/api/tree`), top bar =
search + reindex, main pane = concept view (frontmatter table, markdown body,
outgoing links; internal links navigate) or edit form, or directory view
(description, edit description, child list, "new concept here"). Markdown
rendered with `react-markdown`. Write buttons hidden when read-only.

## Run

`uv run okf-web --bundle-root ./memory` then open http://127.0.0.1:8765.
Dev: `pnpm dev` in `packages/okf-web/frontend` (Vite proxies `/api` to 8765).
Build: `pnpm build` (outputs to `src/okf_web/static`, git-ignored).
