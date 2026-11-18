# Remove Bundles + Package Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the Python packages into core / backend / mcp, make okf-web2
the `okf-web` portal, then remove bundles so that each workspace is one OKF
bundle and each MCP server serves exactly one workspace.

**Architecture:** PR 1 (Tasks 1–3) only moves code: create `okf-backend`
(operations, search, settings, REST API), make okf-mcp and okf-claude depend
on it, delete the old Python `okf-web` and its React frontend, and move
`okf-web2` to `packages/okf-web`. PR 2 (Tasks 4–12) removes bundles, from core
outward: core → backend → REST → MCP → okf-claude → portal → migration → docs.

**Tech Stack:** Python 3.12, uv workspace, hatchling, PyYAML, FastMCP (`mcp`),
pydantic-settings, sqlite-vec, httpx, Starlette/uvicorn, pytest; portal: Bun,
Vite, React 19, wouter, TanStack Query, Vitest + MSW.

**Spec:** `docs/superpowers/specs/2026-11-18-okf-remove-bundles-and-package-split-design.md`

## Global Constraints

- okf-core runtime dependencies: `pyyaml>=6.0` only.
- `.okf/workspace.json` v2 shape: `{"version": 2, "color"?: "<crayon>"}`. Reading v1 raises `ValueError` mentioning `okf-migrate-v2`.
- MCP stdio: `okf-mcp --workspace <name>` (required). MCP streamable-http: header `X-OKF-Workspace` (required on every request). `--workspace` together with `--transport streamable-http` is an error.
- Removed everywhere: `OKF_WORKSPACE`, `OKF_BUNDLE`, `--bundle`, `X-OKF-Bundle`, the `workspace`/`bundle`/`bundles` tool arguments, and the `bundles` map in `workspace.json`.
- MCP tools after PR 2: `add, patch, get, list, read_index, move, delete, reindex, describe, mkdir, search`. Every result includes `"workspace": <name>`.
- `search(query, top_k=5, paths=None)`: hits are `{kind: "index", dir, path, score, excerpt}`.
- Tests never touch the real home: pass `root=` or set `OKF_HOME` to `tmp_path`.
- All bundle file I/O goes through `Storage`; no `pathlib` I/O on concept files.
- okf-claude hooks never fail a session: errors go to `<OKF_HOME>/logs/okf-claude.log`, and the hook exits 0.
- REST API binds 127.0.0.1, no auth; `--read-only` blocks writes with 403.

## Review Focus

