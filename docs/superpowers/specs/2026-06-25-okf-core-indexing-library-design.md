# okf-core — OKF read & index library

**Date:** 2026-06-25
**Status:** Approved design
**Source ported from:** `~/Programming/research/knowledge-catalog/okf` (Open Knowledge Format reference implementation, the `reference_agent` package)

## Purpose & scope

`okf-core` is a dependency-light core library for **consuming** Open Knowledge
Format (OKF) bundles. It does three things:

1. Parse and serialize individual OKF documents (YAML frontmatter + markdown body).
2. Load a bundle directory into an in-memory **concept graph** — concepts plus
   their cross-links and reverse "cited-by" backlinks.
3. Regenerate the bundle's `index.md` progressive-disclosure listings.

It is the first sub-project in the `okf-sdk` multi-project workspace.

### In scope (ported from the source)

- `bundle/document.py` → `okf_core/document.py` (the `OKFDocument` model)
- `bundle/paths.py` → `okf_core/paths.py` (concept-id ↔ path helpers)
- `bundle/index.py` → `okf_core/index.py` (`regenerate_indexes`)
- `bundle/synthesizer.py` → `okf_core/synthesizer.py` (deterministic fallback only)
- `viewer/generator.py`'s bundle-walking/graph logic (`_walk_concepts`,
  `_extract_links`, `_build_graph`, the `Concept` model) → promoted into a clean
  `okf_core/bundle.py` API, **with the HTML/Cytoscape rendering removed**.

### Out of scope (producer-side and presentation — dropped)

- `sources/` (BigQuery and the `Source` base) — data ingestion.
- `web/fetcher.py` — web crawling.
- `agent.py`, `runner.py`, `cli.py`, `__main__.py` — the Google ADK agent.
- `tools/` (`web_tools`, `source_tools`, `bundle_tools`, `context`) — agent tools.
- `prompts/` — agent prompts.
- `viewer/templates/`, `viewer/static/` — the HTML/CSS/JS viewer rendering.

### Decisions confirmed during brainstorming

- **Scope:** full read+index core (data model + path helpers + `Bundle` graph
  loader + `index.md` regeneration).
- **Layout:** uv workspace with a virtual root; the lib lives at
  `packages/okf-core`.
- **Drop the Gemini dependency.** `regenerate_indexes` keeps its injectable
  `synthesize` callable seam, defaulting to the deterministic fallback. The core's
  only runtime dependency stays `pyyaml`. Callers wanting LLM-generated directory
  summaries pass their own callable.
- **Add absolute-link resolution.** A deliberate fidelity enhancement over the
  source viewer (see Bundle module below).
- **Vendor `SPEC.md`** (OKF v0.1) into the package as the reference for the format
  the library implements.

## Workspace layout (uv workspace, virtual root)

```
okf-sdk/
├── pyproject.toml            # virtual root: [tool.uv.workspace] members=["packages/*"]; dev group: pytest
├── .python-version           # 3.12 (kept)
├── README.md                 # updated: describes the workspace + okf-core
├── CLAUDE.md                 # updated to reflect the new structure
└── packages/
    └── okf-core/
        ├── pyproject.toml    # [project] name="okf-core", deps=["pyyaml>=6"], hatchling build, src layout
        ├── README.md
        ├── SPEC.md           # vendored OKF v0.1 spec
        ├── src/okf_core/
        │   ├── __init__.py   # public API re-exports + __version__
        │   ├── document.py
        │   ├── paths.py
        │   ├── bundle.py
        │   ├── index.py
        │   └── synthesizer.py
        └── tests/
            ├── test_document.py
            ├── test_paths.py
            ├── test_bundle.py
            └── test_index.py
```

- The root `main.py` (the `uv init` Hello World scaffold) is deleted.
- The root `pyproject.toml` is converted to a **virtual workspace root**: it
  carries `[tool.uv.workspace]` and a `dev` dependency group (pytest) but **no
  `[project]` table** of its own.
- `uv sync` builds one shared `.venv` at the root; members install editable, so
  `import okf_core` resolves in tests with no `pythonpath` manipulation.
- `okf-core` uses a `src/` layout and the `hatchling` build backend (uv's
  default). It ships only Python — no package-data, since the templates/static
  assets are dropped.

## Modules & API

### `document.py` (ported ~verbatim)

- `OKFDocumentError(ValueError)`
- `REQUIRED_FRONTMATTER_KEYS = ("type", "title", "description", "timestamp")`
- `OKFDocument` dataclass — `frontmatter: dict[str, Any]`, `body: str`:
  - `parse(text) -> OKFDocument` — splits the `---`-delimited YAML frontmatter
    from the body; text with no leading `---` becomes all-body; an unterminated
    block raises `OKFDocumentError`; non-mapping frontmatter raises.
  - `serialize() -> str` — round-trips frontmatter (`sort_keys=False`,
    `allow_unicode=True`) + body.
  - `validate()` — raises `OKFDocumentError` if any required key is missing/empty.

### `paths.py` (ported verbatim)

- `concept_id_to_path(bundle_root, concept_id: tuple[str, ...]) -> Path`
- `path_to_concept_id(bundle_root, path) -> tuple[str, ...]`
- `parse_concept_id(s: str) -> tuple[str, ...]`
- Segment validation via the existing `_SEGMENT_RE` (rejects empty / invalid
  segments).

### `bundle.py` (new — absorbs the viewer's graph logic, no HTML)

