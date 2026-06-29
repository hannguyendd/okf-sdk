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

## Tools

- `add(concept_id, frontmatter, body, bundle_root?)` — create a concept (fails if it exists; `type` required).
- `patch(concept_id, frontmatter?, body?, bundle_root?)` — update a concept (merge-only frontmatter; body replaced only when given).
- `get(concept_id, bundle_root?)` — read one concept (frontmatter, body, outgoing links).
- `list(type?, prefix?, bundle_root?)` — enumerate concepts, optionally filtered.
- `read_index(dir?, depth=1, bundle_root?)` — read `index.md` files for progressive disclosure (depth 1-3).

Every `add`/`patch` regenerates indexes and appends a dated entry to the changed
concept's directory `log.md`. `timestamp` frontmatter is managed automatically.

## Development

```bash
uv sync
uv run pytest packages/okf-mcp
```
