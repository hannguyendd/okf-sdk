# okf-mcp

Producer MCP server for authoring and maintaining Open Knowledge Format (OKF)
bundles. Built on the official `mcp` SDK (FastMCP); depends on `okf-core`.

## Configuration

Set the bundle root via the `OKF_BUNDLE_ROOT` environment variable, or pass
`bundle_root` to any tool to override per call. For local use, copy
`.env.example` to `.env` (gitignored) and set `OKF_BUNDLE_ROOT` there — real
environment variables take precedence over the `.env` file. Example MCP client
config:

```json
{
  "mcpServers": {
    "okf-producer": {
      "command": "okf-mcp",
      "env": { "OKF_BUNDLE_ROOT": "/path/to/bundle" }
    }
  }
}
```

### Store mode (`OKF_STORE_ROOT`)

Instead of pointing at a single bundle, set `OKF_STORE_ROOT` to a base directory
and the server partitions documents into a **per-project subfolder** under it —
no per-project configuration:

```json
{
  "mcpServers": {
    "okf-producer": {
      "command": "okf-mcp",
      "env": { "OKF_STORE_ROOT": "/path/to/store" }
    }
  }
}
```

The subfolder is named `<project-basename>-<hash8>`, e.g. a project at
`/Users/you/dev/acme/web-app` resolves to `/path/to/store/web-app-3f9a1c7b/`. The
basename is the readable prefix; the 8-hex-char SHA-256 of the absolute path keeps
two same-named projects from colliding. The subfolder is created on first write.

The **project path** comes from the client's MCP `roots` capability (the first
advertised workspace folder); if the client sends no roots, the server falls back
to its working directory.

**Resolution precedence** (per call): an explicit `bundle_root` argument wins;
otherwise `OKF_STORE_ROOT` (store mode); otherwise `OKF_BUNDLE_ROOT` (single
bundle). Setting **both** `OKF_STORE_ROOT` and `OKF_BUNDLE_ROOT` is an error
(`set OKF_STORE_ROOT or OKF_BUNDLE_ROOT, not both`). `OKF_STORE_ROOT` must be an
existing directory.

## Setup (stdio)

`main()` calls `mcp.run()`, which uses the **stdio** transport: the client
launches the server as a subprocess and speaks JSON-RPC over stdin/stdout. No
flags are needed.

### Launch command

Pick one for your client config (replace `/path/to/okf-sdk` and the bundle path):

- **Direct venv console script** (simplest — its shebang resolves all deps, no
  `uv` needed on `PATH`):
  `/path/to/okf-sdk/.venv/bin/okf-mcp`
- **Via uv** (re-syncs the workspace if needed):
  `uv run --directory /path/to/okf-sdk okf-mcp`

The bundle the server edits comes from `OKF_BUNDLE_ROOT` (or a per-call
`bundle_root`); the directory must exist.

### Claude Code

```bash
claude mcp add okf-producer \
  --scope project \
  --env OKF_BUNDLE_ROOT=/path/to/bundle \
  -- /path/to/okf-sdk/.venv/bin/okf-mcp
```

`claude mcp list` should report `okf-producer: ✓ connected`, and `/mcp` lists the
tools. This is equivalent to a project `.mcp.json`:

```json
{
  "mcpServers": {
    "okf-producer": {
      "command": "/path/to/okf-sdk/.venv/bin/okf-mcp",
      "env": { "OKF_BUNDLE_ROOT": "/path/to/bundle" }
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
`add, patch, get, list, read_index, move, reindex, delete, describe`. Or explore interactively with the
[MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector \
  uv run --directory /path/to/okf-sdk okf-mcp
```

The server starts even with no `OKF_BUNDLE_ROOT`; it only errors when a tool runs
and cannot resolve a bundle root. stdio keeps stdout reserved for protocol
traffic — tools return values rather than printing.

## Tools

- `add(concept_id, frontmatter, body, bundle_root?)` — create a concept (fails if it exists; `type` required).
- `patch(concept_id, frontmatter?, body?, bundle_root?)` — update a concept (merge-only frontmatter; body replaced only when given).
- `get(concept_id, bundle_root?)` — read one concept (frontmatter, body, outgoing links).
- `list(type?, prefix?, bundle_root?)` — enumerate concepts, optionally filtered.
- `read_index(dir?, depth=1, bundle_root?)` — read `_index.md` files for progressive disclosure (depth 1-3).
- `move(from_concept_id, to_concept_id, bundle_root?)` — relocate/rename a concept; rewrites inbound and own links, regenerates indexes, logs a Move entry (fails if source missing, destination exists, or ids equal).
- `delete(concept_id, force=False, bundle_root?)` — delete a concept; safe by default (returns `action="blocked"` with `referenced_by` when other concepts link to it). `force=True` deletes anyway, unlinking inbound references (`[label](target.md)` → `label`), then regenerates indexes and logs a Deletion entry. Irreversible; fails if the concept does not exist.
- `reindex(bundle_root?)` — regenerate every `_index.md` from current content to repair drift (e.g. files edited outside these tools); does not touch `_log.md`.
- `describe(dir, description, bundle_root?)` — set a directory's authored `description` (its purpose) in that directory's `_index.md` frontmatter; regenerates indexes so it appears in the parent's listing, and appends an Update `_log.md` entry. An empty string clears it (reverting to the synthesized summary). Fails if `dir` has no `_index.md`.

Every write tool (`add`/`patch`/`move`/`delete`/`describe`) regenerates indexes and appends
a dated entry to the relevant directory `_log.md`. `add`/`patch` manage the
`timestamp` frontmatter automatically; `move` preserves it. `reindex` only regenerates
indexes — it is index maintenance, not a concept change, so it writes no log entry.

## Development

```bash
uv sync
uv run pytest packages/okf-mcp
```
