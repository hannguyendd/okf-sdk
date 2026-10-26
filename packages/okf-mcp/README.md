# okf-mcp

Producer MCP server for authoring and maintaining Open Knowledge Format (OKF)
bundles. Built on the official `mcp` SDK (FastMCP); depends on `okf-core`.

## Workspaces and bundles

The server works on **bundles inside workspaces**:
`<OKF_HOME>/workspaces/<workspace>/<bundle>/` (`OKF_HOME` defaults to `~/.okf`).
Each workspace keeps its metadata in a hidden `.okf/` folder:
`.okf/workspace.json` holds each bundle's description (what it is for), and
`.okf/vectors.db` is the workspace's search index. Workspaces are created by a
person; agents can create **bundles** (`create_bundle`).

Every tool takes optional `workspace` and `bundle` arguments. Each is resolved
independently, first match wins:

1. the tool argument;
2. the `X-OKF-Workspace` / `X-OKF-Bundle` request header (HTTP transport);
3. the `OKF_WORKSPACE` / `OKF_BUNDLE` environment variable (also read from `.env`);
4. the choice the user made earlier in this MCP session;
5. otherwise the only candidate, if there is exactly one, or **the user is asked**
   (MCP elicitation). A client without elicitation gets an error listing the
   choices, so the agent can retry with an argument.

The default workspace and default bundle act as a pair: the default bundle is
ignored when a call names a different workspace. Every result echoes the
`workspace` and `bundle` it used.

## Setup

### stdio (default)

```json
{
  "mcpServers": {
    "okf-producer": {
      "command": "/path/to/okf-sdk/.venv/bin/okf-mcp",
      "env": { "OKF_WORKSPACE": "team", "OKF_BUNDLE": "notes" }
    }
  }
}
```

Both env vars are optional. Launch with the venv console script (above) or
`uv run --directory /path/to/okf-sdk okf-mcp`. With Claude Code:

```bash
claude mcp add okf-producer --scope project \
  --env OKF_WORKSPACE=team \
  -- /path/to/okf-sdk/.venv/bin/okf-mcp
```

### Streamable HTTP (defaults per client via headers)

```bash
okf-mcp --transport streamable-http --port 8000   # binds 127.0.0.1; no auth
```

```json
{
  "mcpServers": {
    "okf-producer": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": { "X-OKF-Workspace": "team", "X-OKF-Bundle": "notes" }
    }
  }
}
```

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
| /path/to/okf-sdk/.venv/bin/okf-mcp
```

Expect an `initialize` result naming `okf-producer`, then a `tools/list` with
`add, patch, get, list, read_index, move, reindex, delete, describe, search,
list_workspaces, list_bundles, create_bundle, describe_bundle`. Or explore interactively with the
[MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector \
  uv run --directory /path/to/okf-sdk okf-mcp
```

The server starts even with no workspace configured; a tool only errors when it
runs and cannot resolve its workspace or bundle. stdio keeps stdout reserved for protocol
traffic — tools return values rather than printing.

## Tools

Concept tools — each also takes optional `workspace` and `bundle`, and returns
its result plus `workspace` and `bundle` (list results as `{workspace, bundle, items}`):

- `add(concept_id, frontmatter, body)` — create a concept (fails if it exists; `type` required).
- `patch(concept_id, frontmatter?, body?)` — update a concept (merge-only frontmatter; body replaced only when given).
- `get(concept_id)` — read one concept (frontmatter, body, outgoing links).
- `list(type?, prefix?)` — enumerate concepts, optionally filtered.
- `read_index(dir?, depth=1)` — read `_index.md` files for progressive disclosure (depth 1-3).
- `move(from_concept_id, to_concept_id)` — relocate/rename a concept; rewrites inbound and own links, regenerates indexes, logs a Move entry (fails if source missing, destination exists, or ids equal).
- `delete(concept_id, force=False)` — delete a concept; safe by default (returns `action="blocked"` with `referenced_by` when other concepts link to it). `force=True` deletes anyway, unlinking inbound references (`[label](target.md)` → `label`), then regenerates indexes and logs a Deletion entry. Irreversible; fails if the concept does not exist.
- `reindex()` — regenerate every `_index.md` from current content to repair drift (e.g. files edited outside these tools); does not touch `_log.md`.
- `describe(dir, description)` — set a directory's authored `description` in that directory's `_index.md` frontmatter; regenerates indexes and appends an Update `_log.md` entry. An empty string clears it. Fails if `dir` has no `_index.md`.

Workspace and bundle tools:

- `list_workspaces()` — `[{name, bundles}]`.
- `list_bundles(workspace?)` — `{workspace, bundles: [{name, description}]}`.
- `create_bundle(name, description?, workspace?)` — create an empty bundle (fails if it exists).
- `describe_bundle(description, bundle?, workspace?)` — set (or clear with null/empty) what a bundle is for; max 1000 chars.

Search:

- `search(query, top_k=5, bundles?, dir?, workspace?)` — semantic search across the workspace: returns `{workspace, bundles, hits}`, hits `{bundle, kind, dir, path, score, excerpt}` best first (`kind` is `index`, or `bundle` for a bundle-description match with `path` null). Searches every bundle unless `bundles` (or a default bundle) narrows it; `dir` needs exactly one bundle. See [Search](#search).

Every write tool (`add`/`patch`/`move`/`delete`/`describe`) regenerates indexes and appends
a dated entry to the relevant directory `_log.md`. `add`/`patch` manage the
`timestamp` frontmatter automatically; `move` preserves it. `reindex` only regenerates
indexes — it is index maintenance, not a concept change, so it writes no log entry.

## Search

`search` embeds every `_index.md` (one file = one chunk, truncated to
`OKF_EMBEDDING_MAX_CHARS`) and every bundle description with a **local
OpenAI-compatible embedding server**, and ranks them together by cosine
similarity. Concept bodies are not searched. It is
disabled until you configure the server; every other tool works without it.

| Variable | Meaning | Default |
|---|---|---|
| `OKF_EMBEDDING_URL` | Base URL incl. any `/v1` prefix; `/embeddings` is appended (e.g. Ollama: `http://localhost:11434/v1`) | unset (search errors) |
| `OKF_EMBEDDING_MODEL` | Model name sent to the server | unset (search errors) |
| `OKF_EMBEDDING_API_KEY` | Bearer token, if the server wants one | none |
| `OKF_EMBEDDING_MAX_CHARS` | Max characters of an `_index.md` sent to the model | `6000` |

Vectors live in one [`sqlite-vec`](https://github.com/asg017/sqlite-vec) file per
workspace, `<workspace>/.okf/vectors.db`, outside every bundle. The bundles a
search covers are synced at its start — only indexes and descriptions whose text
changed are re-embedded, and deleted files and bundles are dropped — so write
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
