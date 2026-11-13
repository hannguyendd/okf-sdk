# okf-mcp: vector search over `_index.md` files — design

**Superseded in part by:** `2026-10-26-okf-workspace-targeting-design.md` — one vector DB per workspace (`<workspace>/.okf/vectors.db`) with rows keyed by bundle, bundle-description hits, and no `OKF_VECTOR_DB`.

Date: 2026-10-19. Status: draft for review. Roadmap item 3 in `docs/TODO.md`
("Vectorize index files to improve search").

## Intent

Today an agent finds knowledge in a bundle by walking `_index.md` listings from
the root (`read_index`) or by listing concepts with exact filters (`list`). That
only works when the agent already knows roughly where something lives, and it
cannot match a question phrased in different words from the ones the bundle
uses ("how do we handle retries?" vs a concept titled "backoff policy").

Add a `search` tool to `okf-mcp` that embeds every `_index.md` file and returns
the ones whose meaning is closest to a natural-language query. The intended
agent workflow is two steps: **search the indexes to locate the right area, then
go deeper** with `read_index` / `list` / `get` on what comes back. Search is a
way to enter the progressive-disclosure tree, not a replacement for it.

## Goals

- A new MCP tool `search(query, top_k, dir, bundle_root)` returning ranked
  `_index.md` hits.
- Embeddings come from a **local model served over an OpenAI-compatible
  `/v1/embeddings` endpoint** (e.g. Ollama, LM Studio, llama.cpp server, vLLM).
- **One `_index.md` file is one chunk.** Its text is truncated to a configurable
  maximum number of characters before embedding; there is no multi-chunk
  splitting.
- Vectors are stored in a **single-file embedded store, `sqlite-vec`**, with no
  server to run.
- The vector index stays correct without manual care: it follows writes,
  `reindex`, moves/deletes, and direct file edits.

## Non-goals

- Searching individual concept documents. Only `_index.md` files are embedded
  (decided with the user: the agent searches indexes, then reads deeper).
- Keyword/hybrid search, reranking, query rewriting, or result caching.
- Hosted/remote vector databases, or hosted embedding APIs as a supported target
  (an OpenAI-compatible URL may point anywhere, but we only design and test for
  a local server).
- Running, installing, or managing the embedding server.
- Changing `okf-core`.

## Anti-goals (a failure even if search technically works)

- A write tool (`add`, `patch`, `move`, `delete`, `describe`, `reindex`) fails,
  becomes slower, or even contacts the embedding server (writes never touch the
  vector store).
- `okf-core` gains a runtime dependency (it must stay PyYAML-only), or
  `okf-mcp` cannot start / run its other tools when the embedding server is
  unconfigured.
- The vector database file is picked up as bundle content (listed, indexed,
  flagged by `validate_bundle`, or surfaced by `list`/`read_index`).
- Search silently returns results from a stale or differently-modelled index.

## Constraints

- Lives entirely in `packages/okf-mcp`. Reuse `okf_core.Storage` for reading
  `_index.md` text (`Storage.iter_files(suffix=...)`, `read_text`) so it works
  with any storage backend for *reading*; tests use `MemoryStorage` where they
  can.
- Python 3.12, existing `pydantic-settings` `OKF_`-prefixed settings in
  `server.py`. New dependencies are limited to `sqlite-vec` and (if the builder
  wants an HTTP client) one already available transitively with `mcp`
  (`httpx`); no embedding SDK.
- Tests must not need a real embedding server or touch the real home directory
  (use a fake embedder, as existing tests inject fakes / `MemoryStorage`).
- Vectors are compared by cosine similarity; exact (brute-force) search is
  sufficient — a bundle has hundreds to low thousands of `_index.md` files.

## The tool

```
search(query: str, top_k: int = 5, dir: str | None = None,
       bundle_root: str | None = None) -> list[dict]
```

