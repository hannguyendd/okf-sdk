# Workspace Targeting, Bundle Descriptions & Workspace Search — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address everything in okf-mcp and okf-web by workspace + bundle. Give bundles JSON-stored descriptions. Expose workspace/bundle tools over MCP. Search a whole workspace through one vector DB.

**Architecture:**
- okf-core's `Workspace` moves onto the shared `Storage` interface and owns `<workspace>/.okf/workspace.json`.
- okf-mcp gains a target resolver module, `okf_mcp/target.py`. It resolves workspace and bundle in this order: argument, then header, then env, then the pick remembered for the session, then elicitation. It replaces the `bundle_root`/store modes.
- The vector store keys rows by bundle name inside one `<workspace>/.okf/vectors.db`.
- okf-web takes a `(Workspace, bundle)` pair instead of a root, and adds a bundle-description endpoint and UI.

**Tech Stack:** Python 3.12, uv workspace, PyYAML (core), `mcp` 1.28 FastMCP (elicitation and streamable-HTTP), pydantic-settings, sqlite-vec, Starlette, React/Bun/Tailwind.

**Spec:** `docs/superpowers/specs/2026-10-26-okf-workspace-targeting-design.md`

## Global Constraints

- okf-core keeps PyYAML as its only runtime dependency. JSON comes from the stdlib `json` module.
- All bundle and workspace file I/O goes through `okf_core.Storage`. No `pathlib` I/O on bundle files.
- Tests never touch the real home. Use `home=`/`root=`, `OKF_HOME`, `tmp_path`, or `MemoryStorage`.
- Workspace metadata dir is `.okf`, file `workspace.json`, DB `vectors.db`.
- `workspace.json` shape is `{"version": 1, "bundles": {"<name>": {"description": str | null}}}`. Write it with `json.dumps(..., indent=2, sort_keys=True) + "\n"`.
- Description: stripped, max **1000** chars. `None` or blank clears it.
- Headers are `X-OKF-Workspace` / `X-OKF-Bundle`. Env vars are `OKF_WORKSPACE` / `OKF_BUNDLE`.
- Removed entirely: `OKF_BUNDLE_ROOT`, `OKF_STORE_ROOT`, `OKF_VECTOR_DB`, the `bundle_root` tool argument, `resolve_bundle_root`, `resolve_store_bundle_root`, `derive_project_folder`, `_slug`, the `--bundle-root`/`--project` web flags, and the `roots`-based project discovery in `server.py`.
- `search` `top_k` stays in 1..20.
- Workspaces cannot be created over MCP. Bundles can.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A hand-edited or corrupt `workspace.json`** (invalid JSON, `version: 2`, `bundles` not an object). The server must raise a clear `ValueError` and **never overwrite** the file. Pinned in Task 1.
2. **A bundle whose directory was created by hand**, with no JSON entry. It must be listed with `description: null`, and setting its description must work. An entry whose directory was deleted must not appear and is pruned on the next write. Pinned in Task 1.
3. **An elicitation answer that isn't one of the offered names**, from a client that ignores `enum`. It must be rejected with the choices-listing error, not used as a path. Pinned in Task 4.
4. **Searching after a bundle was deleted from disk.** Its rows (index and description) must not come back as hits. Pinned in Task 3.
5. **Two MCP sessions on one HTTP server.** One session's remembered pick must not leak into the other. Pinned in Task 4.

---

## File map

| File | Change |
|---|---|
| `packages/okf-core/src/okf_core/workspace.py` | Rewrite onto `Storage`; descriptions; metadata constants |
| `packages/okf-core/src/okf_core/__init__.py` | Export new constants |
| `packages/okf-core/tests/test_workspace.py` | Rewrite and extend |
| `packages/okf-mcp/src/okf_mcp/vector_store.py` | Bundle-keyed rows, description rows, multi-bundle query, `workspace_db_path` |
| `packages/okf-mcp/src/okf_mcp/operations.py` | Remove root-mode helpers; `search_workspace`, `create_bundle` |
| `packages/okf-mcp/src/okf_mcp/target.py` | **New.** Resolution, elicitation, per-session picks |
| `packages/okf-mcp/src/okf_mcp/server.py` | Settings, CLI/transport, tool rewiring, new tools, echo |
| `packages/okf-mcp/tests/test_vector_store.py`, `test_operations.py`, `test_server.py`, `test_target.py` (new) | As per tasks |
| `packages/okf-web/src/okf_web/server.py`, `app.py`; `tests/test_web_server.py`, `test_web_api.py` | Workspace+bundle, info, describe endpoint |
| `packages/okf-web/frontend/src/{api.ts,fakeApi.ts,App.tsx,SearchView.tsx,App.test.tsx}` | Description show/edit, hit shape |
| `CLAUDE.md`, package READMEs, store-mode and vector-search specs | Docs |

