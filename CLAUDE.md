# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

`okf-sdk` is an early-stage scaffold created by `uv init`. As of now it contains only a Hello World `main.py` — there is no SDK implementation, tests, or lint configuration yet. Expect to establish these conventions as the project grows; update this file when you do.

## Tooling

This is a [uv](https://docs.astral.sh/uv/)-managed project targeting Python 3.12 (pinned in `.python-version`). Dependencies and metadata live in `pyproject.toml`; a `uv.lock` is generated on first sync.

## Commands

- `uv run main.py` — run the entry point
- `uv sync` — create/update the virtual environment (`.venv`) from `pyproject.toml` + `uv.lock`
- `uv add <package>` / `uv add --dev <package>` — add a runtime / dev dependency
- `uv run python -c "..."` — run arbitrary Python inside the project environment

No test runner or linter is configured yet. When adding tests, prefer `uv run pytest` (after `uv add --dev pytest`); run a single test with `uv run pytest path/to/test.py::test_name`.
