# okf-mcp Vector Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `search` MCP tool to `okf-mcp` that returns the `_index.md` files closest in meaning to a natural-language query.

**Architecture:** An OpenAI-compatible embedding client and a `sqlite-vec` store live in `okf-mcp` (never `okf-core`). Each `_index.md` is one chunk, truncated to a character limit. The store is synced (hash diff, embed only changed files, prune deleted ones) at the start of every `search`; write tools never touch it.

**Tech Stack:** Python 3.12, `sqlite-vec`, `httpx` (already a transitive dependency of `mcp`; add it explicitly), FastMCP, `pydantic-settings`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-19-okf-mcp-vector-search-design.md`

## Global Constraints

- Code lives only in `packages/okf-mcp`; `okf-core` is not modified and stays PyYAML-only.
- New runtime dependencies for `okf-mcp` are limited to `sqlite-vec` and `httpx`. No embedding SDK.
- Only `_index.md` files are embedded (not concepts). One file = one chunk, truncated with `text[:max_chars]`, default `OKF_EMBEDDING_MAX_CHARS=6000`.
- Write tools (`add`, `patch`, `move`, `delete`, `describe`, `reindex`) must not touch the vector store or the embedding server.
- The vector file is never inside the bundle: default is the sibling `<bundle_root>.vectors.db`; `OKF_VECTOR_DB` overrides and is required for non-local `Storage`.
- Settings use the `OKF_` prefix: `OKF_EMBEDDING_URL` (includes any `/v1`; client appends only `/embeddings`), `OKF_EMBEDDING_MODEL`, `OKF_EMBEDDING_API_KEY`, `OKF_EMBEDDING_MAX_CHARS`, `OKF_VECTOR_DB`. Unset URL/model makes only `search` error; the server and other tools work.
- Tool signature: `search(query: str, top_k: int = 5, dir: str | None = None, bundle_root: str | None = None) -> list[dict]`. `top_k` outside 1..20 is rejected with `ValueError`. The root directory key is `""`.
- Vectors are L2-normalized in the client and ranked by cosine similarity. Rows are scoped by `Storage.location`. SQLite runs in WAL mode with a busy timeout; each sync is one transaction.
- A failed sync makes `search` raise; it never answers from an un-synced store.
- Tests use a fake embedder / `httpx.MockTransport` and `MemoryStorage` or `tmp_path`. They never contact a real server or touch the real home.
- Git: work on branch `feat/okf-mcp-vector-search` (created in Task 1), never on `main`. Stage explicit paths only; the working tree has unrelated uncommitted files (`.gitignore`, `.vscode/`, `AGENTS.md`) that must not be committed.

## Review Focus

- `search` with an empty or whitespace-only query: raise `ValueError`, no embedding call. (Task 3)
- A bundle with no `_index.md` files, or `top_k` larger than the number of files: return what exists (possibly `[]`), no error. (Task 2)
- A file named `foo_index.md` (not `_index.md`) must not be embedded; `Storage.iter_files(suffix=...)` is an `endswith` match. (Task 2)
- A bundle root given with a trailing slash or as a `file://` URI resolves to the same sibling DB path as the plain path. (Task 2)
- The embedding server returns fewer vectors than inputs, or a vector of a different dimension than the store holds: the sync fails and `search` raises, leaving the previous store contents intact (transaction rolls back). (Tasks 1, 2)

---

### Task 1: Embedding client

**Files:**
- Create: `packages/okf-mcp/src/okf_mcp/embeddings.py`
- Test: `packages/okf-mcp/tests/test_embeddings.py`
- Modify: `packages/okf-mcp/pyproject.toml` (dependencies)

**Interfaces:**
- Produces:
  - `class EmbeddingError(RuntimeError)`
  - `@dataclass(frozen=True) class EmbeddingConfig: url: str; model: str; api_key: str | None = None; timeout: float = 30.0; batch_size: int = 32`
  - `def embed_texts(texts: list[str], config: EmbeddingConfig, *, client: httpx.Client | None = None) -> list[list[float]]` — one L2-normalized vector per input, in input order.

- [ ] **Step 1: Create the branch and add dependencies**

Run `git switch -c feat/okf-mcp-vector-search`, then `uv add --package okf-mcp sqlite-vec httpx`. Expected: `packages/okf-mcp/pyproject.toml` and `uv.lock` change.