- `Concept` dataclass:
  - `id: str` — slash-joined concept id (e.g. `tables/users`).
  - `document: OKFDocument` — the **full** parsed document; arbitrary frontmatter
    keys are preserved per SPEC §4.1.
  - `links_to: list[str]` — concept ids referenced from the body (resolved,
    order-preserving, deduped; may include not-yet-existing targets).
  - Convenience read-only properties derived from frontmatter: `type` (default
    `"Unknown"`), `title` (default = `id`), `description`, `resource`, `tags`
    (always a `list[str]`), and `body` (= `document.body`).
- `Bundle` class:
  - `Bundle.load(root) -> Bundle` — `rglob("*.md")`, skipping `index.md` files;
    parse each doc (unparseable docs are silently skipped); build `Concept`s and
    an id index. Raises `FileNotFoundError` if `root` is not a directory.
  - `get(concept_id) -> Concept | None`, `__iter__`, `__len__`, `__contains__`.
  - `edges() -> list[tuple[str, str]]` — directed `(source_id, target_id)` pairs,
    filtered to targets that exist in the bundle, deduped, excluding self-loops.
  - `backlinks(concept_id) -> list[str]` — reverse of the link graph (the viewer's
    "Cited by").
  - `types() -> list[str]` — sorted unique concept types.
- **Link extraction** (`extract_links(body, doc_dir, bundle_root)`): finds
  markdown link targets ending in `.md` (tolerating a trailing `#anchor`),
  resolving:
  - **relative** links against the document's directory (as the source viewer
    did), and
  - **absolute bundle-root** links (`/path/to/x.md`) against `bundle_root` — the
    SPEC §5.1 *recommended* form, which the source viewer skipped. **This is the
    one intentional behavioral enhancement over the source.**

    External links (`scheme://…`) are skipped. Targets are normalized to concept
    ids (`.md` stripped), deduped preserving first-seen order.

### `index.py` (ported, LLM seam preserved)

- `regenerate_indexes(bundle_root, *, synthesize=fallback_synthesizer) -> list[Path]`
  - The `model` parameter is **removed** (no longer meaningful); the `synthesize`
    callable signature becomes `(rel_path: str, children: list[tuple[str, str]]) -> str`.
  - Behavior preserved exactly: discover directories that transitively contain
    `.md` files (never above `bundle_root`); process **deepest-first** so child
    summaries are available to parents; group entries by frontmatter `type`
    (missing → `"Other"`), subdirectories under `"Subdirectories"`; types sorted
    alphabetically, titles case-insensitively; link text = `title` or filename
    stem; skip the index file itself, non-`.md` files, unparseable docs, and empty
    directories; the root index gets no synthesized description; single-child
    directories with a non-empty child description reuse it verbatim (no synth
    call).
  - Returns the list of written `index.md` paths; returns `[]` for a nonexistent
    root.

### `synthesizer.py` (deterministic fallback only)

- `fallback_synthesizer(rel_path, children) -> str` — returns
  `Contains N entries: <comma-joined titles>.` (or `no titled entries` when none
  have titles); `""` for no children. The Gemini/`google.genai` code is dropped.
  The docstring documents the callable protocol so users can supply an
  LLM-backed synthesizer.

### `__init__.py`

Re-exports the public surface and a `__version__`:
`OKFDocument`, `OKFDocumentError`, `REQUIRED_FRONTMATTER_KEYS`, `Concept`,
`Bundle`, `concept_id_to_path`, `path_to_concept_id`, `parse_concept_id`,
`regenerate_indexes`, `fallback_synthesizer`.

## Error handling (faithful to the source)

- `OKFDocument.parse` raises `OKFDocumentError` on malformed/unterminated/
  non-mapping frontmatter.
- `Bundle.load` and `regenerate_indexes` **silently skip** unparseable documents,
  so a single bad file never aborts a run.
- `Bundle.load` raises `FileNotFoundError` when `root` is not a directory.
- `regenerate_indexes` returns `[]` when `bundle_root` does not exist.

## Testing

All tests live in `packages/okf-core/tests/` and run via `uv run pytest` from the
workspace root. Built test-first: tests are ported/written before the
implementation is made to pass.

- `test_document.py` — ported verbatim from the source (import path only):
  round-trip, no-frontmatter-is-body, unterminated-raises, validate-rejects-
  missing-keys, validate-accepts-full.
- `test_paths.py` — *new* small suite: `concept_id_to_path` / `path_to_concept_id`
  round-trip, `parse_concept_id` happy path, invalid-segment and empty-id rejection.
- `test_bundle.py` — rewritten from the source `test_viewer.py`, testing the
  `Bundle` API directly instead of generated HTML:
  - concept count and ids (excluding `index.md`),
  - `edges()` contains the expected directed cross-link pairs,
  - `backlinks()` is the correct reverse graph,
  - `types()` returns sorted unique types,
  - missing/dangling link targets are excluded from `edges()` but the source
    concept still loads,
  - `Bundle.load` raises `FileNotFoundError` on a missing root,
  - **new:** absolute bundle-root links (`/tables/users.md`) resolve to edges.
  - HTML/palette/`to_node` assertions are dropped.
- `test_index.py` — ported from the source, adapted to the removed `model`
  parameter (stub synth signature `(rel, children)`): group-by-type + relative
  links, skip-empty-directories, single-child-reuses-description (asserts the
  synth callable is **not** called).

## Implementation notes

- Keep modules small and single-purpose; match the source's existing style
  (`from __future__ import annotations`, dataclasses, type hints).
- No new runtime dependency beyond `pyyaml`. `pytest` is the only dev dependency.
- Update the root `README.md` and `CLAUDE.md` to describe the workspace structure
  and the `okf-core` package (the source `CLAUDE.md` invites updating it as
  conventions are established).
