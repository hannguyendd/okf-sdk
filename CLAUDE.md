# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

`okf-sdk` is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
of Open Knowledge Format tooling. The root `pyproject.toml` is a **virtual**
workspace root (no `[project]` of its own); packages live under `packages/*`.

The first and currently only member is **`packages/okf-core`** — a library for
reading and indexing OKF bundles (`OKFDocument`, `Bundle`, `regenerate_indexes`).
Its only runtime dependency is PyYAML. See
`docs/superpowers/specs/2026-06-25-okf-core-indexing-library-design.md` for the
design.

## Tooling

This is a [uv](https://docs.astral.sh/uv/)-managed workspace targeting Python 3.12 (pinned in `.python-version`). The shared `.venv`, lockfile (`uv.lock`), and dev dependency group live at the root; each member package carries its own `[project]` metadata.

## Commands

- `uv sync` — create/update the shared `.venv` with all workspace members (installed editable) plus the dev dependency group
- `uv run pytest` — run the full test suite (config in the root `pyproject.toml`)
- `uv run pytest packages/okf-core/tests/test_bundle.py::test_load_collects_concepts_excluding_index -v` — run a single test
- `uv add --package okf-core <package>` — add a runtime dependency to the okf-core member
- `uv add --dev <package>` — add a dev dependency to the workspace root