- [ ] **Step 2: Write the failing tests** in `test_embeddings.py`, using `httpx.Client(transport=httpx.MockTransport(handler))`:
  - `test_posts_to_embeddings_path_with_model_and_input`: URL `http://h/v1`, handler asserts request URL is `http://h/v1/embeddings`, JSON body `{"model": "m", "input": ["a", "b"]}`, no `Authorization` header.
  - `test_sends_bearer_token_when_api_key_set`: header equals `Bearer k`.
  - `test_vectors_are_l2_normalized_and_ordered_by_index`: handler returns `data` out of order with `index` fields; result matches input order and each vector has norm 1.0 (`pytest.approx`).
  - `test_batches_by_batch_size`: 5 texts, `batch_size=2` → handler called 3 times, 5 vectors returned.
  - `test_raises_on_count_mismatch`, `test_raises_on_http_error_status`, `test_raises_on_connect_error` (handler raises `httpx.ConnectError`), `test_raises_on_mixed_dimensions`: all `pytest.raises(EmbeddingError)`.

- [ ] **Step 3: Run** `uv run pytest packages/okf-mcp/tests/test_embeddings.py -v`. Expected: FAIL (module missing).

- [ ] **Step 4: Implement** `embeddings.py` with the signatures above. Create an `httpx.Client(timeout=config.timeout)` when `client` is None and close it afterwards. Wrap every `httpx.HTTPError` and every non-2xx status in `EmbeddingError` with a message naming the URL.

- [ ] **Step 5: Run** the same command. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers packages/okf-mcp/pyproject.toml uv.lock packages/okf-mcp/src/okf_mcp/embeddings.py packages/okf-mcp/tests/test_embeddings.py
git commit -m "feat(okf-mcp): add OpenAI-compatible embedding client"
```

---

### Task 2: Vector store and sync

**Files:**
- Create: `packages/okf-mcp/src/okf_mcp/vector_store.py`
- Test: `packages/okf-mcp/tests/test_vector_store.py`

**Interfaces:**
- Consumes: `okf_core.Storage`, `LocalStorage`, `MemoryStorage`, `INDEX_FILENAME` (from `okf_core`); `okf_mcp.operations._clean_dir` is *not* imported here, `query` receives an already-clean `dir`.
- Produces:
  - `Embedder = Callable[[list[str]], list[list[float]]]` (vectors already normalized)
  - `class VectorStoreError(RuntimeError)`
  - `def default_db_path(storage: Storage) -> Path` — for `LocalStorage` returns `Path(str(storage.root) + ".vectors.db")`; any other storage raises `VectorStoreError` saying to set `OKF_VECTOR_DB`.
  - `class VectorStore`:
    - `__init__(self, path: Path | str) -> None` — opens SQLite (creating parent dirs), sets WAL and a busy timeout, loads `sqlite-vec`; if the `sqlite3` module cannot load extensions or `sqlite_vec` is missing, raises `VectorStoreError` explaining that a Python whose `sqlite3` allows extensions is needed (uv-managed Python works).
    - `sync(self, storage: Storage, embed: Embedder, *, model: str, max_chars: int) -> None`
    - `query(self, storage: Storage, vector: list[float], top_k: int, dir: str = "") -> list[dict]` — each hit `{"dir": str, "path": str, "score": float, "excerpt": str}`, descending score, ties by path; `dir` filters to `_index.md` files at or under it (`""` = all).
    - `close(self) -> None`

- [ ] **Step 1: Write the failing tests** with `MemoryStorage` and a deterministic fake embedder (e.g. maps known words to unit vectors; records the texts it was called with):
  - `test_sync_embeds_every_index_file_once`, `test_second_sync_embeds_nothing_when_unchanged` (fake's call log empty).
  - `test_sync_reembeds_only_changed_file` (edit one `_index.md`, only that text embedded).
  - `test_sync_prunes_deleted_index_file` (deleted file no longer in `query` results).
  - `test_sync_ignores_files_not_named_index_md` (`tables/foo_index.md` never embedded).
  - `test_text_truncated_to_max_chars` (embedder receives `text[:max_chars]`; a change after the cut does not trigger a re-embed).
  - `test_model_change_rebuilds_store` (second sync with a different `model` embeds all again, including a different vector dimension).
  - `test_failed_sync_rolls_back` (embedder raises mid-sync after a first successful sync; old rows still queryable; the exception propagates).
  - `test_wrong_dimension_from_embedder_fails_sync` (embedder returns dimension ≠ stored, same model → `VectorStoreError`, store unchanged).
  - `test_query_ranks_by_cosine_and_respects_top_k` (including `top_k` larger than row count returns all; empty bundle returns `[]`).
  - `test_query_dir_filter` (`dir="tables"` returns `tables/_index.md` and `tables/x/_index.md`, not `views/_index.md`; root file has `dir == ""` and `path == "_index.md"`).
  - `test_rows_scoped_by_storage_location` (two `MemoryStorage`s with distinct `location` values sharing one db do not see each other's rows; `MemoryStorage.location` is already defined in `storage.py`).
  - `test_hit_excerpt_prefers_description_then_first_200_chars`.
  - `test_default_db_path_is_sibling_and_stable` using `tmp_path`: `LocalStorage(tmp_path/"b")`, `LocalStorage(str(tmp_path/"b") + "/")` and `LocalStorage("file://…")`-style opens (via `open_storage`) all give `tmp_path/"b.vectors.db"`; `MemoryStorage` raises `VectorStoreError` mentioning `OKF_VECTOR_DB`.

- [ ] **Step 2: Run** `uv run pytest packages/okf-mcp/tests/test_vector_store.py -v`. Expected: FAIL (module missing).

- [ ] **Step 3: Implement** `vector_store.py`. Schema: table `meta(key, value)` holding `model` and `dim`; table `vectors(root TEXT, key TEXT, hash TEXT, embedding BLOB, excerpt TEXT, PRIMARY KEY(root, key))`. Store embeddings as float32 blobs (`sqlite_vec.serialize_float32`) and rank with `vec_distance_cosine`; score = `1 - distance`. `sync` lists `storage.iter_files(suffix="_index.md")` and keeps only keys whose basename equals `INDEX_FILENAME`; hashes `text[:max_chars]` with sha256; embeds changed files in one `embed` call; wraps the whole thing in one transaction (`BEGIN IMMEDIATE`), clearing every row first when `model` or the embedder's dimension differs from `meta`. A threading lock serializes `sync` calls within the process. `excerpt`: the `description` frontmatter value if present (parse via `okf_core.OKFDocument`; check `packages/okf-core/src/okf_core/document.py` for the parse call) else the first 200 characters of the file.

- [ ] **Step 4: Run** the same command. Expected: PASS (if `sqlite3` cannot load extensions on this Python, the failure message from `VectorStore.__init__` should say so; use `uv run` with the project's pinned Python).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/vector_store.py packages/okf-mcp/tests/test_vector_store.py
git commit -m "feat(okf-mcp): add sqlite-vec store with hash-based sync"
```