---

### Task 1: okf-core — Workspace on `Storage`, with bundle descriptions

**Files:**
- Modify: `packages/okf-core/src/okf_core/workspace.py` (whole file)
- Modify: `packages/okf-core/src/okf_core/__init__.py:34`
- Test: `packages/okf-core/tests/test_workspace.py`

**Interfaces:**
- Produces:
  - `METADATA_DIR = ".okf"`, `WORKSPACE_FILE = "workspace.json"`, `MAX_DESCRIPTION_CHARS = 1000`. Export these from `okf_core`.
  - `WorkspaceRegistry(root: Path | str | Storage | None = None)`. `root` defaults to `okf_home() / "workspaces"`. It is opened with `open_storage`, which yields `self.storage`. The old `storage=` kwarg and the private `LocalStorage` class are deleted. It keeps `exists/create/get/list` with the same names, errors, and sorting.
  - `@dataclass(frozen=True) Workspace(name: str, storage: Storage)`, built with `registry.storage.child(name)`.
    - `path -> Path | None` (property): `storage.root` when the storage has one, else `None`.
    - `indexes() -> list[str]`: same rule as before (visible top-level dirs, skipping names that start with `.` or `_`).
    - `create_index(name, description: str | None = None) -> Storage`: raises `FileExistsError` if the bundle exists.
    - `bundle_storage(name) -> Storage`: raises `FileNotFoundError` if absent.
    - `index_root(name) -> Path`: kept for local storage.
    - `load_index(name) -> Bundle`, via `Bundle.load(self.bundle_storage(name))`.
    - `description(name) -> str | None`
    - `set_description(name, text: str | None) -> str | None`: returns the stored value.
    - `bundles_info() -> list[dict]`: `[{"name", "description"}]`, sorted.
    - `meta_storage() -> Storage`: `storage.child(METADATA_DIR)`.

- [ ] **Step 1: Write failing tests.** Keep every existing behavior test, ported to the new constructor (`WorkspaceRegistry(root=tmp_path / "workspaces")`, `ws.path`). Add these:

```python
def test_description_roundtrip_writes_json(tmp_path):
    ws = WorkspaceRegistry(root=tmp_path).create("w")
    ws.create_index("notes", description="  Team notes  ")
    assert ws.description("notes") == "Team notes"
    data = json.loads((tmp_path / "w" / ".okf" / "workspace.json").read_text())
    assert data == {"version": 1, "bundles": {"notes": {"description": "Team notes"}}}
    assert (tmp_path / "w" / ".okf" / "workspace.json").read_text().endswith("\n")

def test_metadata_dir_is_not_an_index(tmp_path):
    ws = WorkspaceRegistry(root=tmp_path).create("w")
    ws.create_index("a", description="x")
    assert ws.indexes() == ["a"]

def test_set_description_blank_or_none_clears(tmp_path): ...  # both "  " and None -> description(name) is None
def test_set_description_too_long_raises(tmp_path): ...       # "x" * 1001 -> ValueError; "x" * 1000 ok
def test_set_description_unknown_bundle_raises(tmp_path): ... # FileNotFoundError
def test_hand_made_bundle_has_null_description_and_can_be_described(tmp_path):
    ...  # mkdir w/manual -> bundles_info() == [{"name": "manual", "description": None}]; set works
def test_stale_entry_hidden_and_pruned_on_write(tmp_path):
    ...  # write JSON with "gone" entry; bundles_info() omits it; after set_description("a", ...) JSON lacks "gone"
@pytest.mark.parametrize("text", ["{not json", '{"version": 2, "bundles": {}}', '{"version": 1, "bundles": []}'])
def test_corrupt_workspace_json_raises_and_is_not_overwritten(tmp_path, text):
    ...  # description() and set_description() raise ValueError; file bytes unchanged
def test_workspace_on_memory_storage():
    reg = WorkspaceRegistry(root=MemoryStorage()); ws = reg.create("w"); ws.create_index("b", "d")
    assert reg.list()[0].name == "w" and ws.bundles_info() == [{"name": "b", "description": "d"}] and ws.path is None
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest packages/okf-core/tests/test_workspace.py -v`. Expected: FAIL, because `create_index` takes no description and there's no `.okf` handling.