- `query`: natural-language text. Empty/whitespace is an error.
- `top_k`: 1–20; out-of-range values are clamped or rejected (builder's call).
- `dir`: optional bundle-relative directory; only `_index.md` files at or under
  it are returned (lets an agent narrow after a first pass). Same
  normalization as `read_index`'s `dir`.
- `bundle_root`: same per-call override and same root resolution as every other
  tool (explicit arg → store mode → `OKF_BUNDLE_ROOT`).

Each hit contains at least: the bundle-relative path of the `_index.md`
(e.g. `tables/_index.md`), its directory (`"."`/empty for the root, matching
`read_index` conventions), a similarity `score`, and enough of the file to be
useful at a glance (its authored `description` if present, else the first lines
of text). The agent passes the directory to `read_index` / `list` next. Results
are ordered by descending score; ties broken by path.

Errors are returned in the same style the other tools use (raised exceptions
surfaced by FastMCP) with clear messages for: embedding endpoint not
configured, endpoint unreachable, and `sqlite-vec` unavailable.

## Settings (all optional until search is used)

Added to the `Settings` class and documented in `.env.example` / README:

| Variable | Meaning | Default (my call) |
|---|---|---|
| `OKF_EMBEDDING_URL` | Base URL of the OpenAI-compatible server (the client calls `<url>/embeddings`) | unset → `search` errors with a clear "not configured" message; everything else works |
| `OKF_EMBEDDING_MODEL` | Model name sent in the request | unset → error as above |
| `OKF_EMBEDDING_API_KEY` | Bearer token if the server wants one | unset → no auth header |
| `OKF_EMBEDDING_MAX_CHARS` | Max characters of an `_index.md` fed to the model (truncate from the end) | 6000 |
| `OKF_VECTOR_DB` | Path of the sqlite-vec file | see below |

## How the vector index stays correct

A single function, `sync`, makes the vector store match the bundle:

1. List every `_index.md` in the bundle; read its text; truncate to the max
   characters; compute a content hash of the **truncated text**.
2. Compare against stored rows (`key`, `hash`). Embed only the files whose hash
   is new or changed; delete rows whose `_index.md` no longer exists.
3. Embedding requests are batched (batch size is the builder's call).

`sync` is called **only at the start of every `search`** (revised after review;
see "Settled after review"). Write tools and `reindex` do not touch the vector
store and never contact the embedding server. This repairs drift from any cause
(MCP writes, direct file edits, `git pull`) with one mechanism. When nothing
changed it costs one read + hash per `_index.md` and zero embedding calls; the
first search after a large change pays the embedding cost for just the changed
files.

If `sync` fails (server down or unreachable, model/dimension change that cannot
be rebuilt, dimension mismatch from the server), **`search` raises an error**
and returns nothing. It never answers from a store it could not bring up to
date.

Store metadata records the embedding **model name** and **vector dimension**. If
either differs from the current configuration, the store is rebuilt from
scratch on the next `sync` rather than mixing incompatible vectors.

### Where the vector file lives

- **Outside the bundle, never inside it.** `Storage.iter_files` does not skip
  dot-directories, so a hidden file in the bundle would be visible to the
  directory walks. Default for a bundle on local disk
  (`isinstance(storage, LocalStorage)`, using its `.root`): a sibling file
  `<bundle_root>.vectors.db` (e.g. `~/store/myproj-1a2b3c4d.vectors.db`, or
  `<workspace>/idx.vectors.db`). SQLite sidecars (`-wal`, `-shm`) land beside it,
  also outside the bundle. This also keeps it out of a git repo that wraps the
  bundle.
- In store mode each per-project bundle folder gets its own sibling file, so
  projects stay isolated.
- `OKF_VECTOR_DB` overrides the path and is **required for non-local `Storage`
  backends** (no local directory to derive from); without it, `search` errors
  clearly. Because one override file can then serve different `bundle_root`
  values across calls, every row carries the bundle's `Storage.location` and
  all reads/writes/prunes are scoped to it.

### Concurrency

Open the SQLite file in WAL mode with a busy timeout, and run each `sync` in a
single transaction. Serialize `sync` within a process with a lock. Several
server processes sharing one file is safe because the transaction plus hash
check make concurrent syncs idempotent (the loser at worst re-embeds a file).

## Conventions pinned down

- Paths are bundle-relative keys with `/` separators, as in `read_index`. The
  root directory is the **empty string `""`**, matching `read_index`'s
  `_clean_dir`; `dir` normalization reuses `_clean_dir` (so `"."` and `""` both
  mean the whole bundle, `..`/absolute paths are rejected).
- A hit's `dir` field is the directory key (`""` for root); `path` is the
  `_index.md` key (`""`-rooted: `_index.md`, `tables/_index.md`), exactly the
  shape `read_index` returns, so the agent can pass `dir` straight to it.
- Embedding endpoint: `OKF_EMBEDDING_URL` includes the version prefix if the
  server needs one (e.g. `http://localhost:11434/v1`); the client appends only
  `/embeddings`. The client L2-normalizes vectors and ranks by cosine
  similarity. A vector whose dimension differs from the store's (or from the
  first vector of a rebuild), or a batch the server rejects, fails the sync (and
  therefore the search).

## What is left to the builder

- Module layout inside `okf_mcp` (e.g. `embeddings.py`, `vector_store.py`) and
  how `operations.py` / `server.py` wire in the best-effort sync.
- Exact snippet shape returned per hit, `top_k` clamping vs rejecting, batch
  size, request timeout and retry behaviour, and how the best-effort sync logs.
- Whether to add an mtime/stat shortcut to skip reading unchanged files at
  search time (not required: one read per `_index.md` per search is accepted).
- How `sqlite-vec` is loaded and how to detect a Python whose `sqlite3` module
  cannot load extensions (the error should say what to do; `uv`-managed Python
  works).
- Test strategy: fake embedder returning deterministic vectors, round-trips
  through `MemoryStorage`, hash-skip behaviour, model-change rebuild, delete
  pruning, `dir` filtering, and the "embedding server down during a write"
  case.
- README / `.env.example` / `CLAUDE.md` updates, and ticking item 3 in
  `docs/TODO.md`.

## Decisions that are my calls (not yet confirmed by the user)

- `sqlite-vec` as the store (vs Chroma, Qdrant, LanceDB).
- Code in `okf-mcp`, not `okf-core`.
- Sync only at search time; writes never touch the vector store.
- Default `OKF_EMBEDDING_MAX_CHARS=6000`; vector file as a sibling
  `<bundle_root>.vectors.db`, outside the bundle.
- Tool name `search` and its parameters.
- `search` errors (rather than warning) if sync cannot complete.
- WAL + transaction concurrency model; rows scoped by `Storage.location`.

## Settled after review

A pre-build review raised these; all were resolved from the code or as minor
calls. The one that changes an earlier statement: the first draft synced
best-effort after every write. That conflicted with "writes must never get
slower" (a timeout inline is slow; a background task adds an architecture), so
sync now happens only at search time.
