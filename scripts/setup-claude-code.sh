#!/usr/bin/env bash
# Set up OKF memory for Claude Code in a project.
#
#   scripts/setup-claude-code.sh --workspace <ws> --bundle <bundle> [--project <dir>] [options]
#
# Syncs the okf-sdk environment, then runs `okf-claude setup` (see
# packages/okf-claude/README.md, or pass --help). --project defaults to the
# directory you run this from.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v uv >/dev/null || { echo "error: uv is required (https://docs.astral.sh/uv/)" >&2; exit 1; }
command -v claude >/dev/null || echo "warning: 'claude' not on PATH; MCP registration and episode summaries need it" >&2

uv sync --project "$ROOT" --quiet
exec "$ROOT/.venv/bin/okf-claude" setup "$@"
