# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

`okf-sdk` is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
of Open Knowledge Format tooling. The root `pyproject.toml` is a **virtual**
workspace root (no `[project]` of its own); packages live under `packages/*`.

The workspace has two members. **`packages/okf-core`** — a library for
reading, indexing, and validating OKF bundles (`OKFDocument`, `Bundle`,
`regenerate_indexes`, `validate_bundle`). Its only runtime dependency is PyYAML.
See `docs/superpowers/specs/2026-06-25-okf-core-indexing-library-design.md` for
the indexing-library design and
`docs/superpowers/specs/2026-06-26-okf-conformance-rules-design.md` plus
`packages/okf-core/CONFORMANCE.md` for the conformance rules the validator
checks.

**`packages/okf-mcp`** — a producer MCP server (official `mcp` SDK / FastMCP,
plus `pydantic-settings`) for authoring bundles: tools to `add`, `patch`,
`move`, `get`, and `list` concepts and `read_index` (progressive disclosure),
re-indexing and appending a directory-scoped `_log.md` entry after each write.
The bundle root comes from `OKF_BUNDLE_ROOT` (overridable per call). See
`docs/superpowers/specs/2026-06-29-okf-mcp-producer-design.md` and
`docs/superpowers/plans/2026-06-29-okf-mcp-producer.md`.

## Tooling

This is a [uv](https://docs.astral.sh/uv/)-managed workspace targeting Python 3.12 (pinned in `.python-version`). The shared `.venv`, lockfile (`uv.lock`), and dev dependency group live at the root; each member package carries its own `[project]` metadata.

## Commands

- `uv sync` — create/update the shared `.venv` with all workspace members (installed editable) plus the dev dependency group
- `uv run pytest` — run the full test suite (config in the root `pyproject.toml`)
- `uv run pytest packages/okf-core/tests/test_bundle.py::test_load_collects_concepts_excluding_index -v` — run a single test
- `uv add --package okf-core <package>` — add a runtime dependency to the okf-core member
- `uv add --dev <package>` — add a dev dependency to the workspace root
