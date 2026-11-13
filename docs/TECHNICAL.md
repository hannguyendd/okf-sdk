# The boring page

> Okie: "You came here on purpose? Fine. Here's how the sausage is made."

This is the technical side of **OK, Fine Memory**. The fun version is the
[README](../README.md).

- [What's in the box](#whats-in-the-box)
- [Words we use](#words-we-use)
- [Run it](#run-it)
- [Connect an AI agent (MCP)](#connect-an-ai-agent-mcp)
- [Search](#search)
- [Develop](#develop)
- [Where things live on disk](#where-things-live-on-disk)
- [Design docs](#design-docs)

---

## What's in the box

`okf-sdk` is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
of [Open Knowledge Format](../packages/okf-core/CONFORMANCE.md) (OKF) tooling.
The root `pyproject.toml` is a virtual workspace root; packages live under `packages/`.

| Package | What it is | Stack |
|---|---|---|
| [`okf-core`](../packages/okf-core/) | Library: read, index and validate OKF bundles (`OKFDocument`, `Bundle`, `regenerate_indexes`, `validate_bundle`), workspaces (`WorkspaceRegistry`), and the `Storage` interface. | Python 3.12, PyYAML only |
| [`okf-mcp`](../packages/okf-mcp/) | MCP server for agents: add, patch, move, delete, get and list concepts; describe directories; reindex; create and describe bundles; semantic search. | `mcp` (FastMCP), `pydantic-settings` |
| [`okf-web`](../packages/okf-web/) | Local HTTP API (Starlette) over `okf_mcp.operations`, plus the original React UI. | Starlette, React, Bun |
| [`okf-web2`](../packages/okf-web2/) | **OK, Fine Memory**: the notebook-doodle UI, served by `okf-web --static`. | Vite, React 19, wouter, TanStack Query, Tailwind v4, rough.js |

`okf-web2` is bun-only (no `pyproject.toml`), so the uv workspace excludes it.

## Words we use

| Word | Means |
|---|---|
| **Concept** | One markdown file with YAML frontmatter (`type` is required). One unit of knowledge: a service, a decision, a recipe. |
| **Bundle** / **index** / **notebook** | A folder of concepts. The UI calls it a notebook; MCP and the API call it a bundle. |
| **Workspace** | A named folder of bundles under `$OKF_HOME/workspaces/<name>`, with metadata in `.okf/workspace.json`. |
| **`_index.md`** | The generated *directory listing* in every folder. Regenerated after each write. |
| **`_log.md`** | An append-only change log per directory. |

The rules a valid bundle follows are in
[`packages/okf-core/CONFORMANCE.md`](../packages/okf-core/CONFORMANCE.md).

## Run it

Needs [uv](https://docs.astral.sh/uv/) and [Bun](https://bun.sh/).

```bash
uv sync                                   # Python side
cd packages/okf-web2 && bun install && bun run build && cd -
uv run okf-web --static packages/okf-web2/dist
# open http://127.0.0.1:8765
```

`okf-web` options:

| Flag | Default | What it does |
|---|---|---|
| `--static DIR` | the bundled `okf-web` UI | serve a built frontend (e.g. `packages/okf-web2/dist`) |
| `--port PORT` | `8765` | port |
| `--host HOST` | `127.0.0.1` | bind address. **There is no auth**; keep it local. |
| `--read-only` | off | disable every write endpoint |

Environment:

| Variable | Default | What it does |
|---|---|---|
| `OKF_HOME` | `~/.okf` | where workspaces live |
| `OKF_EMBEDDING_URL` / `OKF_EMBEDDING_MODEL` | unset | an OpenAI-compatible embeddings server; enables search |

Frontend development with hot reload:

```bash
uv run okf-web                           # API on 8765
cd packages/okf-web2 && bun run dev      # UI on 5173, proxies /api to 8765
# OKF_API=http://127.0.0.1:9000 bun run dev   # point the proxy elsewhere
```

The landing page is a second Vite entry (`landing.html` → `src/landing/`).
In dev open `http://localhost:5173/landing.html`; `bun run build` writes
`dist/landing.html`, which `okf-web --static` serves at `/landing.html`.

Add `?intro` to the app URL to replay the opening animation (it plays once per tab,
and never under `prefers-reduced-motion`).

## Connect an AI agent (MCP)

Agents write into the same notebooks you browse. With Claude Code:

```bash
claude mcp add okf-producer --scope project \
  --env OKF_WORKSPACE=team \
  -- /path/to/okf-sdk/.venv/bin/okf-mcp
```

Or in any MCP client config:

```json
{
  "mcpServers": {
    "okf-producer": {
      "command": "/path/to/okf-sdk/.venv/bin/okf-mcp",
      "env": { "OKF_WORKSPACE": "team", "OKF_BUNDLE": "handbook" }
    }
  }
}
```

Each tool resolves its workspace and bundle in this order: tool argument >
`X-OKF-Workspace` / `X-OKF-Bundle` header (HTTP transport) > `OKF_WORKSPACE` /
`OKF_BUNDLE` env > the choice made earlier in the session > the only candidate,
or the user is asked. Full details, the HTTP transport and the tool list:
[`packages/okf-mcp/README.md`](../packages/okf-mcp/README.md).

## Search

Search is semantic: it embeds each folder's `_index.md` listing and each bundle
description through a local OpenAI-compatible embeddings server, stored in the
workspace's `.okf/vectors.db` (sqlite-vec) and synced lazily at search time.
Without `OKF_EMBEDDING_URL` and `OKF_EMBEDDING_MODEL`, search is off and Okie
naps on the search page.

## Develop

```bash
uv sync                                  # shared .venv with every member + dev group
uv run pytest                            # all Python tests
uv run pytest packages/okf-core/tests/test_bundle.py -v

cd packages/okf-web2
bun run test                             # Vitest + MSW (in-memory fake API)
bun run typecheck
bun run build
```

- All bundle file access goes through `okf_core.Storage` (`LocalStorage` by
  default, `MemoryStorage` in tests). Don't use `pathlib` on bundle files.
- Tests must set `OKF_HOME` or pass `root=`; never touch the real home folder.
- Add a Python package under `packages/<name>/` with its own `pyproject.toml`;
  the workspace members glob picks it up.
- Runtime deps: `uv add --package okf-core <pkg>`; dev deps: `uv add --dev <pkg>`.

### okf-web2 layout

```
packages/okf-web2/
├── index.html, landing.html   two Vite entries (app, landing page)
├── src/
│   ├── pages/                 one file per route (wouter, hash routes)
│   ├── components/            Tree (explorer), Dialogs, Crumbs, Intro, ThemeToggle…
│   ├── doodle/                rough.js drawing primitives: Sketch, Btn, Mark, Okie…
│   ├── lib/                   api client, TanStack Query hooks, route scope, accent colour
│   ├── landing/               the landing page
│   ├── assets/                generated PNG doodles (Okie, icons, decor, landing art)
│   └── test/                  MSW fake backend + setup
└── brand/                     BRAND.md, brand board, logo files
```

Brand, voice and asset rules: [`packages/okf-web2/brand/BRAND.md`](../packages/okf-web2/brand/BRAND.md).
How the art is generated: [`packages/okf-web2/ASSETS_PROMPT.md`](../packages/okf-web2/ASSETS_PROMPT.md).

## Where things live on disk

```
~/.okf/workspaces/
└── team/                        a workspace
    ├── .okf/
    │   ├── workspace.json       bundle descriptions + the workspace's crayon colour
    │   └── vectors.db           search index
    └── handbook/                a bundle (notebook)
        ├── _index.md            generated listing
        ├── _log.md              change log
        ├── welcome.md           a concept
        └── services/
            ├── _index.md
            └── payments-api.md
```

Everything is plain markdown. You can open it in any editor, commit it to git,
or grep it. Okie won't be offended. (Okie will be a little offended.)

## Design docs

- [Indexing library](superpowers/specs/2026-06-25-okf-core-indexing-library-design.md)
- [Conformance rules](superpowers/specs/2026-06-26-okf-conformance-rules-design.md)
- [MCP producer](superpowers/specs/2026-06-29-okf-mcp-producer-design.md)
- [Workspaces](superpowers/specs/2026-10-18-okf-core-workspace-design.md)
- [Storage interface](superpowers/specs/2026-10-19-okf-storage-interface-design.md)
- [Vector search](superpowers/specs/2026-10-19-okf-mcp-vector-search-design.md)
- [Web UI](superpowers/specs/2026-10-25-okf-web-ui-design.md)
- [Workspace targeting](superpowers/specs/2026-10-26-okf-workspace-targeting-design.md)
