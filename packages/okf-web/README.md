# okf-web

Local web UI for browsing, searching and managing OKF bundles: a small Starlette
HTTP API over `okf_mcp.operations` plus a React (Bun + TypeScript + Tailwind) frontend.
Design: `docs/superpowers/specs/2026-10-25-okf-web-ui-design.md`.

## Run

```bash
cd packages/okf-web/frontend && bun install && bun run build  # once: builds into src/okf_web/static
uv run okf-web --bundle-root ./memory                       # http://127.0.0.1:8765
```

Root selection matches okf-mcp: `--bundle-root` / `OKF_BUNDLE_ROOT`, or store mode
(`OKF_STORE_ROOT`, project from `--project`, default cwd). `--read-only` disables
writes. Search needs `OKF_EMBEDDING_URL` and `OKF_EMBEDDING_MODEL`. No auth: it
binds `127.0.0.1` by default; do not expose it.

## Develop / test

```bash
uv run okf-web --bundle-root ./memory        # API on 8765
cd packages/okf-web/frontend && bun run dev   # Bun dev server (HMR), proxies /api
bun test                                     #  Bun test runner; Python: uv run pytest packages/okf-web
```
