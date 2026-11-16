# OKF Claude Code integration (okf-claude) — design

Roadmap item 6 (`docs/TODO.md`). Gives Claude Code sessions long-term memory in
an OKF bundle: guidance and recent history at session start, an automatic
episode at session end, and slash commands for explicit saves and lookups.

## Goals

- One command sets a project up: MCP server, hooks, slash commands.
- A new session starts knowing how to use OKF memory and what recent sessions did.
- Every session of substance leaves an **episode** concept behind, with no
  action from the user or the agent.
- Hooks never break or slow a session.

Non-goals (for now): episode aging/decay, concept-level search, packaging as a
Claude Code plugin, a PreCompact save.

## Approaches considered (who writes the episode)

| Approach | Trade-off |
|---|---|
| **SessionEnd hook → detached `claude -p` over the transcript** (chosen) | Good summaries, zero cost to the live session, works after the agent is gone. Needs `claude` on PATH and costs one small model call per session. |
| Stop/PreCompact hook that makes the live agent write the episode | Best context, but spends the user's session tokens, blocks the stop, and fires every turn unless gated. |
| Transcript parser, no model | Free and deterministic, but produces a log rather than a summary of goals, decisions, and open threads. |

## Design

New workspace member `packages/okf-claude`, CLI `okf-claude`:

- `setup` — ensures the workspace/bundle exist (`--no-create` to refuse);
  `claude mcp add --scope <scope> okf -e OKF_WORKSPACE=… -e OKF_BUNDLE=… --
  <venv>/okf-mcp`; merges hook entries into the scope's settings file
  (`local` → `.claude/settings.local.json` default, since commands are absolute
  venv paths; `project` → `.claude/settings.json`; `user` → `~/.claude/settings.json`);
  copies `/okf-remember` and `/okf-recall`. Idempotent: our hook entries are
  recognized by `okf-claude … hook …` in the command and replaced; foreign
  hooks are kept. `uninstall` reverses all three.
- `hook session-start` — prints `hookSpecificOutput.additionalContext`: the
  `session_start.md` guidance plus up to `--recent` episodes (same `project` as
  the event's `cwd` preferred, else any), the newest one's body inlined (1500
  chars).
- `hook session-end` — spawns `okf-claude episode …` detached
  (`start_new_session`, stderr to the log) and returns immediately.
- `episode` — parses the JSONL transcript (user prompts + assistant text only;
  drops tool calls/results, meta, sidechains, command wrappers), skips sessions
  with < 2 prompts, renders it (first prompt + newest tail, 60k chars), runs
  `claude -p --model <m> --tools "" --strict-mcp-config --no-session-persistence`
  in `OKF_HOME` with `OKF_CLAUDE_CHILD=1`, parses the JSON answer
  (`title`, `description`, `tags`, `body`), and writes it through
  `okf_mcp.operations` (so indexes and `_log.md` update).

Episode concept: `episodes/<UTC start date>-<first 8 alnum of session id>`,
frontmatter `type: episode`, `title`, `description`, `tags`, `session_id`,
`project` (cwd), `started`, `end_reason`. A resumed session's end patches the
same concept. The `episodes/` directory gets an authored description on first
write.

Safety: every hook path catches errors, logs to
`<OKF_HOME>/logs/okf-claude.log`, and exits 0. `OKF_CLAUDE_CHILD` makes both
hooks no-ops inside the summarizer run, so episodes never recurse.

Entry script `scripts/setup-claude-code.sh` runs `uv sync` and then
`okf-claude setup "$@"`.
