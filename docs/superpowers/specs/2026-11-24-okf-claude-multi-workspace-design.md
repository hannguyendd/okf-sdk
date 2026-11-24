# okf-claude: several workspaces per project

Status: accepted · 2026-11-24 · builds on
`2026-11-13-okf-claude-code-integration-design.md` and the session-start root
overview (PR #16).

## Problem

`okf-claude setup` wires exactly one workspace into a project. The MCP server
is always named `okf` and setup replaces its own hooks, so a second
`setup --workspace B` silently replaces A. Working around it with different
`--scope`s is worse: Claude Code runs the hooks of every settings file (both
overviews, both episode lists, and every session summarized twice) but only
one `okf` server wins (local > project > user), so the agent can read B's
overview while its `mcp__okf__*` calls go to A.

## Decisions

1. **Repeatable `--workspace`.** `okf-claude setup -w backend -w team`. Order
   matters: the first workspace is the *primary* one. Duplicates are dropped.
2. **One MCP server per workspace.** This keeps okf-mcp's "one workspace per
   server" rule. Server names:
   - one workspace: `okf` (unchanged, so existing installs and the slash
     commands' `mcp__okf__*` names keep working);
   - several: `okf-<ws>`, with every character outside `[A-Za-z0-9_-]`
     replaced by `-` (Claude Code's server-name alphabet; workspace names may
     also contain `.`). Two workspaces mapping to the same name is a setup
     error. Tools are then `mcp__okf-<ws>__search`, etc.
   The rule lives in one function (`okf_claude.servers.server_names`) used by
   both the installer and the SessionStart hook, so the context always names
   the servers that were registered.
3. **Episodes go to one workspace**: the primary one, or `--episodes <ws>`
   (must be one of the `--workspace`s). SessionEnd writes there only;
   SessionStart lists recent episodes from there only. Writing to every
   workspace would duplicate history and leak one project's sessions into
   shared workspaces.
4. **SessionStart shows one overview per workspace**, each headed with its
   server and tool prefix, followed by the "when to use it" guidance: pick the
   workspace(s) whose overview fits the task, possibly several, possibly none;
   save knowledge in the workspace it belongs to and ask the user when that is
   unclear. The overview budget (3,000 chars) is shared, split evenly across
   workspaces (at least 600 each). With one workspace the context is the same
   as before.
5. **Slash commands** no longer hard-code `mcp__okf__*`; they tell the agent to
   use the servers listed in the session-start context and, for
   `/okf-remember`, to choose the target workspace (ask if unclear).
6. **Re-running setup and uninstall** find previously registered servers from
   the workspaces in our existing hook commands. Setup removes those servers
   (and the new ones) before adding, so going from `-w a -w b` to `-w a`
   leaves no stale `okf-b`. Uninstall removes all of them; with no hooks to
   read, it falls back to `okf`.

## Hook command lines

```
okf-claude hook session-start --workspace backend --workspace team --episodes backend --recent 5
okf-claude hook session-end --workspace backend --model haiku
```

SessionEnd only ever needs the episodes workspace. A single-workspace install
omits `--episodes`; old single-workspace hooks keep working unchanged.

## Out of scope

- Search across workspaces in one call (the agent calls each server).
- Per-workspace scopes in one setup run (one `--scope` per run, as before).
