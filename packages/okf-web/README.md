# okf-web

Local web UI for browsing, searching and managing OKF bundles: a small Starlette
HTTP API over `okf_mcp.operations` plus a React (Bun + TypeScript + Tailwind) frontend.
Design: `docs/superpowers/specs/2026-10-25-okf-web-ui-design.md`.

## Run

```bash
cd packages/okf-web/frontend && bun install && bun run build  # once: builds into src/okf_web/static
uv run okf-web --workspace team --bundle notes             # http://127.0.0.1:8765
```

It serves one bundle of a workspace under `OKF_HOME` (default `~/.okf`):
`--workspace` / `--bundle`, else `OKF_WORKSPACE` / `OKF_BUNDLE`, else the only
one there is (otherwise it exits listing the choices). The header shows the
bundle's description, which you can edit there. `--read-only` disables writes,
including that edit. Search needs `OKF_EMBEDDING_URL` and `OKF_EMBEDDING_MODEL`. No auth: it
binds `127.0.0.1` by default; do not expose it.

## Develop / test

```bash
uv run okf-web --workspace team --bundle notes  # API on 8765
cd packages/okf-web/frontend && bun run dev   # Bun dev server (HMR), proxies /api
bun test                                     #  Bun test runner; Python: uv run pytest packages/okf-web
```
