# okf-sdk

A uv workspace of Open Knowledge Format (OKF) tooling.

## Packages

- [`packages/okf-core`](packages/okf-core/) — core library for reading and
  indexing OKF bundles: parse documents, load a bundle into an in-memory concept
  graph (cross-links + backlinks), and regenerate `_index.md` listings. Only
  runtime dependency is PyYAML.

## Development

```bash
uv sync            # create/update the shared .venv with all workspace members
uv run pytest      # run the full test suite
```

Add a new package under `packages/<name>/` with its own `pyproject.toml`; it is
picked up automatically by the `[tool.uv.workspace]` members glob.
