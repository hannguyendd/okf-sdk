# okf-mcp

Producer MCP server for authoring and maintaining Open Knowledge Format (OKF)
workspaces. Built on the official `mcp` SDK (FastMCP); a thin adapter over
`okf-backend` (operations, search and embedding settings live in
`okf_backend`), which builds on `okf-core`.

## One server, one workspace

A **workspace** is one OKF bundle on disk at `<OKF_HOME>/workspaces/<workspace>/`
(`OKF_HOME` defaults to `~/.okf`). Its hidden `.okf/` folder keeps
`.okf/workspace.json` (version and crayon colour) and `.okf/vectors.db`, the
workspace's search index. Workspaces are created by a person, never over MCP.

Each server instance serves exactly one workspace. Tools take workspace-relative
paths (a **node** is a directory or a concept) and have no `workspace` argument:

| Transport | How the workspace is set | If it is missing or unknown |
|---|---|---|
| stdio | `--workspace <name>`, read once at startup | the server exits, listing the existing workspaces |
| streamable-http | the `X-OKF-Workspace` header, read on every request | that tool call fails, listing the existing workspaces |

`--workspace` together with `--transport streamable-http` is an error. To give an
agent several workspaces, configure several servers. Every result echoes the
`workspace` it used.

## Setup

### stdio (default)

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

Launch with the venv console script (above) or
`uv run --directory /path/to/okf-sdk okf-mcp --workspace team`. With Claude Code:

```bash
claude mcp add okf-team --scope project \
  -- /path/to/okf-sdk/.venv/bin/okf-mcp --workspace team
```

### Streamable HTTP (workspace per client via a header)

```bash
okf-mcp --transport streamable-http --port 8000   # binds 127.0.0.1; no auth
```

```json
{
  "mcpServers": {
    "okf-team": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": { "X-OKF-Workspace": "team" }
    }
  }
}
```

The header is required on every request.

### Claude Desktop

Add the same `mcpServers` block to
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) and
restart the app.

### Verify without a client

Raw JSON-RPC handshake over the pipe:

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
| /path/to/okf-sdk/.venv/bin/okf-mcp --workspace team
```

Expect an `initialize` result naming `okf-producer`, then a `tools/list` with
`add, patch, get, list, read_index, move, reindex, delete, describe, mkdir,
search`. Or explore interactively with the
[MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector \
  uv run --directory /path/to/okf-sdk okf-mcp --workspace team
```

stdio keeps stdout reserved for protocol
traffic — tools return values rather than printing.

## Tools

Every tool returns its result plus `workspace` (list results as `{workspace, items}`).
Paths and ids are relative to the workspace root:

- `add(concept_id, frontmatter, body)` — create a concept (fails if it exists; `type` required).
- `patch(concept_id, frontmatter?, body?)` — update a concept (merge-only frontmatter; body replaced only when given).
- `get(concept_id)` — read one concept (frontmatter, body, outgoing links).
- `list(type?, prefix?)` — enumerate concepts, optionally filtered.
- `read_index(dir?, depth=1)` — read `_index.md` files for progressive disclosure (depth 1-3).
- `move(from_concept_id, to_concept_id)` — relocate/rename a concept; rewrites inbound and own links, regenerates indexes, logs a Move entry (fails if source missing, destination exists, or ids equal).
- `delete(concept_id, force=False)` — delete a concept; safe by default (returns `action="blocked"` with `referenced_by` when other concepts link to it). `force=True` deletes anyway, unlinking inbound references (`[label](target.md)` → `label`), then regenerates indexes and logs a Deletion entry. Irreversible; fails if the concept does not exist.
- `reindex()` — regenerate every `_index.md` from current content to repair drift (e.g. files edited outside these tools); does not touch `_log.md`.
- `describe(dir, description)` — set a directory's authored `description` in that directory's `_index.md` frontmatter; regenerates indexes and appends an Update `_log.md` entry. An empty string clears it. Fails if `dir` has no `_index.md`.
- `mkdir(dir, description?)` — create an empty directory with an optional description (writes its `_index.md`; fails if it exists). Concepts added under a new path create their directories automatically.

Search:

- `search(query, top_k=5, paths?)` — semantic search across the workspace: returns `{workspace, hits}`, hits `{kind, dir, path, score, excerpt}` best first (`kind` is `index`). `paths` is a list of directory prefixes that limits the search. See [Search](#search).

Every write tool (`add`/`patch`/`move`/`delete`/`describe`/`mkdir`) regenerates indexes and appends
a dated entry to the relevant directory `_log.md`. `add`/`patch` manage the
`timestamp` frontmatter automatically; `move` preserves it. `reindex` only regenerates
indexes — it is index maintenance, not a concept change, so it writes no log entry.

## Search

`search` embeds every `_index.md` in the workspace (one file = one chunk,
truncated to `OKF_EMBEDDING_MAX_CHARS`; a directory's description lives in its
`_index.md`) with a **local OpenAI-compatible embedding server**, and ranks them
by cosine similarity. Concept bodies are not searched. It is
disabled until you configure the server; every other tool works without it.
The search implementation and the `OKF_EMBEDDING_*` settings belong to `okf-backend`;
this server just exposes them.

Settings come from real environment variables, then `./.env` in the directory
the server starts in, then `<OKF_HOME>/.env` (`~/.okf/.env` by default). A stdio
server that Claude Code spawns runs in *that* project's directory, so put the
settings in `~/.okf/.env` to configure every server once.

| Variable | Meaning | Default |
|---|---|---|
| `OKF_EMBEDDING_URL` | Base URL incl. any `/v1` prefix; `/embeddings` is appended (e.g. Ollama: `http://localhost:11434/v1`) | unset (search errors) |
| `OKF_EMBEDDING_MODEL` | Model name sent to the server | unset (search errors) |
| `OKF_EMBEDDING_API_KEY` | Bearer token, if the server wants one | none |
| `OKF_EMBEDDING_MAX_CHARS` | Max characters of an `_index.md` sent to the model | `6000` |

Vectors live in one [`sqlite-vec`](https://github.com/asg017/sqlite-vec) file per
workspace, `<workspace>/.okf/vectors.db`, outside the concepts. The workspace is
synced at the start of a search — only `_index.md` files whose text
changed are re-embedded, and deleted files are dropped — so write
tools never contact the embedding server, and edits made outside them are picked up
too. The first search after many changes is slower. If the embedding server is
down, `search` fails rather than answering from stale vectors. Changing
`OKF_EMBEDDING_MODEL` (or the server starting to return vectors of another dimension)
rebuilds the whole workspace file on the next search. Concurrent searches are safe: embedding
happens outside the database write transaction. This needs a Python
whose `sqlite3` allows loadable extensions (uv-managed Python does).

## Development

```bash
uv sync
uv run pytest packages/okf-mcp
```
