# okf storage interface — design

Date: 2026-10-19 · Roadmap item: "Storage abstraction" (docs/TODO.md #4)

## Intent

Today `okf-core` (`Bundle`, `regenerate_indexes`, `validate_bundle`) and the
`okf-mcp` write tools read and write files through `pathlib` directly, so a
bundle can only live on a local disk. Put the file system behind a small
`Storage` interface so the backing infrastructure (object store, remote git,
database) can be swapped without touching OKF logic. The local filesystem stays
the default and the only backend shipped for real; an in-memory backend ships
too, to prove the seam and to serve as a fast test double.

## Goals

- One `Storage` ABC in `okf_core.storage` covering read, write, list, move,
  delete, exists/is_dir, mkdir, and a write lock.
- `LocalStorage` (default) and `MemoryStorage`.
- Every existing caller goes through it: `Bundle.load`, `regenerate_indexes`,
  `validate_bundle`, and all `okf_mcp.operations` / `server` code.
- Selection by location string: a plain path or `file://` URI is local; any other
  scheme resolves through a backend registry. `OKF_BUNDLE_ROOT`, `OKF_STORE_ROOT`
  and the per-call `bundle_root` accept such a location.
- `okf-core` keeps PyYAML as its only runtime dependency.

## Non-goals

No real remote backend (S3/git/DB), no git management, no transactions across
files, no async API, no content-addressing or versioning.

## Interface

Keys are bundle-relative POSIX strings (`"tables/orders.md"`; `""` is the
bundle root). `normalize_key` rejects absolute keys, backslashes, empty, `.`
and `..` segments with `ValueError`, so a backend never sees a key that escapes
its root. Content is text (UTF-8, no newline translation).

| method | contract |
|---|---|
| `read_text(key)` | `FileNotFoundError` if absent |
| `write_text(key, text)` | creates parents; **atomic per key** (readers see old or new, never partial) |
| `delete(key)` | file only; `FileNotFoundError` if absent; leaves directories |
| `move(src, dst)` | `FileNotFoundError` / `FileExistsError`; default = write+delete, local = rename |
| `exists(key)`, `is_dir(key)` | `is_dir("")` is false when the bundle root itself is missing |
| `list_dir(key)` | sorted `Entry(name, is_dir)` of direct children; `FileNotFoundError` if not a directory |
| `mkdir(key)` | create directory (no-op on flat/object stores) |
| `iter_files(prefix="", suffix="")` | recursive, sorted depth-first by name; concrete default built on `list_dir` so a backend may override with a cheaper listing |
| `lock()` | context manager; exclusive and reentrant; held across a whole multi-file write operation |
| `child(prefix)` | a `Storage` scoped under a prefix (used by store mode for the per-project folder) |
| `location` | human-readable origin for error messages |

Only `read_text`, `write_text`, `delete`, `exists`, `is_dir`, `list_dir` are
abstract. The rest have working defaults, so a minimal backend is six methods.

**Atomicity and locking.** Single-file writes are atomic (`LocalStorage`: temp
file in the same directory + `os.replace`). A producer operation touches many
files (concept, `_log.md`, inbound links, every `_index.md`) and is *not*
transactional; instead each write tool holds `storage.lock()` for its whole
duration so concurrent producers serialise. `LocalStorage.lock()` combines a
process-wide per-root `RLock` with `fcntl.flock` on `<root>/.okf.lock` where
`fcntl` exists (POSIX); on Windows it degrades to the in-process lock. The lock
file is hidden and not `.md`, so bundles ignore it. Backends without a native
lock use the default per-instance `RLock`.

## Selecting a backend

`open_storage(location)` accepts a `Storage` (returned as is), a `Path`, or a
string. No scheme (or a one-letter Windows drive scheme) or `file://` → `LocalStorage`.
Otherwise the scheme is looked up in the registry: first
`register_backend(scheme, factory)`, then the `okf_core.storage` entry-point
group (`name` = scheme, `value` = `module:factory`, factory takes the full
location string). Unknown scheme → `ValueError` naming the scheme and the
registered ones. This is how optional backends plug in: a package such as
`okf-core[s3]` (a future extra) ships an entry point and imports its SDK only
inside the factory, so core's runtime dependency stays PyYAML.

In `okf-mcp` no new setting is introduced: `OKF_BUNDLE_ROOT`, `OKF_STORE_ROOT`,
and the `bundle_root` tool argument take a location. Store mode becomes
`open_storage(store).child(<project-basename>-<hash8>)`. Local locations keep
today's validation and still resolve to `Path`.

## Callers

- `okf_core` entry points take `Path | str | Storage`. `Bundle.load`,
  `validate_bundle` and `regenerate_indexes` normalise through `open_storage`.
  `Bundle` gains `.storage`; `.root` is kept (the input given).
- `regenerate_indexes` returns absolute `Path`s as before for `Path`/`str` input
  and bundle-relative key strings for `Storage` input *(documented call: keeps
  existing tests/consumers working while the storage form stays path-free)*.
- Link helpers get pure, path-free twins (`extract_link_ids`, `rewrite_link_ids`,
  `strip_link_ids`; `posixpath` on directory keys). The `Path`-based
  `extract_links`/`rewrite_links`/`strip_links` remain as thin wrappers.
- `okf_mcp.operations` functions take `Path | str | Storage` and work on keys;
  each write tool runs inside `storage.lock()`. Result shapes are unchanged.

## Relation to PR #1 (`workspace.LocalStorage`)

That branch adds a small injectable `LocalStorage(exists, is_dir, mkdir,
list_dirs)` in `okf_core/workspace.py`. These map 1:1 onto `exists`, `is_dir`,
`mkdir` and `list_dir` (filter `is_dir`) here, so once both land its seam can
be replaced by `okf_core.storage.LocalStorage` (rename-only; `list_dirs(path)` →
`[e.name for e in list_dir(key) if e.is_dir]`). This work does not depend on it.

## Calls I made (not asked)

- Text-only interface, no `read_bytes`; the validator catches
  `UnicodeDecodeError` from `read_text`.
- `move` is in the interface per the roadmap but `move_concept` still writes the
  rewritten document and deletes the source (the body changes on move).
- Lock file lives inside the bundle root (`.okf.lock`).
- No empty extras added to `okf-core`'s `pyproject.toml` until a real backend exists.
- `memory` backend is constructed directly (`MemoryStorage()`), no `memory://`
  scheme.
