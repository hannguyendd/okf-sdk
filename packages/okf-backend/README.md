# okf-backend

Shared backend for OKF tooling. It holds:

- `okf_backend.operations`: add/patch/move/delete/describe/mkdir/reindex and
  get/list/read_index over a workspace (a workspace is one OKF bundle);
- `okf_backend.embeddings`, `okf_backend.vector_store` and search (embeddings
  plus sqlite-vec, stored in the workspace's `.okf/vectors.db`);
- `okf_backend.settings.BackendSettings` (`OKF_EMBEDDING_*` environment
  configuration from the environment, `./.env`, then `<OKF_HOME>/.env`; see
  `.env.example`);
- the REST API (Starlette) under `/api/workspaces/{ws}/...`, with no index or
  bundle segment: `concepts/...`, `dirs/...`, `search?paths=`, `color`.

## Run the API

```bash
uv run okf-backend [--read-only] [--host 127.0.0.1] [--port 8765] [--static DIR]
```

`--static DIR` serves a built portal (for example `packages/okf-web/dist`). There
is no auth: it binds to 127.0.0.1 by default, so keep it local. `OKF_HOME`
(default `~/.okf`) says where workspaces live.

Because there is no auth, the API refuses requests a web page could forge:
the `Host` header must be a loopback name or the `--host` address (this blocks
DNS rebinding; bind to `0.0.0.0` to turn the check off). Writes are refused
when cross-site (`Origin` differs from `Host`, or `Sec-Fetch-Site: cross-site`).
Write bodies must be `application/json`. curl and scripts that send no `Origin`
header still work.

## Migrate from the bundle era

Workspaces made before bundles were removed (version 1) are upgraded in place
by `okf-migrate-v2`:

```bash
uv run okf-migrate-v2 --dry-run   # show what would change; write nothing
uv run okf-migrate-v2             # migrate every workspace under $OKF_HOME
okf-claude setup --workspace <ws> # re-run for each project that used okf-claude
```

For each workspace it rewrites absolute links with the old bundle directory as a
prefix, moves bundle descriptions into the directories' `_index.md`, moves
`okf_version` to the root `_index.md`, writes `.okf/workspace.json` version 2
and drops `.okf/vectors.db` (rebuilt on the next search). A workspace already at
version 2 is skipped.
