# okf-core — Workspace Concept Design

**Date:** 2026-10-18
**Status:** Approved decisions (terminology, index = bundle) — implemented test-first
**Source:** `docs/TODO.md` item 2

## 1. Motivation

Bundles today live wherever the caller points (`OKF_BUNDLE_ROOT`, a per-call
`bundle_root`, or an `OKF_STORE_ROOT` per-project subfolder). There is no
well-known home for a user's knowledge. A **workspace** gives it one: a named
directory under `~/.okf/workspaces/` that holds one or more indexes.

## 2. Terminology (decided by the user)

- **Workspace** — a named, git-repo-shaped directory at
  `~/.okf/workspaces/<name>`. The unit git will manage later (TODO #1).
- **Index** — a collection of concepts inside a workspace. **One index is one
  bundle**: each visible top-level directory of a workspace is an index, and its
  directory name is the index name.
- The previous glossary term **Index** (`_index.md`) is renamed **Directory
  listing**. File names and code are unchanged (`INDEX_FILENAME`, `_index.md`).
- **Bundle** is unchanged: it is the on-disk form of an index.

## 3. Layout

```
~/.okf/                      # OKF home (override: OKF_HOME env or `home=` arg)
└── workspaces/
    └── <workspace>/         # a workspace
        ├── <index>/         # an index == a bundle (concepts, _index.md, _log.md)
        └── .git/            # (future) not created by this feature
```

Hidden (`.`-prefixed) and reserved (`_`-prefixed) top-level entries, and plain
files, are not indexes.

## 4. API (`okf_core.workspace`, stdlib only)

- `okf_home(home=None) -> Path` — explicit `home` arg > `OKF_HOME` env (the
  `.okf` directory itself) > `Path.home() / ".okf"`. Pure; creates nothing.
- `WorkspaceRegistry(root=None, storage=None)` — `root` defaults to
  `okf_home() / "workspaces"`.
  - `create(name) -> Workspace` — makes the directory (and the `.okf/workspaces`
    parents on first use); `FileExistsError` if present.
  - `list() -> list[Workspace]` — sorted by name; `[]` if the root is missing.
  - `get(name) -> Workspace` — `FileNotFoundError` if absent.
  - `exists(name) -> bool`.
- `Workspace(name, path)` (frozen dataclass)
  - `indexes() -> list[str]` — sorted index names.
  - `create_index(name) -> Path` — makes `<path>/<name>/`; `FileExistsError` if present.
  - `index_root(name) -> Path` — path of an existing index; `FileNotFoundError` otherwise.
  - `load_index(name) -> Bundle` — `Bundle.load(index_root(name))`.
- Names (workspace and index) match `[A-Za-z0-9][A-Za-z0-9._-]*`; anything else
  (separators, `..`, leading `.`/`_`, empty) raises `ValueError`.

## 5. Storage seam

All filesystem access in the registry goes through a small `LocalStorage` object
(`exists`, `is_dir`, `mkdir`, `list_dirs`). Registry and `Workspace` take it by
injection (default: local filesystem), so TODO #4 can swap the backend without
touching callers. `Bundle.load` itself still reads the filesystem directly;
abstracting that is TODO #4's job.

## 6. Relation to existing modes

- **Bundle root resolution (okf-mcp)** is unchanged. A workspace index is just a
  bundle directory: `OKF_BUNDLE_ROOT=<workspace>/<index>` or
  `bundle_root=` works today. A first-class `workspace`/`index` tool argument in
  okf-mcp is a follow-up, not in this change.
- **Store mode (`OKF_STORE_ROOT`)** is unchanged and independent: it partitions
  per code project; workspaces are named by the user. They can converge later.

## 7. Calls made by the author (not user decisions)

- `OKF_HOME` points at the `.okf` directory itself; also the test seam, so tests
  never touch the real home (tests use `home=tmp_path` / `monkeypatch.setenv`).
- **No `git init`** on `create`: the user deferred this ("will discuss later").
  A workspace is created as a plain directory; git management is TODO #1.
- Library only; no CLI. `create`/`create_index` do not pre-create `.okf` on
  import or on `okf_home()` — only when a workspace is created.
- Empty top-level directories count as indexes (a new index must exist before it
  has concepts).

## 8. Non-goals

Git operations, vector search, storage-interface abstraction beyond the seam
above, React UI, Claude Code hooks, okf-mcp tool changes, tag/explicit-list
index definitions.