1. **`.okf/` and root `_log.md` now sit inside the bundle root.** Reindex, validate, tree, list, and `Bundle.load` must not show `.okf`, write `.okf/_index.md`, or report violations for `workspace.json`/`vectors.db`. Test: Task 4.
2. **An existing `vectors.db` with the old `root` column.** The first search must rebuild it rather than crash or return stale bundle rows. Test: Task 6.
3. **A hostile or unknown `X-OKF-Workspace` (`../etc`, blank, a name that doesn't exist).** The tool call fails, the error lists existing workspaces, and nothing outside the registry is touched. Test: Task 8.
4. **Hooks installed by the old okf-claude still pass `--bundle b`.** The hook must exit 0 and log "re-run `okf-claude setup`" instead of an argparse crash. Test: Task 9.
5. **Migration input variety:** links with `#anchor`, `https://`, `//host`, relative links, and a second run. External and relative links stay unchanged, the anchor is preserved, and the second run is a no-op. Test: Task 11.

---

# PR 1 — Package split (no behaviour change)

Branch: `refactor/package-split`.

### Task 1: Create `okf-backend` with operations, search, and settings

**Files:**
- Create: `packages/okf-backend/pyproject.toml` (name `okf-backend`; deps `okf-core`, `pydantic-settings>=2.0`, `sqlite-vec>=0.1.9`, `httpx>=0.28.1`, `starlette>=0.40`, `uvicorn>=0.30`; `[tool.uv.sources] okf-core = { workspace = true }`; wheel package `src/okf_backend`), `packages/okf-backend/README.md`, `packages/okf-backend/src/okf_backend/__init__.py`
- Move (`git mv`): `packages/okf-mcp/src/okf_mcp/{operations,embeddings,vector_store}.py` → `packages/okf-backend/src/okf_backend/`; `packages/okf-mcp/tests/{test_operations,test_embeddings,test_vector_store}.py` → `packages/okf-backend/tests/`
- Create: `packages/okf-backend/src/okf_backend/settings.py`
- Modify: `packages/okf-mcp/pyproject.toml` (deps: `mcp>=1.0`, `pydantic-settings>=2.0`, `okf-core`, `okf-backend`; drop sqlite-vec/httpx), `packages/okf-mcp/src/okf_mcp/server.py`, `packages/okf-claude/pyproject.toml` (`okf-mcp` → `okf-backend`), `packages/okf-claude/src/okf_claude/episodes.py`, `packages/okf-web/src/okf_web/{app,server}.py`, `packages/okf-web/pyproject.toml` (add `okf-backend`)
- Test: `packages/okf-backend/tests/test_package_import.py`

**Interfaces:**
- Produces: `okf_backend.operations` (same functions as today's `okf_mcp.operations`), `okf_backend.embeddings.EmbeddingConfig`, `okf_backend.vector_store.{VectorStore, workspace_db_path}`, and
  `okf_backend.settings.BackendSettings(BaseSettings)` with fields `embedding_url: str | None`, `embedding_model: str | None`, `embedding_api_key: str | None`, `embedding_max_chars: int = 6000` (env prefix `OKF_`, `env_file=".env"`, `extra="ignore"`), plus method `embedding_config() -> EmbeddingConfig | None` (`None` unless both url and model are set).
- `okf_mcp.server.Settings` keeps only `workspace`/`bundle` until Task 8; it uses `BackendSettings` for the embedding fields.

- [ ] **Step 1: Write the failing test** `test_package_import.py`:

```python
def test_backend_exports():
    from okf_backend import operations
    from okf_backend.embeddings import EmbeddingConfig
    from okf_backend.settings import BackendSettings
    assert callable(operations.add_concept)
    assert BackendSettings(_env_file=None).embedding_config() is None

def test_backend_settings_builds_config(monkeypatch):
    from okf_backend.settings import BackendSettings
    monkeypatch.setenv("OKF_EMBEDDING_URL", "http://h/v1")
    monkeypatch.setenv("OKF_EMBEDDING_MODEL", "m")
    cfg = BackendSettings(_env_file=None).embedding_config()
    assert (cfg.url, cfg.model) == ("http://h/v1", "m")
```

- [ ] **Step 2:** Run `uv run pytest packages/okf-backend -v`. Expected: FAIL (`ModuleNotFoundError: okf_backend`).
- [ ] **Step 3:** Create the package and `git mv` the modules and tests. Replace `okf_mcp.operations|embeddings|vector_store` imports with `okf_backend.*` everywhere (`grep -rn "okf_mcp\.\(operations\|embeddings\|vector_store\)\|from okf_mcp import operations" packages`). Replace the three inline `EmbeddingConfig(...) if ... else None` blocks (okf_mcp/server.py `search`, okf_web/server.py `build_app`) with `BackendSettings().embedding_config()`. Run `uv sync`.
- [ ] **Step 4:** Run `uv run pytest`. Expected: all pass (same count as before plus 2).
- [ ] **Step 5:** Commit `refactor: extract okf-backend (operations, search, settings) from okf-mcp`.

### Task 2: Move the REST API into okf-backend and delete the old okf-web

**Files:**
- Move: `packages/okf-web/src/okf_web/app.py` → `packages/okf-backend/src/okf_backend/api.py`; `.../okf_web/server.py` → `.../okf_backend/server.py`; `packages/okf-web/tests/test_web_{api,server,workspaces}.py` → `packages/okf-backend/tests/test_api{,_server,_workspaces}.py`
- Modify: `packages/okf-backend/pyproject.toml` (`[project.scripts] okf-backend = "okf_backend.server:main"`)
- Delete: the whole `packages/okf-web/` directory (pyproject, `src/okf_web`, `frontend/`, README). The untracked `packages/okf-web/frontend/.env.example` goes with it.

**Interfaces:**
- Produces: `okf_backend.api.create_app(registry, *, read_only=False, search_config=None, search_max_chars=6000, static_dir=None) -> Starlette` (signature unchanged), CLI `okf-backend [--read-only] [--host] [--port 8765] [--static DIR]`.
- With no `--static`, the server serves only the API: no bundled static dir and no `STATIC_DIR` constant. `--static DIR` without `index.html` exits with `okf-backend: --static DIR: no index.html (build the frontend first)`.

- [ ] **Step 1:** In the moved `test_api_server.py`, replace the bundled-static test with:

```python
def test_no_static_serves_api_only(tmp_path, monkeypatch):
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    app = server.build_app(server.parse_args([]))
    assert not any(getattr(r, "path", "") == "/{path:path}" for r in app.routes)
```

- [ ] **Step 2:** Run `uv run pytest packages/okf-backend -v`. Expected: FAIL on imports (`okf_web`).
- [ ] **Step 3:** Move the files, rename the imports `okf_web.app` → `okf_backend.api` and `okf_web.server` → `okf_backend.server`, set `prog="okf-backend"`, remove `STATIC_DIR`, delete `packages/okf-web`, run `uv sync`.
- [ ] **Step 4:** Run `uv run pytest`. Expected: all pass.
- [ ] **Step 5:** Commit `refactor: move REST API to okf-backend; drop old okf-web package and frontend`.

### Task 3: Move okf-web2 to `packages/okf-web` (the portal)

**Files:**
- Move: `git mv packages/okf-web2 packages/okf-web`
- Modify: root `pyproject.toml` (`exclude = ["packages/okf-web"]`), `packages/okf-web/package.json` (`"name": "okf-web"`), `packages/okf-web/vite.config.ts` (comment: `uv run okf-backend`), `packages/okf-web/src/lib/api.ts` header comment (→ `packages/okf-backend/src/okf_backend/api.py`), `CLAUDE.md`, `docs/TECHNICAL.md`, `README.md` (package list per spec §6; run commands `uv run okf-backend --static packages/okf-web/dist`)

- [ ] **Step 1:** Run `git mv` and the edits; `rm -rf packages/okf-web/node_modules && cd packages/okf-web && bun install`.
- [ ] **Step 2:** Run `cd packages/okf-web && bun run typecheck && bun run test`. Expected: PASS.
- [ ] **Step 3:** Run `uv sync && uv run pytest` and `grep -rn "okf-web2\|okf_web\b\|okf_mcp.operations" --exclude-dir=node_modules --exclude-dir=docs .`. Expected: tests pass; grep prints nothing.
- [ ] **Step 4:** Commit `refactor: okf-web2 becomes the okf-web portal`. Open PR 1.

---

# PR 2 — Remove bundles; one workspace per MCP server

Branch: `feat/remove-bundles` (from main after PR 1 merges).

### Task 4: Core — workspace is the bundle; workspace.json v2

**Files:**
- Modify: `packages/okf-core/src/okf_core/workspace.py`, `packages/okf-core/src/okf_core/__init__.py`
- Test: `packages/okf-core/tests/test_workspace.py` (rewrite bundle tests)

**Interfaces:**
- Removes: `Workspace.indexes`, `create_index`, `bundle_storage`, `index_root`, `load_index`, `description`, `set_description`, `bundles_info`; the export `MAX_DESCRIPTION_CHARS`.
- Produces: `Workspace.load() -> Bundle` (equivalent to `Bundle.load(self.storage)`). `_read_meta()` returns `{"version": 2}` when the file is missing; version 1 raises `ValueError("… workspace.json is version 1; run okf-migrate-v2")`. `_WORKSPACE_FILE_VERSION = 2`. `color()`/`set_color()` are unchanged.

- [ ] **Step 1: Write failing tests**

```python
def test_v1_workspace_json_points_to_migration(tmp_path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.storage.write_text(".okf/workspace.json", '{"version": 1, "bundles": {}}')
    with pytest.raises(ValueError, match="okf-migrate-v2"):
        ws.color()

def test_set_color_writes_v2(tmp_path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.set_color("pink")
    assert json.loads(ws.storage.read_text(".okf/workspace.json")) == {"version": 2, "color": "pink"}

def test_workspace_root_is_the_bundle_and_ignores_metadata(tmp_path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.set_color("blue")
    ws.storage.write_text(".okf/vectors.db", "x")
    ws.storage.write_text("notes/a.md", "---\ntype: note\n---\nhi\n")
    assert [c.id for c in ws.load().concepts] == ["notes/a"]
    written = regenerate_indexes(ws.storage)
    assert not any(k.startswith(".okf") for k in written)
    assert validate_bundle(ws.path) == []

def test_bundle_methods_are_gone():
    assert not hasattr(Workspace, "indexes") and not hasattr(Workspace, "bundle_storage")
```

(Adjust the `validate_bundle` call and the frontmatter of `a.md` to whatever makes a conformant concept per `CONFORMANCE.md`. The point of the test is that `.okf/` adds no violations.)

- [ ] **Step 2:** Run `uv run pytest packages/okf-core/tests/test_workspace.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. If the walks in `index.py`/`validate.py` reach `.okf/`, make them skip top-level entries starting with `.`.
- [ ] **Step 4:** Run `uv run pytest packages/okf-core -v`. Expected: PASS. (Other packages are red until Tasks 6–9; that is expected inside PR 2.)
- [ ] **Step 5:** Commit `feat(core)!: workspace is the OKF bundle; workspace.json v2`.

### Task 5: Core — `map_absolute_links` and `export_subtree`

**Files:**
- Modify: `packages/okf-core/src/okf_core/links.py`, `packages/okf-core/src/okf_core/__init__.py`
- Create: `packages/okf-core/src/okf_core/export.py`
- Test: `packages/okf-core/tests/test_links.py`, `packages/okf-core/tests/test_export.py`

**Interfaces:**
- Produces: `map_absolute_links(body: str, fn: Callable[[str], str | None]) -> str`. It calls `fn` with the bundle-relative target of every markdown link whose href starts with exactly one `/` (no `//`, no `scheme:`), with the leading `/` and any `#fragment` removed. A string return replaces the target (the `/` and the fragment are put back). `None` leaves the link unchanged.
- Produces: `export_subtree(storage: Storage, path: str, dest: Storage) -> int`. It copies every file under `path/` into `dest` with keys relative to `path`, rewrites `/path/x.md` → `/x.md` in `.md` files, leaves links outside the subtree unchanged, and returns the number of files copied. `FileNotFoundError` if `path` is not a directory.

- [ ] **Step 1: Write failing tests**

```python
def test_map_absolute_links_skips_external_relative_and_keeps_fragment():
    body = "[a](/x/y.md#h) [b](https://e.com/z.md) [c](//cdn/z.md) [d](../r.md)"
    out = map_absolute_links(body, lambda t: "p/" + t)
    assert out == "[a](/p/x/y.md#h) [b](https://e.com/z.md) [c](//cdn/z.md) [d](../r.md)"

def test_export_subtree_rebases_links():
    src, dst = MemoryStorage(), MemoryStorage()
    src.write_text("p/a.md", "see [b](/p/q/b.md) and [o](/other/o.md)")
    src.write_text("p/q/b.md", "b")
    assert export_subtree(src, "p", dst) == 2
    assert dst.read_text("a.md") == "see [b](/q/b.md) and [o](/other/o.md)"
```

- [ ] **Step 2:** Run `uv run pytest packages/okf-core/tests/test_links.py packages/okf-core/tests/test_export.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. Reuse the link regex and skip rules in `links.py` / `bundle.extract_link_ids`; don't write a second parser.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(core): map_absolute_links and export_subtree`.

### Task 6: Backend — workspace-wide operations and search by path

**Files:**
- Modify: `packages/okf-backend/src/okf_backend/operations.py` (delete `create_bundle`; rewrite `search_workspace`), `packages/okf-backend/src/okf_backend/vector_store.py`
- Test: `packages/okf-backend/tests/test_operations.py`, `packages/okf-backend/tests/test_vector_store.py`

**Interfaces:**
- Produces: `search_workspace(workspace, query, top_k=5, paths: list[str] | None = None, *, config, max_chars=6000, embed=None, db_path=None) -> list[dict]`. Hits are `{kind: "index", dir, path, score, excerpt}`. `paths` entries are cleaned with `_clean_dir`; an empty list or `None` means the whole workspace; a path that is not a directory raises `FileNotFoundError("no directory 'x' in workspace 'w'")`.
- Produces: `VectorStore.sync(storage, embed, *, model, max_chars) -> None` and `VectorStore.query(vector, top_k, *, paths: list[str] | None = None) -> list[dict]`. Schema: `vectors(key TEXT PRIMARY KEY, hash, embedding, excerpt)`. When an existing DB has a `root` column (old schema), drop and recreate both tables on open. `prune_bundles` and description rows are removed.
- All other operations (`add_concept`, …, `create_directory`, `reindex_bundle`) are unchanged and take the workspace's `Storage`.

- [ ] **Step 1: Write failing tests**

```python
def test_search_filters_by_path_prefixes(ws_with_dirs, fake_embed):
    # ws has a/_index.md, a/x/_index.md, b/_index.md
    hits = search_workspace(ws_with_dirs, "q", 10, ["a"], config=CFG, embed=fake_embed)
    assert {h["path"] for h in hits} == {"a/_index.md", "a/x/_index.md"}
    assert all(set(h) == {"kind", "dir", "path", "score", "excerpt"} for h in hits)

def test_search_unknown_path_errors(ws_with_dirs, fake_embed):
    with pytest.raises(FileNotFoundError, match="no directory 'zzz'"):
        search_workspace(ws_with_dirs, "q", paths=["zzz"], config=CFG, embed=fake_embed)

def test_old_schema_db_is_rebuilt(tmp_path, fake_embed, ws_with_dirs):
    db = tmp_path / "v.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE vectors(root TEXT, key TEXT, hash TEXT, embedding BLOB, excerpt TEXT, PRIMARY KEY(root, key))")
    con.execute("INSERT INTO vectors VALUES('old','', 'h', x'00', 'stale')"); con.commit(); con.close()
    hits = search_workspace(ws_with_dirs, "q", 10, config=CFG, embed=fake_embed, db_path=db)
    assert "stale" not in {h["excerpt"] for h in hits} and hits
```

(`ws_with_dirs`, `fake_embed`, `CFG`: adapt the existing fixtures in `test_operations.py`.) Delete the tests for `create_bundle`, bundle descriptions, and `dir requires exactly one bundle`.

- [ ] **Step 2:** Run `uv run pytest packages/okf-backend/tests/test_operations.py packages/okf-backend/tests/test_vector_store.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. The query filter is `key` matching any `prefix + "/"` (SQL `OR` over `substr(key,1,len)=?`), with `ORDER BY score DESC, key ASC LIMIT ?`.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(backend)!: workspace-wide search filtered by paths; drop bundles`.

### Task 7: Backend REST — drop the `/indexes/{index}` segment

**Files:**
- Modify: `packages/okf-backend/src/okf_backend/api.py`
- Test: `packages/okf-backend/tests/test_api.py`, `packages/okf-backend/tests/test_api_workspaces.py`

**Interfaces:**
- Produces routes: `GET /api/info`; `GET|POST /api/workspaces` (items `{name, color}`; no `indexes`); `POST /api/workspaces/{workspace}/color`; and under `/api/workspaces/{workspace}`: `GET /tree`, `GET /index`, `GET|POST /concepts`, `GET|PATCH|DELETE /concepts/{concept_id:path}`, `POST /move`, `POST /describe`, `GET|POST /dirs`, `POST /reindex`, `GET /overview`, `GET /search?q=&top_k=&paths=a&paths=b` (repeated `paths`; response is a list of hits).
- Removed: `POST /api/workspaces/{ws}/indexes`, `GET /bundle`, `POST /bundle/describe`.
- Storage for every per-workspace route: `registry.get(ws).storage`.

- [ ] **Step 1: Write failing tests** (with the existing Starlette `TestClient` fixture):

```python
def test_concept_crud_at_workspace_root(client):
    r = client.post("/api/workspaces/w/concepts", json={"concept_id": "notes/a", "frontmatter": {"type": "note"}, "body": "x"})
    assert r.status_code == 201
    assert client.get("/api/workspaces/w/concepts/notes/a").json()["id"] == "notes/a"
    assert client.get("/api/workspaces/w/indexes/b/tree").status_code == 404

def test_workspace_list_has_no_indexes(client):
    assert client.get("/api/workspaces").json() == [{"name": "w", "color": None}]

def test_search_passes_repeated_paths(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(operations, "search_workspace", lambda ws, q, k, paths, **kw: seen.update(paths=paths) or [])
    client.get("/api/workspaces/w/search?q=x&paths=a&paths=b/c")
    assert seen["paths"] == ["a", "b/c"]
```

- [ ] **Step 2:** Run `uv run pytest packages/okf-backend/tests/test_api*.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. Rename `bundle_routes(prefix, resolve)` to `workspace_routes()` with prefix `/api/workspaces/{workspace}`, and pass `paths = request.query_params.getlist("paths") or None` to search.
- [ ] **Step 4:** Run `uv run pytest packages/okf-backend -v`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(api)!: per-workspace routes; remove index segment`.

### Task 8: MCP — one workspace per server

**Files:**
- Delete: `packages/okf-mcp/src/okf_mcp/target.py`, `packages/okf-mcp/tests/test_target.py`
- Modify: `packages/okf-mcp/src/okf_mcp/server.py`, `packages/okf-mcp/.env.example` (keep only the `OKF_HOME` note and the `OKF_EMBEDDING_*` block)
- Test: `packages/okf-mcp/tests/test_server.py` (rewrite fixtures: workspace `w` with dirs, no bundles; drop `OKF_WORKSPACE`/`OKF_BUNDLE` from `_ENV`)

**Interfaces:**
- Consumes: `okf_backend.operations.*`, `search_workspace` (Task 6), `BackendSettings` (Task 1).
- Produces in `server.py`: module state `_fixed_workspace: str | None`, `WORKSPACE_HEADER = "x-okf-workspace"`, and `def workspace(ctx) -> Workspace`. That function uses `_fixed_workspace` when set, and otherwise the header. If both are missing, it raises `ValueError("no workspace: start okf-mcp with --workspace <name> (stdio) or send the X-OKF-Workspace header (http); workspaces: …")`. If the name is unknown or invalid, it raises `ValueError("unknown workspace '<name>'; workspaces: a, b")`, catching the name validation and `FileNotFoundError` from `registry().get`.
- Tools: `add(concept_id, frontmatter, body)`, `patch`, `get`, `list`, `read_index`, `move`, `delete`, `reindex`, `describe` (same parameters as today, minus `workspace`/`bundle`), `mkdir(dir: str, description: str | None = None)` → `operations.create_directory`, and `search(query, top_k=5, paths=None)`. Each returns `{"workspace": name, ...result}` (list results stay wrapped as `items`).
- `main(argv)`: adds `--workspace NAME`. stdio without it → `SystemExit("okf-mcp: --workspace is required for stdio; workspaces: …")`. `--workspace` with `--transport streamable-http` → `SystemExit("okf-mcp: --workspace is not used with streamable-http; send the X-OKF-Workspace header")`. An unknown name on stdio is checked at startup and exits with the list of workspaces.

- [ ] **Step 1: Write failing tests**

```python
def test_tool_set():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"add","patch","get","list","read_index","move","delete","reindex","describe","mkdir","search"}
    for t in asyncio.run(mcp.list_tools()):
        assert "workspace" not in t.inputSchema["properties"] and "bundle" not in t.inputSchema["properties"]

def test_header_selects_workspace(home):
    out = run(server.add(_ctx({"x-okf-workspace": "w"}), "notes/a", {"type": "note"}, "x"))
    assert out["workspace"] == "w"

@pytest.mark.parametrize("hdr", ["../etc", "", "nope"])
def test_bad_header_fails_and_lists(home, hdr):
    with pytest.raises(ValueError, match="workspaces: w"):
        run(server.list_(_ctx({"x-okf-workspace": hdr})))

def test_fixed_workspace_wins_on_stdio(home, monkeypatch):
    monkeypatch.setattr(server, "_fixed_workspace", "w")
    assert run(server.list_(_ctx()))["workspace"] == "w"

def test_main_requires_workspace_for_stdio(home, monkeypatch):
    monkeypatch.setattr(mcp, "run", lambda **kw: None)
    with pytest.raises(SystemExit, match="--workspace is required"):
        server.main([])
    with pytest.raises(SystemExit, match="not used with streamable-http"):
        server.main(["--transport", "streamable-http", "--workspace", "w"])
    server.main(["--workspace", "w"])  # ok

def test_search_passes_paths(home, monkeypatch): ...  # adapt _capture_search: assert seen["paths"] == ["a"]
def test_mkdir_creates_directory(home): ...  # read_index on the new dir succeeds
```

- [ ] **Step 2:** Run `uv run pytest packages/okf-mcp -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. Move the module docstring and tool docstrings to the new model ("paths relative to the workspace root"). Delete `_TARGET_DOC`, `_with_target_doc`, `_target`, `_bundle`, and the four workspace/bundle tools.
- [ ] **Step 4:** Run `uv run pytest packages/okf-mcp -v`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(mcp)!: one workspace per server via --workspace / X-OKF-Workspace`.

### Task 9: okf-claude — workspace only

**Files:**
- Modify: `packages/okf-claude/src/okf_claude/{cli,installer,episodes,hooks}.py`, prompts in `src/okf_claude/prompts/` that mention bundles
- Test: `packages/okf-claude/tests/test_{cli,installer,episodes,hooks}.py`

**Interfaces:**
- `InstallConfig` loses `bundle`. `ensure_target(workspace: str, *, create: bool) -> list[str]`. MCP registration is `claude mcp add --scope <scope> okf -- <abs okf-mcp> --workspace <ws>` with `-e` only for `cfg.server_env` (no `OKF_WORKSPACE`/`OKF_BUNDLE`).
- `episodes.workspace_storage(workspace: str) -> Storage` replaces `bundle_storage`. Episodes are written at `episodes/<date>-<session8>` relative to the workspace root.
- `hook_command` emits `okf-claude hook <event> --workspace <ws> ...`. The `hook` subparser uses `parse_known_args`: if it gets unknown args (e.g. `--bundle b` from an old install), it logs `"ignoring stale hook arguments [...]; re-run okf-claude setup"` and continues with the workspace.
- `setup`/`uninstall` drop `--bundle/-b`.

- [ ] **Step 1: Write failing tests**

```python
def test_mcp_add_pins_workspace_by_parameter(cfg, fake_runner):
    installer.register_mcp(cfg, runner=fake_runner)  # use the existing registration function name
    argv = fake_runner.calls[0]
    assert argv[-2:] == ["--workspace", "w"] and not any("OKF_BUNDLE" in a or "OKF_WORKSPACE" in a for a in argv)

def test_episode_written_at_workspace_root(home):
    ...  # write_episode(...) then WorkspaceRegistry().get("w").storage.exists("episodes/<id>.md")

def test_stale_bundle_hook_arg_exits_zero_and_logs(home, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["hook", "session-start", "--workspace", "w", "--bundle", "b"])
    assert e.value.code == 0
    assert "re-run okf-claude setup" in episodes.log_path().read_text()
```

- [ ] **Step 2:** Run `uv run pytest packages/okf-claude -v`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest` (whole suite). Expected: PASS. PR 2's Python side is now green.
- [ ] **Step 5:** Commit `feat(claude)!: pin okf-claude to a workspace only`.

### Task 10: Portal — workspace scope, no index picker

**Files:**
- Modify: `packages/okf-web/src/lib/{api,queries,scope}.ts(x)`, `packages/okf-web/src/App.tsx`, `packages/okf-web/src/pages/{WorkspacesPage,WorkspacePage,SearchPage,DirPage,ConceptPage,ConceptForm}.tsx`, `packages/okf-web/src/components/{Tree,Crumbs,Dialogs}.tsx`, `packages/okf-web/src/test/fakeBackend.ts`, `packages/okf-web/src/App.test.tsx`
- Rename: `pages/IndexLayout.tsx` → `pages/WorkspaceLayout.tsx`

**Interfaces:**
- `Scope = { ws: string }`; `base(s) = /api/workspaces/${seg(s.ws)}`. Removed: `IndexInfo`, `BundleInfo`, `api.createIndex`, `api.bundle`, `api.describeBundle`. `WorkspaceInfo = { name; color }`. `Hit = { kind: "index"; dir; path; score; excerpt }`. `api.search(s, q, paths?: string[])`.
- Query keys: `keys.ws(s) = ["ws", s.ws]`, and everything else nests under it.
- Routes: `#/` workspaces; `#/w/:ws/` workspace root (layout + tree); `#/w/:ws/d/<dir>`; `#/w/:ws/c/<id>`; `#/w/:ws/search`. "Create index" becomes "New folder" (`api.createDir`). The root description is edited through `describeDir(s, "", text)`.

- [ ] **Step 1:** Update `fakeBackend.ts` to the Task 7 routes, and update `App.test.tsx` so that, for workspace `w`, it asserts: visiting `#/w/w/` shows the root tree with no index picker; creating a folder from the workspace page calls `POST /api/workspaces/w/dirs`; a search hit links to `#/w/w/d/<hit.dir>`.
- [ ] **Step 2:** Run `cd packages/okf-web && bun run test`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `bun run typecheck && bun run test && bun run build`. Expected: PASS. Then smoke test: `uv run okf-backend --static packages/okf-web/dist` and use the `run` skill to load `/#/` against a temporary `OKF_HOME`.
- [ ] **Step 5:** Commit `feat(web)!: portal scoped to workspaces; remove index picker`.

### Task 11: Migration script `okf-migrate-v2`

**Files:**
- Create: `packages/okf-backend/src/okf_backend/migrate.py`; script `okf-migrate-v2 = "okf_backend.migrate:main"` in `packages/okf-backend/pyproject.toml`
- Test: `packages/okf-backend/tests/test_migrate.py`

**Interfaces:**
- Consumes: `map_absolute_links` (Task 5), `operations.reindex_bundle`, `OKFDocument`.
- Produces: `migrate_workspace(storage: Storage, *, dry_run: bool = False) -> list[str]` (one line per action or warning) and `main(argv=None)` (flags `--dry-run`; iterates `WorkspaceRegistry().list()`; prints the lines grouped by workspace). Reads v1 JSON directly, without going through `Workspace`. A v2 workspace returns `["already v2"]` and changes nothing. A missing `workspace.json` counts as v1 with no descriptions.
- Algorithm, per old bundle `B` (visible top-level dir), following spec §7: in each `B/**/*.md` (excluding `_index.md`/`_log.md`), rewrite `/t` → `/B/t`. Copy `bundles[B].description` into `B/_index.md` frontmatter `description` only when it is absent there; otherwise warn `"kept _index.md description for B"`. Remove `okf_version` from each `B/_index.md` and set the highest one on the root `_index.md`, warning if they differed. Then write `{"version": 2, "color"?}`, delete `.okf/vectors.db`, and call `reindex_bundle(storage)`. With `--dry-run`, nothing is written.

- [ ] **Step 1: Write failing tests**

```python
def test_migrates_links_descriptions_versions(tmp_path):
    s = LocalStorage(tmp_path / "w")
    s.write_text(".okf/workspace.json", json.dumps({"version": 1, "color": "red", "bundles": {"b": {"description": "Billing"}, "c": {"description": "C"}}}))
    s.write_text(".okf/vectors.db", "x")
    s.write_text("b/_index.md", "---\nokf_version: '0.1'\n---\n")
    s.write_text("c/_index.md", "---\ndescription: Mine\nokf_version: '0.2'\n---\n")
    s.write_text("b/a.md", "---\ntype: t\n---\n[x](/t/y.md#h) [e](https://e/z.md) [r](../c/q.md)")
    log = migrate_workspace(s)
    assert "[x](/b/t/y.md#h) [e](https://e/z.md) [r](../c/q.md)" in s.read_text("b/a.md")
    assert OKFDocument.parse(s.read_text("b/_index.md")).frontmatter["description"] == "Billing"
    assert OKFDocument.parse(s.read_text("c/_index.md")).frontmatter == {"description": "Mine"}
    assert OKFDocument.parse(s.read_text("_index.md")).frontmatter["okf_version"] == "0.2"
    assert json.loads(s.read_text(".okf/workspace.json")) == {"version": 2, "color": "red"}
    assert not s.exists(".okf/vectors.db")
    assert any("kept _index.md description for c" in l for l in log)

def test_second_run_is_noop(tmp_path): ...  # migrate twice; second returns ["already v2"]; file bytes identical
def test_dry_run_writes_nothing(tmp_path): ...  # snapshot all files before/after
```

- [ ] **Step 2:** Run `uv run pytest packages/okf-backend/tests/test_migrate.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the same command, then `uv run pytest`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(backend): okf-migrate-v2 for bundle-era workspaces`.

### Task 12: Config and docs

**Files:**
- Modify: root `.env.example` (remove the "Default target for okf-mcp" block), `CLAUDE.md`, `docs/TECHNICAL.md`, `README.md`, `packages/*/README.md`, `scripts/setup-claude-code.sh` (drop `--bundle`)
- Create: `packages/okf-backend/.env.example` (the `OKF_HOME` note + `OKF_EMBEDDING_*` block copied from the okf-mcp one)

- [ ] **Step 1:** Run `grep -rniE "OKF_BUNDLE|X-OKF-Bundle|--bundle|list_bundles|create_bundle|describe_bundle|bundles_info|create_index|bundle_storage" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=docs/superpowers .`. Expected: matches only in files about to be edited.
- [ ] **Step 2:** Edit. In the docs, use "workspace" and "node" for the product concepts, and keep "bundle" only for the OKF spec unit. Document a migration step: `uv run okf-migrate-v2 --dry-run`, then without `--dry-run`, then `okf-claude setup --workspace <ws>` again.
- [ ] **Step 3:** Rerun the Step 1 grep (expected: no output), then `uv run pytest` and `cd packages/okf-web && bun run test` (expected: PASS).
- [ ] **Step 4:** Commit `docs: workspace + node model; remove bundle settings`. Open PR 2.