- [ ] **Step 3: Implement it in `workspace.py`.**
  - Read-modify-write `workspace.json` under `self.storage.lock()`.
  - A missing file means the empty document.
  - Validate `version == 1` and that `bundles` is a dict. Otherwise raise `ValueError(f"unsupported or corrupt {METADATA_DIR}/{WORKSPACE_FILE}: ...")` before writing anything.
  - On write, drop entries whose bundle isn't in `indexes()`.
  - `create_index` makes the directory, then sets the description if one is given.

- [ ] **Step 4: Run the tests and confirm they pass.** Run `uv run pytest packages/okf-core -q`. Expected: all pass, including `test_api.py`/`test_import.py` exports.

- [ ] **Step 5: Commit.** Use the message `feat(okf-core): workspaces on Storage with JSON bundle descriptions`.

---

### Task 2: Vector store — one DB per workspace, rows keyed by bundle

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/vector_store.py`
- Test: `packages/okf-mcp/tests/test_vector_store.py`

**Interfaces:**
- Consumes: `Workspace.meta_storage()` and `METADATA_DIR` (Task 1).
- Produces:
  - `workspace_db_path(workspace: Workspace) -> Path`: `<workspace.path>/.okf/vectors.db`. Raises `VectorStoreError` when `workspace.path is None`. This replaces `default_db_path`, which is deleted.
  - `VectorStore.sync(storage: Storage, embed, *, bundle: str, description: str | None, model: str, max_chars: int) -> None`
    - Rows use `root = bundle`.
    - The description is stored as the row with `key = ""`. Its hash is `sha256(description)` and its excerpt is the description. A `None` description deletes that row.
    - A model or dimension change still runs `DELETE FROM vectors` for **all** bundles, plus meta. Keep that existing behavior.
  - `VectorStore.prune_bundles(keep: set[str]) -> None`: deletes rows whose `root` is not in `keep`, in one transaction, and takes no write lock when there is nothing to delete.
  - `VectorStore.query(vector, top_k, *, bundles: list[str], dir: str = "") -> list[dict]`
    - Hits: `{"bundle", "kind", "dir", "path", "score", "excerpt"}`.
    - `kind` is `"bundle"` for `key == ""`, with `dir: ""` and `path: None`. Otherwise `kind` is `"index"`.
    - Ranked over all listed bundles together. A non-empty `dir` excludes description rows.

- [ ] **Step 1: Update the existing tests.** Port them to the new signatures (pass `bundle="b"`, `description=None`). Replace `test_rows_scoped_by_storage_location` and `test_default_db_path_is_sibling_and_stable` with:

```python
def test_rows_scoped_by_bundle_name(tmp_path): ...  # two storages synced as "a"/"b"; query(bundles=["a"]) only returns bundle "a"
def test_query_merges_bundles_and_ranks_together(tmp_path): ...  # best hit from "b", second from "a"; each hit["bundle"] correct
def test_description_row_is_embedded_and_returned(tmp_path):
    ...  # sync(description="orders and billing") -> a hit {"kind": "bundle", "path": None, "dir": "", "excerpt": "orders and billing"}
def test_description_change_reembeds_only_description(tmp_path): ...  # embed call count == 1 text
def test_cleared_description_removes_row(tmp_path): ...
def test_dir_filter_excludes_description_rows(tmp_path): ...
def test_model_change_wipes_all_bundles(tmp_path):
    ...  # sync a,b with model m1; sync a with m2 -> query(bundles=["b"]) == []; next sync of b re-embeds all its files