---

### Task 3: `search` operation, settings and MCP tool

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py` (add `search_indexes`)
- Modify: `packages/okf-mcp/src/okf_mcp/server.py` (Settings fields, `search` tool)
- Test: `packages/okf-mcp/tests/test_operations.py` (operation), `packages/okf-mcp/tests/test_server.py` (settings and tool wiring)

**Interfaces:**
- Consumes: `EmbeddingConfig`, `embed_texts`, `EmbeddingError` (Task 1); `VectorStore`, `default_db_path`, `Embedder`, `VectorStoreError` (Task 2); existing `operations._clean_dir`, `open_storage`.
- Produces:
  - `def search_indexes(bundle_root: "Path | str | Storage", query: str, top_k: int = 5, dir: str | None = None, *, config: EmbeddingConfig | None, max_chars: int = 6000, db_path: Path | str | None = None, embed: Embedder | None = None) -> list[dict]` in `operations.py`. `embed` is a test seam; when None it is `lambda texts: embed_texts(texts, config)`.
  - Settings fields: `embedding_url: str | None`, `embedding_model: str | None`, `embedding_api_key: str | None`, `embedding_max_chars: int = 6000`, `vector_db: str | None`.
  - MCP tool `search(ctx, query, top_k=5, dir=None, bundle_root=None) -> list[dict]`.

- [ ] **Step 1: Write the failing operation tests** in `test_operations.py` (fake `embed`, `MemoryStorage`, explicit `db_path=tmp_path/"v.db"`):
  - `test_search_returns_closest_index_first_with_read_index_shape` (hit keys `dir`, `path`, `score`, `excerpt`; `path` like `tables/_index.md`).
  - `test_search_syncs_before_querying` (an `_index.md` added after a first search shows up in the second).
  - `test_search_rejects_blank_query_without_embedding` (`""` and `"   "` → `ValueError`; fake never called).
  - `test_search_rejects_top_k_out_of_range` (0 and 21 → `ValueError`).
  - `test_search_rejects_dir_escaping_bundle` (`"../x"` → `ValueError`).
  - `test_search_errors_when_embedding_not_configured` (`config=None` and no `embed` → `ValueError` mentioning `OKF_EMBEDDING_URL` and `OKF_EMBEDDING_MODEL`).
  - `test_search_raises_when_embedder_fails` (embedder raises `EmbeddingError` → propagates; no partial results).
  - `test_search_on_non_local_storage_requires_db_path` (`MemoryStorage`, no `db_path` → `VectorStoreError`).
  - `test_write_tools_never_call_embedder` (run `add_concept`, `patch_concept`, `move_concept`, `delete_concept`, `describe_directory`, `reindex_bundle` against a bundle with `search_indexes`'s fake never invoked; assert the fake's call log is empty and no `.vectors.db` file appears).

- [ ] **Step 2: Run** `uv run pytest packages/okf-mcp/tests/test_operations.py -k search -v`. Expected: FAIL (`search_indexes` missing).

- [ ] **Step 3: Implement `search_indexes`** in `operations.py` per the signature: validate query/`top_k`, `_clean_dir(dir)`, `open_storage`, resolve `db_path or default_db_path(storage)`, open `VectorStore`, `sync(..., model=config.model, max_chars=max_chars)`, embed the query, `query(...)`, close the store in `finally`.

- [ ] **Step 4: Run** the same command. Expected: PASS.

- [ ] **Step 5: Write the failing server tests** in `test_server.py`, mirroring how existing tests there call tools:
  - `test_settings_read_embedding_env_vars` (using `_use_settings`; all five new fields populate, `embedding_max_chars` defaults to 6000).
  - `test_search_tool_passes_settings_and_root_to_operation` (monkeypatch `operations.search_indexes`; assert it receives the resolved root, the config built from settings, `max_chars`, and `db_path=settings.vector_db`).
  - `test_search_tool_without_embedding_settings_errors_but_other_tools_work` (no `OKF_EMBEDDING_*` set: `search` raises; `list_` on the same bundle succeeds).

- [ ] **Step 6: Run** `uv run pytest packages/okf-mcp/tests/test_server.py -k "search or embedding" -v`. Expected: FAIL.

- [ ] **Step 7: Implement** the Settings fields and the `search` tool in `server.py`. Build `EmbeddingConfig` only when both `embedding_url` and `embedding_model` are set, else pass `config=None`. Resolve the root with the existing `_root(bundle_root, ctx)`. Run the blocking call with `await asyncio.to_thread(...)`. The docstring must tell the agent to follow up with `read_index` / `list` / `get` on the returned `dir`.

- [ ] **Step 8: Run the full suite** `uv run pytest`. Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py packages/okf-mcp/src/okf_mcp/server.py packages/okf-mcp/tests/test_operations.py packages/okf-mcp/tests/test_server.py
git commit -m "feat(okf-mcp): add search tool over _index.md vectors"
```

