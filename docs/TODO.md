# OKF To-Do

Ideas captured for later review. Each needs a brainstorm and a spec before implementation. Status as of 2026-10-19.

## 1. Git-managed bundles

**Status:** Not started.

- Manage bundle files with git (the request mentioned "git pull" to manage files).
- Open questions: what the git integration should do (pull teammates' changes, commit own writes, history), and how it interacts with `okf-mcp` write tools and `_log.md`.

## 2. Workspace concept

**Status:** Done — merged in PR #1 (`okf_core.workspace`, `~/.okf/workspaces/<name>`). Not yet done: `git init` on workspace creation (belongs to item 1).

- Introduce a **workspace** as a first-class concept: a workspace is a git repo.
- Within a workspace, an **index** is a collection of concepts (as the user described it; not the same thing as today's per-directory `_index.md` files, so the terminology needs to be settled).
- Likely ties to item 1: the workspace is the unit git manages.
- Open questions: relation to bundle and to store mode (`OKF_STORE_ROOT`), whether one workspace holds several indexes/bundles, how an index is defined (directory, tag, or explicit list), and whether `CONTEXT.md` glossary should define workspace/index first.

## 3. Vectorize index files to improve search

**Status:** Not started.

- Embed `_index.md` files (and possibly concepts) into a vector index so search goes beyond keyword and tree browsing.
- Open questions: embedding provider (local vs API), where the vector store lives, how it stays in sync with writes and `reindex`, and whether it stays optional so `okf-core` keeps PyYAML as its only runtime dependency.

## 4. Storage abstraction (filesystem as an interface)

**Status:** Done — in review in PR #2 (storage interface with local and in-memory backends; all okf-core and okf-mcp callers use it). Distributed backends remain future work.

- Put the file system behind an interface so storage can later move to a distributed backend without changing callers.
- Likely touches `okf-core` (`Bundle`, `OKFDocument`, `regenerate_indexes`, `validate_bundle`) and `okf-mcp` write tools, which read and write files directly today.
- Ties to items 1-3: git, workspaces, and the vector index would all sit on top of this layer.
- Open questions: interface shape (read/write/list/move/delete, atomicity, locking), whether the local filesystem stays the default backend, which distributed backends to target (object store, remote git, database), and how it affects the PyYAML-only dependency of `okf-core`.

## 5. React web UI for querying and managing memories

**Status:** Not started.

- A React web app to query and view (and manage) the memories stored in OKF bundles.
- Open questions: read-only viewer vs full management (add/patch/move/delete), how the UI reaches the data (new HTTP API over `okf-core`, or via `okf-mcp`), where it lives in the workspace (a new member under `packages/` or a separate frontend folder), how it relates to search (item 3) and the storage interface (item 4), and auth if it is ever hosted.

## 6. Claude Code integration: hooks and setup (episodic memory)

**Status:** Not started.

- Ship a setup for Claude Code (hooks, possibly packaged as a plugin or "mod") that wires OKF into sessions.
- Episodic memory: at the end of a session, capture a summary of what happened as an episode concept, so later sessions start with context from history.
- Counterpart at session start: load recent or relevant episodes into the agent's context.
- Possible hook points to evaluate: SessionEnd, SessionStart, PreCompact (save before context is compacted), Stop.
- Also possible: an init command that registers the `okf-mcp` server and installs the hooks in a project.
- Open questions: who writes the summary (the agent, a hook-spawned model call, or a transcript parser), how episodes are organized and aged out (see memory decay idea), how much context is injected at start, and how this respects store mode's per-project folders.