def test_prune_bundles_removes_gone_bundle_rows(tmp_path): ...  # incl. its description row
def test_workspace_db_path(tmp_path): ...  # == tmp_path/"w"/".okf"/"vectors.db"; MemoryStorage workspace -> VectorStoreError
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest packages/okf-mcp/tests/test_vector_store.py -v`. Expected: FAIL on the new signatures.

- [ ] **Step 3: Implement it.** Keep these existing properties: embed outside the transaction, one transaction per sync, `VectorStoreError` on sqlite errors. Change `query`'s `WHERE` to `root IN (...)`.

- [ ] **Step 4: Run the tests and confirm they pass.** Run `uv run pytest packages/okf-mcp/tests/test_vector_store.py -q`. Expected: PASS.

- [ ] **Step 5: Commit.** Use the message `feat(okf-mcp): workspace vector store keyed by bundle with description rows`.

---

### Task 3: operations — drop root modes; add `search_workspace` and `create_bundle`

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py:36-96` (delete), `:592-end` (replace `search_indexes`)
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: Task 1 `Workspace`; Task 2 `VectorStore`, `workspace_db_path`.
- Produces:
  - `search_workspace(workspace: Workspace, query: str, top_k: int = 5, bundles: list[str] | None = None, dir: str | None = None, *, config: EmbeddingConfig | None, max_chars: int = 6000, embed: Embedder | None = None, db_path: Path | None = None) -> list[dict]`. `db_path` is only a test seam and defaults to `workspace_db_path(workspace)`.
    - `bundles=None` means all of `workspace.indexes()`. An unknown name raises `FileNotFoundError`.
    - A non-empty `dir` with a scope other than exactly one bundle raises `ValueError("dir requires exactly one bundle")`.
    - Keep the existing blank-query, `top_k`, and not-configured validations.
    - Then it calls `prune_bundles(set(workspace.indexes()))`, then `sync` for each bundle in scope (with `description=workspace.description(b)`), then `query`.
    - `search_indexes` is deleted.
  - `create_bundle(workspace: Workspace, name: str, description: str | None = None) -> dict`
    - Calls `workspace.create_index(name, description)` and then `reindex_bundle(<that storage>)`.
    - Returns `{"bundle": name, "description": <stored>}`.
    - Writes no `_log.md` entry (my call: there's no concept change to log).

- [ ] **Step 1: Write failing tests and delete the removed ones.** Delete `test_resolve_requires_a_root`, the `test_derive_project_folder_*` tests, the `test_resolve_store_bundle_root_*` tests, the `test_resolve_bundle_root_*` tests, and the `search_indexes` tests. Port any `search_indexes` assertions that still apply. Add these (fake `embed`, real sqlite via `db_path=tmp_path/"v.db"`):

```python
def test_search_workspace_all_bundles_by_default(tmp_path): ...  # hits from both bundles, each tagged
def test_search_workspace_bundle_filter(tmp_path): ...           # bundles=["a"] -> every hit["bundle"] == "a"
def test_search_workspace_unknown_bundle_raises(tmp_path): ...   # FileNotFoundError
def test_search_workspace_dir_needs_single_bundle(tmp_path): ... # bundles=None, dir="x" -> ValueError; bundles=["a"], dir="x" ok
def test_search_workspace_finds_bundle_description(tmp_path): ...# kind == "bundle"
def test_search_workspace_ignores_deleted_bundle(tmp_path):
    ...  # search once, then shutil.rmtree the bundle dir, search again -> no hit has that bundle
def test_create_bundle_seeds_root_index_and_description(tmp_path):
    ...  # result == {"bundle": "n", "description": "d"}; bundle storage has "_index.md"; ws.description("n") == "d"
def test_create_bundle_existing_raises(tmp_path): ...            # FileExistsError
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest packages/okf-mcp/tests/test_operations.py -v`. Expected: FAIL with the import error for `search_workspace`.

- [ ] **Step 3: Implement it.** Also remove the now-unused imports (`hashlib` if it's unused, `re`, `is_uri`).

- [ ] **Step 4: Run the tests and confirm they pass.** Run `uv run pytest packages/okf-mcp/tests/test_operations.py -q`. Expected: PASS. `server.py` and okf-web fail to import until Tasks 4–6; that's expected.

- [ ] **Step 5: Commit.** Use the message `feat(okf-mcp): workspace search and bundle creation operations; drop root modes`.

---

### Task 4: Target resolver (`okf_mcp/target.py`)

**Files:**
- Create: `packages/okf-mcp/src/okf_mcp/target.py`
- Test: `packages/okf-mcp/tests/test_target.py`

**Interfaces:**
- Consumes: `WorkspaceRegistry`, `Workspace` (Task 1).
- Produces:
  - `WORKSPACE_HEADER = "x-okf-workspace"`, `BUNDLE_HEADER = "x-okf-bundle"` (lowercase is fine: Starlette headers are case-insensitive).
  - `class TargetError(ValueError)`
  - `@dataclass(frozen=True) class Target: workspace: Workspace; bundle: str | None`
  - `async def resolve_target(ctx, registry: WorkspaceRegistry, *, workspace: str | None, bundle: str | None, need_bundle: bool, env_workspace: str | None, env_bundle: str | None) -> Target`
  - `def header(ctx, name: str) -> str | None`: returns `ctx.request_context.request.headers.get(name)`, or `None` when there's no request (stdio) or the attribute is missing.

**Resolution rules** (spec §6):
- Workspace: arg → header → env → remembered pick → ask.
- Ask:
  - Zero workspaces: raise `TargetError("no workspaces exist; create one first ...")`.
  - Exactly one workspace: use it, and don't remember it.
  - Otherwise elicit.
- A named-but-missing workspace or bundle is a `TargetError` naming the choices. It never triggers a prompt.
- Bundle, only when `need_bundle`:
  - Order: arg → default (header, else env), applied only if `default_ws is None or resolved_ws.name == default_ws` → remembered bundle, applied only if `remembered_ws == resolved_ws.name` → ask.
  - `default_ws` is the header workspace if set, else the env workspace.
  - Ask:
    - Zero bundles: raise `TargetError` saying to call `create_bundle`.
    - One bundle: use it.
    - Otherwise elicit, with the message listing `name — description` for each bundle.
- When `need_bundle` is false (search, `list_bundles`), `bundle` is the arg-or-default as above, or `None`, and there's never a prompt.
- Elicitation:
  - Skip it when `ctx.session.check_client_capability(types.ClientCapabilities(elicitation=types.ElicitationCapability()))` is false.
  - Otherwise call `await ctx.elicit(message, schema)`. Build the schema with `pydantic.create_model("PickWorkspace" | "PickBundle", choice=(str, Field(description=..., json_schema_extra={"enum": names})))`.
  - `action != "accept"`, no capability, or an answer not in `names` all raise `TargetError(f"no {kind} chosen; pass {kind}= one of: {', '.join(names)}")`.
- Remembered picks:
  - Stored in a module-level `_picks: weakref.WeakKeyDictionary[object, dict[str, str]]`, keyed by `ctx.session`.
  - A workspace pick sets `{"workspace": w}` and drops any remembered bundle that belonged to another workspace.
  - A bundle pick sets `"workspace"` and `"bundle"` together.

- [ ] **Step 1: Write the failing tests.**
  - Fake `ctx`: a `SimpleNamespace(session=_Session(elicit_ok: bool), request_context=SimpleNamespace(request=<obj with .headers dict> | None), elicit=<async fn recording calls, returning SimpleNamespace(action=..., data=SimpleNamespace(choice=...))>)`.
  - `_Session` defines `check_client_capability` and must be weak-referenceable. A plain class is fine.
  - Registry: `WorkspaceRegistry(root=tmp_path)`.

```python
async def test_arg_beats_header_beats_env(...)
async def test_single_workspace_and_single_bundle_auto_picked_without_prompt(...)  # elicit never called; nothing remembered
async def test_elicits_workspace_then_bundle_and_remembers(...)  # 2nd call on same session: elicit not called again
async def test_picks_are_per_session(...)                         # other session object -> elicits again
async def test_default_bundle_ignored_for_other_workspace(...)    # env ws=A, env bundle=notes, arg ws=B (2 bundles) -> elicits bundle in B
async def test_default_bundle_applies_when_no_default_workspace(...)
async def test_named_missing_workspace_or_bundle_errors_without_prompt(...)
async def test_decline_or_cancel_raises_with_choices(...)         # message contains every name
async def test_no_elicitation_capability_raises_with_choices(...)
async def test_answer_not_in_choices_rejected(...)                # data.choice == "../etc" -> TargetError
async def test_no_workspaces_error_mentions_creation(...)
async def test_need_bundle_false_never_prompts_for_bundle(...)    # returns bundle None
async def test_header_reads_request_headers_and_none_on_stdio(...)
```

  Use `pytest.mark.anyio` or `asyncio.run`, whichever the repo's existing async tests use (`test_server.py` uses `asyncio.run`).

- [ ] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest packages/okf-mcp/tests/test_target.py -v`. Expected: FAIL with `ModuleNotFoundError: okf_mcp.target`.

- [ ] **Step 3: Implement `target.py`** following the rules above.

- [ ] **Step 4: Run the tests and confirm they pass.** Run `uv run pytest packages/okf-mcp/tests/test_target.py -q`. Expected: PASS.

- [ ] **Step 5: Commit.** Use the message `feat(okf-mcp): workspace/bundle target resolver with elicitation and session picks`.

---

### Task 5: MCP server — settings, transport, tools, echo

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/server.py` (whole tool surface)
- Test: `packages/okf-mcp/tests/test_server.py`

**Interfaces:**
- Consumes: Task 3 `search_workspace`, `create_bundle`; Task 4 `resolve_target`, `Target`, `TargetError`.
- Produces:
  - `Settings` fields: `workspace: str | None`, `bundle: str | None`, `embedding_url`, `embedding_model`, `embedding_api_key`, `embedding_max_chars`. `bundle_root`, `store_root`, and `vector_db` are removed.
  - `registry() -> WorkspaceRegistry`: a module function, built fresh per call (the default root comes from `OKF_HOME`) so tests can monkeypatch `OKF_HOME`.
  - `main(argv: list[str] | None = None) -> None`: argparse `--transport {stdio,streamable-http}` (default `stdio`), `--host` (default `127.0.0.1`), `--port` (default `8000`). It sets `mcp.settings.host`/`port` and then calls `mcp.run(transport=...)`.
  - Tools (each concept tool takes `workspace: str | None = None, bundle: str | None = None` last and `need_bundle=True`):

| Tool | Result |
|---|---|
| `add`, `patch`, `get`, `move`, `delete`, `reindex`, `describe` | `{**op_result, "workspace": ws, "bundle": b}` |
| `list`, `read_index` | `{"workspace", "bundle", "items": op_result}`. `read_index` returns a list today, so it is wrapped like `list`. This corrects spec §6, which listed it with the dict tools. |
| `list_workspaces()` | `[{"name", "bundles": int}]`. No target, never elicits. |
| `list_bundles(workspace=None)` | `{"workspace", "bundles": ws.bundles_info()}`. Wrapped so that the target is echoed. |
| `create_bundle(name, description=None, workspace=None)` | `{"workspace", **create_bundle(...)}` |
| `describe_bundle(description: str \| None, bundle=None, workspace=None)` | `{"workspace", "bundle", "description"}` |
| `search(query, top_k=5, bundles: list[str] \| None = None, dir=None, workspace=None)` | `{"workspace", "bundles": scope, "hits": [...]}`. Scope is `bundles`, else `[target.bundle]` if a default bundle resolved, else all bundles. `need_bundle=False`. |

  Tool docstrings must tell the agent:
  - `workspace`/`bundle` are optional and defaulted from headers or env.
  - The user is asked when the target is ambiguous.
  - Results echo the target, so the agent can pass it explicitly afterwards.
  - Search spans every bundle unless filtered.
  - Workspaces themselves cannot be created here.

  Run the blocking ops in `asyncio.to_thread` as `search` does today. The concept ops can stay synchronous, as they are now.

- [ ] **Step 1: Rewrite `test_server.py`.**
  - Delete the `_FakeSession` roots fake and the `test_root_*`, `test_settings_reads_store_root`, and `test_settings_reads_dotenv` tests.
  - Keep `test_tool_schema_excludes_ctx`.
  - Use `OKF_HOME=tmp_path` and Task 4's fake ctx. Add:

```python
def test_all_tools_registered(): ...  # previous set + {"list_workspaces","list_bundles","create_bundle","describe_bundle"}; "bundle_root" in no tool's inputSchema
def test_settings_read_workspace_and_bundle_env(monkeypatch): ...
def test_add_echoes_target_and_writes_into_bundle(tmp_path, monkeypatch): ...  # result["workspace"]=="w", result["bundle"]=="b"; file under OKF_HOME/workspaces/w/b
def test_list_and_read_index_wrap_items(...): ...
def test_list_workspaces_counts_bundles(...): ...
def test_list_bundles_includes_descriptions(...): ...
def test_create_bundle_and_describe_bundle(...): ...       # describe_bundle(None) clears
def test_search_scope_default_bundle_vs_all_vs_filter(..., monkeypatch): ...  # monkeypatch operations.search_workspace to capture bundles arg
def test_search_without_embedding_settings_errors_but_other_tools_work(...): ...  # ported
def test_main_parses_transport_and_port(monkeypatch): ...  # monkeypatch mcp.run to capture transport; mcp.settings.port == 9000
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest packages/okf-mcp/tests/test_server.py -v`. Expected: FAIL (import errors or missing tools).

- [ ] **Step 3: Implement `server.py`.**

- [ ] **Step 4: Run the tests and confirm they pass.** Run `uv run pytest packages/okf-mcp -q`. Expected: PASS.

- [ ] **Step 5: Commit.** Use the message `feat(okf-mcp): workspace/bundle targeting on all tools, bundle tools, HTTP transport`.

---

### Task 6: okf-web backend — workspace + bundle, info, describe endpoint

**Files:**
- Modify: `packages/okf-web/src/okf_web/server.py`, `packages/okf-web/src/okf_web/app.py`
- Test: `packages/okf-web/tests/test_web_server.py`, `packages/okf-web/tests/test_web_api.py`

**Interfaces:**
- Consumes: Tasks 1 and 3.
- Produces:
  - `create_app(workspace: Workspace, bundle: str, *, read_only=False, search_config=None, search_max_chars=6000, static_dir=None) -> Starlette`. The `vector_db` kwarg is removed, and `storage = workspace.bundle_storage(bundle)`.
  - `GET /api/info` returns `{"location", "read_only", "search_enabled", "workspace", "bundle", "description"}`.
  - `POST /api/bundle/describe` takes a body of `{"description": str | null}`, is registered with `write=True`, and returns `{"workspace", "bundle", "description"}`.
  - `GET /api/search` calls `operations.search_workspace(workspace, q, top_k, [bundle], dir, ...)`. Hits now carry `bundle` and `kind`, and `path` may be `null`.
  - `parse_args`: `--workspace`, `--bundle`, `--read-only`, `--host`, `--port`.
  - `build_app(args)` resolves from flag, then `Settings().workspace/bundle`, then the single candidate. If none of those resolve, it raises `sys.exit("okf-web: ... choose one of: a, b")`, and it does the same for a missing name.

- [ ] **Step 1: Write failing tests.**
  - `test_web_api.py`: the fixture builds `WorkspaceRegistry(root=MemoryStorage()).create("w")` and `create_index("b", "Billing data")`, then adds the concepts to `ws.bundle_storage("b")`. `client()` calls `create_app(ws, "b", **kw)`. Update `test_info` to expect the three new keys.
  - New API tests:

```python
def test_bundle_describe_sets_and_clears(ws): ...        # POST {"description": "New"} -> info description == "New"; {"description": None} -> None
def test_bundle_describe_forbidden_when_read_only(ws): ...  # 403, description unchanged
def test_bundle_describe_too_long_is_400(ws): ...
def test_search_hits_include_bundle_and_kind(ws, monkeypatch): ...  # monkeypatch ops.search_workspace; assert called with bundles == ["b"]
```

  - `test_web_server.py`: replace the four tests with ones that use `OKF_HOME=tmp_path`:

```python
def test_no_workspace_exits(...)
def test_single_workspace_and_bundle_auto_selected(...)
def test_flags_select_target_and_read_only(...)        # info workspace/bundle match flags
def test_env_selects_target(...)                        # OKF_WORKSPACE/OKF_BUNDLE
def test_ambiguous_bundle_exits_listing_choices(..., capsys)  # SystemExit message contains both names
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest packages/okf-web -v`. Expected: FAIL.

- [ ] **Step 3: Implement it.**

- [ ] **Step 4: Run the tests and confirm they pass.** Run `uv run pytest -q` for the whole workspace. Expected: PASS.

- [ ] **Step 5: Commit.** Use the message `feat(okf-web): serve a workspace bundle; bundle description endpoint`.

---

### Task 7: okf-web frontend — show and edit the bundle description, plus the new hit shape

**Files:**
- Modify: `packages/okf-web/frontend/src/api.ts`, `fakeApi.ts`, `App.tsx`, `SearchView.tsx`
- Test: `packages/okf-web/frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: Task 6 endpoints.
- Produces:
  - `api.ts`:
    - `Info` gains `workspace: string; bundle: string; description: string | null`.
    - `Hit` becomes `{ bundle: string; kind: "index" | "bundle"; dir: string; path: string | null; score: number; excerpt: string }`.
    - `api.describeBundle(description: string | null)` calls `POST /api/bundle/describe`.
  - `fakeApi.ts`:
    - `info` returns `workspace: "w", bundle: "b"`, plus a mutable `description` that starts as `"Billing data"`.
    - It handles `/api/bundle/describe`, updating that description.
    - Its search hits include one `kind: "bundle"` hit.

- [ ] **Step 1: Write failing tests in `App.test.tsx`.** Follow the file's existing render, find, and calls patterns.

```tsx
test("header shows workspace / bundle and its description")       // text "w / b" and "Billing data"
test("edit bundle description saves via /api/bundle/describe")    // stub window.prompt -> "New"; calls has POST /api/bundle/describe {description: "New"}; UI shows "New"
test("empty prompt clears the bundle description")                // prompt -> "" -> body {description: null}
test("bundle description edit hidden when read-only")
test("search renders a bundle-description hit linking to the root") // text "bundle" label + excerpt; link href === href.dir("")
```

- [ ] **Step 2: Run the tests and confirm they fail.** In `packages/okf-web/frontend`, run `bun test`. Expected: FAIL.

- [ ] **Step 3: Implement it.**
  - In the `App.tsx` header, show `{info.workspace} / {info.bundle}` and the description (muted, or "No description").
  - Add an "Edit bundle description" button. It's shown only when the server isn't read-only and works like `DirView.describe`: `window.prompt` (where `null` aborts and `""` is sent as `null`), then `api.describeBundle`, then refetch info.
  - In `SearchView`, render a `kind === "bundle"` hit as a "bundle" tag plus the excerpt, linked to `href.dir("")`.

- [ ] **Step 4: Run the tests and confirm they pass.** In `packages/okf-web/frontend`, run `bun test && bun run build`. Expected: tests PASS and the build succeeds.

- [ ] **Step 5: Commit.** Use the message `feat(okf-web): show and edit bundle description in the UI`.

---

### Task 8: Docs

**Files:**
- Modify: `CLAUDE.md`, `packages/okf-mcp/README.md`, `packages/okf-web/README.md`, `packages/okf-core/README.md` (whichever exist).
- Modify: `docs/superpowers/specs/2026-07-20-okf-mcp-store-mode-design.md`, `docs/superpowers/specs/2026-10-19-okf-mcp-vector-search-design.md`. Add a "Superseded by `2026-10-26-okf-workspace-targeting-design.md`" status line to each.

- [ ] **Step 1: Update the docs.**
  - `CLAUDE.md`'s okf-mcp and okf-web paragraphs should describe workspace + bundle targeting (arg > header > env > remembered > ask), the new tools, `.okf/workspace.json` and `.okf/vectors.db`, the `--transport streamable-http` flag, and okf-web's `--workspace/--bundle`.
  - Remove every mention of `OKF_BUNDLE_ROOT`, `OKF_STORE_ROOT`, and `OKF_VECTOR_DB`.
  - The READMEs should show an example MCP config for stdio (env) and for HTTP (headers).

- [ ] **Step 2: Verify.** Run `grep -rn "OKF_BUNDLE_ROOT\|OKF_STORE_ROOT\|OKF_VECTOR_DB\|bundle_root\|--bundle-root" CLAUDE.md packages --include=*.md --include=*.py --include=*.ts --include=*.tsx`. Expected: no matches, apart from historical specs under `docs/`. Then run `uv run pytest -q`. Expected: PASS.

- [ ] **Step 3: Commit.** Use the message `docs: workspace targeting replaces bundle/store root modes`.