---

### Task 4: Documentation

**Files:**
- Modify: `packages/okf-mcp/README.md`, `packages/okf-mcp/.env.example`, `CLAUDE.md`, `docs/TODO.md`

**Interfaces:** none.

- [ ] **Step 1: README.** Add a "Search (`search`)" section: what it returns, the five `OKF_*` variables with defaults, the sibling `<bundle_root>.vectors.db` location and `OKF_VECTOR_DB` override, that the first search after changes embeds the changed files, and a local-server example (e.g. Ollama `http://localhost:11434/v1`). Also list `search` in the tools list.

- [ ] **Step 2: `.env.example`.** Add commented entries for the five new variables. (If your tools cannot edit this dotfile, note it in the hand-off and have the user apply the lines.)

- [ ] **Step 3: `CLAUDE.md`.** In the `okf-mcp` paragraph, add `search` (vector search over `_index.md`, sqlite-vec, local OpenAI-compatible embeddings) and link the spec.

- [ ] **Step 4: `docs/TODO.md`.** Mark item 3 "Done — `search` tool in `okf-mcp`" with the spec path.

- [ ] **Step 5: Run** `uv run pytest`. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/okf-mcp/README.md packages/okf-mcp/.env.example CLAUDE.md docs/TODO.md
git commit -m "docs(okf-mcp): document the search tool"
```
