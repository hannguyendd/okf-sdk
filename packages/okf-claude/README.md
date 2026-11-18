# okf-claude

Claude Code integration for OKF: gives Claude Code sessions long-term memory in
an OKF workspace.

| Piece | What it does |
|---|---|
| `okf` MCP server | `okf-mcp`, pinned to one workspace (`okf-mcp --workspace`). |
| **SessionStart** hook | Adds OKF usage guidance and the most recent episodes (newest first, the latest one in full) to the session's context. |
| **SessionEnd** hook | Starts a detached background run that summarizes the transcript with `claude -p` (no tools, no MCP, no session saved) and writes it as an **episode** concept: `episodes/<date>-<session8>`. A resumed session updates its episode. Sessions with fewer than 2 prompts are skipped. |
| `/okf-remember [what]` | Saves durable knowledge (decisions, conventions, gotchas) as a concept, updating an existing one instead of duplicating it. |
| `/okf-recall <topic>` | Searches/browses memory and answers with the concept ids it used. |

Hooks never break a session: errors go to `<OKF_HOME>/logs/okf-claude.log`.

## Setup

From the okf-sdk checkout, for the project you want memory in:

```sh
scripts/setup-claude-code.sh --workspace team --project ~/code/myproject
```

That runs `uv sync` and then `okf-claude setup`, which:

1. creates the workspace if missing (`--no-create` to refuse);
2. registers the `okf` MCP server with `claude mcp add` (`--no-mcp` to skip);
3. writes the hooks into a Claude Code settings file;
4. installs the two slash commands.

Re-running replaces only its own entries. Restart Claude Code afterwards.

| Option | Default | |
|---|---|---|
| `--scope` | `local` | `local`: `.claude/settings.local.json`, just you. `project`: `.claude/settings.json` + `.mcp.json` (committed, but hook commands hold absolute paths to this machine's venv). `user`: `~/.claude/`, every project. |
| `--model` | `haiku` | Model that writes episode summaries. |
| `--recent` | `5` | Episodes listed at session start (`0` for guidance only). |
| `--server-env KEY=VALUE` | | Extra MCP server env, e.g. `OKF_EMBEDDING_URL=http://localhost:1234/v1` and `OKF_EMBEDDING_MODEL=...` to enable `search`. Repeatable. |

Upgrading from the bundle era (before `--bundle` was removed)? Run
`uv run okf-migrate-v2 --dry-run`, then `uv run okf-migrate-v2`, then
`okf-claude setup --workspace <ws>` again. Episodes written before migrating
stay under their old bundle directory (`<bundle>/episodes/`) and are still
shown at session start (SessionStart also reads `<dir>/episodes/` of each
top-level directory); new ones go to `episodes/` at the workspace root. Old
hooks that still pass `--bundle` are ignored and logged, so they do not break a
session until you re-run setup.

Remove everything with `uv run okf-claude uninstall --project ~/code/myproject`
(same `--scope`). Episodes already written stay in the workspace.

## Customizing the prompts

Prompts live in `src/okf_claude/prompts/`: `episode_summary.md` (the summarizer;
`{{transcript}}` is replaced), `session_start.md` (the injected guidance;
`{{workspace}}`, `{{recent}}`), and `commands/` (the slash
commands, copied on setup — re-run setup after editing them).
