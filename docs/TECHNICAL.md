# The boring page

> Okie: "You came here on purpose? Fine. Here's how the sausage is made."

This is the technical side of **OK, Fine Memory**. The fun version is the
[README](../README.md).

- [What's in the box](#whats-in-the-box)
- [Words we use](#words-we-use)
- [Run it](#run-it)
- [Connect an AI agent (MCP)](#connect-an-ai-agent-mcp)
- [Upgrading from the bundle era](#upgrading-from-the-bundle-era)
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
| [`okf-core`](../packages/okf-core/) | Library: read, index and validate OKF bundles (`OKFDocument`, `Bundle`, `regenerate_indexes`, `validate_bundle`), workspaces (`WorkspaceRegistry`, `Workspace`), `export_subtree`, and the `Storage` interface. | Python 3.12, PyYAML only |
| [`okf-backend`](../packages/okf-backend/) | Operations (add, patch, move, delete, describe, mkdir, reindex), semantic search (embeddings + sqlite-vec), settings (`OKF_EMBEDDING_*`), the REST API (Starlette, CLI `okf-backend`), and the `okf-migrate-v2` migration. | Starlette, `pydantic-settings`, sqlite-vec |
| [`okf-mcp`](../packages/okf-mcp/) | Thin MCP server for agents, one workspace per server: its tools call `okf_backend.operations` in-process (stdio or streamable-http). | `mcp` (FastMCP) |
| [`okf-web`](../packages/okf-web/) | The **Memory portal** (**OK, Fine Memory**): the notebook-doodle UI, consuming the okf-backend REST API and served by `okf-backend --static`. | Vite, React 19, wouter, TanStack Query, Tailwind v4, rough.js |
| [`okf-claude`](../packages/okf-claude/) | Claude Code integration: `setup`/`uninstall`, session hooks, slash commands. Uses okf-backend for operations and registers the okf-mcp server. | Python 3.12 |

`okf-web` is bun-only (no `pyproject.toml`), so the uv workspace excludes it.

## Words we use

| Word | Means |
|---|---|
| **Workspace** | A named folder under `$OKF_HOME/workspaces/<name>`: one OKF bundle (the OKF spec's term for the on-disk unit) plus metadata in `.okf/workspace.json`. The portal shows each one as a notebook. |
| **Node** | A directory or a concept, addressed by a path relative to the workspace root. |
| **Concept** | One markdown file with YAML frontmatter (`type` is required). One unit of knowledge: a service, a decision, a recipe. |
| **`_index.md`** | The generated *directory listing* in every folder. Regenerated after each write. A directory's authored `description` lives in its frontmatter; the workspace's description is the root `_index.md`'s. |
| **`_log.md`** | An append-only change log per directory. |

There is nothing between a workspace and its nodes: top-level folders are
ordinary folders. The rules a valid bundle (a workspace) follows are in
[`packages/okf-core/CONFORMANCE.md`](../packages/okf-core/CONFORMANCE.md).

## Run it

Needs [uv](https://docs.astral.sh/uv/) and [Bun](https://bun.sh/).

```bash
uv sync                                   # Python side
cd packages/okf-web && bun install && bun run build && cd -
uv run okf-backend --static packages/okf-web/dist
# open http://127.0.0.1:8765
```

`okf-backend` options:

| Flag | Default | What it does |
|---|---|---|
| `--static DIR` | none (API only) | serve a built frontend (e.g. `packages/okf-web/dist`) |
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
uv run okf-backend                           # API on 8765
cd packages/okf-web && bun run dev      # UI on 5173, proxies /api to 8765
# OKF_API=http://127.0.0.1:9000 bun run dev   # point the proxy elsewhere
```

The landing page is a second Vite entry (`landing.html` → `src/landing/`).
In dev open `http://localhost:5173/landing.html`; `bun run build` writes
`dist/landing.html`, which `okf-backend --static` serves at `/landing.html`.

The landing page is also published to GitHub Pages
(https://hannguyendd.github.io/okf-sdk/) by `.github/workflows/landing-pages.yml`
on every push to `main` that touches `packages/okf-web`: it builds with
`--base=./` and ships `landing.html` as the site's `index.html`. One-time setup
(repo admin): Settings → Pages → Source: **GitHub Actions**.

Add `?intro` to the app URL to replay the opening animation (it plays once per tab,
and never under `prefers-reduced-motion`).

## Connect an AI agent (MCP)

Agents write into the same workspaces you browse. One MCP server serves one
workspace. With Claude Code:

```bash
claude mcp add okf-team --scope project \
  -- /path/to/okf-sdk/.venv/bin/okf-mcp --workspace team
```

Or in any MCP client config:

```json
{
  "mcpServers": {
    "okf-team": {
      "command": "/path/to/okf-sdk/.venv/bin/okf-mcp",
      "args": ["--workspace", "team"]
    }
  }
}
```

Over streamable-http (`okf-mcp --transport streamable-http`), the workspace is
the `X-OKF-Workspace` header, required on every request; `--workspace` is for
stdio only. There is no workspace argument on any tool and no prompt: an agent
that needs several workspaces gets several servers. The tools are `add`,
`patch`, `get`, `list`, `read_index`, `move`, `delete`, `reindex`, `describe`,
`mkdir` and `search(query, top_k, paths)`. Full details and the tool list:
[`packages/okf-mcp/README.md`](../packages/okf-mcp/README.md).

To hook Claude Code up in one go (server, session hooks, slash commands), use
`scripts/setup-claude-code.sh --workspace team` ([`okf-claude`](../packages/okf-claude/README.md)).

## Upgrading from the bundle era

Workspaces made before bundles were removed (`workspace.json` version 1) need a
one-time migration:

```bash
uv run okf-migrate-v2 --dry-run          # show what would change; write nothing
uv run okf-migrate-v2                    # migrate every workspace under $OKF_HOME
okf-claude setup --workspace <ws>        # re-run in each project that used okf-claude
```

It rewrites absolute links with the old bundle directory as a prefix, moves
bundle descriptions into `_index.md`, moves `okf_version` to the root
`_index.md`, writes `workspace.json` version 2 and drops `vectors.db` (rebuilt
on the next search). Running it again changes nothing.

## Search

Search is semantic: it embeds each folder's `_index.md` listing (which carries
the folder's description) through a local OpenAI-compatible embeddings server, stored in the
workspace's `.okf/vectors.db` (sqlite-vec) and synced lazily at search time.
Without `OKF_EMBEDDING_URL` and `OKF_EMBEDDING_MODEL`, search is off and Okie
naps on the search page. The REST route is `GET /api/workspaces/{ws}/search?paths=`
(and the MCP tool takes `paths`: directory prefixes to limit the search).

## Develop

```bash
uv sync                                  # shared .venv with every member + dev group
uv run pytest                            # all Python tests
uv run pytest packages/okf-core/tests/test_bundle.py -v

cd packages/okf-web
bun run test                             # Vitest + MSW (in-memory fake API)
bun run typecheck
bun run build
```

- All workspace file access goes through `okf_core.Storage` (`LocalStorage` by
  default, `MemoryStorage` in tests). Don't use `pathlib` on workspace files.
- Tests must set `OKF_HOME` or pass `root=`; never touch the real home folder.
- Add a Python package under `packages/<name>/` with its own `pyproject.toml`;
  the workspace members glob picks it up.
- Runtime deps: `uv add --package okf-core <pkg>`; dev deps: `uv add --dev <pkg>`.

### okf-web layout

```
packages/okf-web/
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

Brand, voice and asset rules: [`packages/okf-web/brand/BRAND.md`](../packages/okf-web/brand/BRAND.md).
How the art is generated: [`packages/okf-web/ASSETS_PROMPT.md`](../packages/okf-web/ASSETS_PROMPT.md).

## Where things live on disk

```
~/.okf/workspaces/
└── team/                        a workspace (one OKF bundle)
    ├── .okf/
    │   ├── workspace.json       {"version": 2, "color"?}: the crayon colour
    │   └── vectors.db           search index
    ├── _index.md                generated listing (root; carries the workspace description)
    ├── _log.md                  change log
    ├── welcome.md               a concept
    ├── episodes/                e.g. Claude Code session episodes
    └── services/                an ordinary directory
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
- [Workspace targeting](superpowers/specs/2026-10-26-okf-workspace-targeting-design.md) (superseded)
- [Remove bundles and package split](superpowers/specs/2026-11-18-okf-remove-bundles-and-package-split-design.md)
