# okf-core Indexing Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the indexing core of the OKF reference implementation into a standalone `okf-core` library — parse OKF documents, load a bundle into an in-memory concept graph, and regenerate `index.md` listings — as the first member of the `okf-sdk` uv workspace.

**Architecture:** A `src`-layout Python package `okf_core` living at `packages/okf-core/` inside a uv **virtual** workspace root. Five focused modules: `document` (the `OKFDocument` model), `paths` (concept-id ↔ path helpers), `bundle` (the `Bundle`/`Concept` graph loader, absorbing the source viewer's walk/link logic without HTML), `synthesizer` (a deterministic directory-summary fallback), and `index` (`regenerate_indexes`). The public surface is re-exported from `okf_core/__init__.py`.

**Tech Stack:** Python 3.12, uv (workspace + lockfile), hatchling (build backend), PyYAML (only runtime dep), pytest (only dev dep).

## Global Constraints

- **Python:** `requires-python = ">=3.12"`.
- **Runtime dependencies:** `pyyaml>=6.0` ONLY. No `google-genai`, no networking, no other runtime deps.
- **Dev dependencies:** `pytest>=8` only.
- **Package layout:** `src` layout — importable module is `okf_core`, distribution name is `okf-core`.
- **Workspace root is virtual:** the root `pyproject.toml` has `[tool.uv.workspace]` and `[dependency-groups]` but **no `[project]` table**.
- **Source of truth for ported code:** `~/Programming/research/knowledge-catalog/okf/src/reference_agent/`. Port behavior faithfully except the two approved changes: (1) drop the Gemini synthesizer, defaulting to a deterministic fallback via an injectable callable; (2) resolve **both** relative and absolute (`/…`) bundle-root links.
- **Style:** every module starts with `from __future__ import annotations`; use dataclasses and type hints to match the source style.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Tests** live in `packages/okf-core/tests/` and run from the repo root via `uv run pytest`.

---

### Task 1: uv workspace + okf-core package scaffold

**Files:**
- Modify: `pyproject.toml` (repo root — replace the `uv init` scaffold with a virtual workspace root)
- Delete: `main.py` (the Hello World scaffold)
- Create: `packages/okf-core/pyproject.toml`
- Create: `packages/okf-core/src/okf_core/__init__.py`
- Create: `packages/okf-core/SPEC.md` (vendored)
- Create: `packages/okf-core/README.md`
- Test: `packages/okf-core/tests/test_import.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: an installed, editable `okf_core` package exposing `okf_core.__version__ == "0.1.0"`; a working `uv run pytest` from the repo root; the `packages/okf-core/src/okf_core/` and `packages/okf-core/tests/` directories that later tasks fill in.

- [ ] **Step 1: Replace the root `pyproject.toml` with a virtual workspace root**

Overwrite `pyproject.toml` (repo root) with exactly:

```toml
[tool.uv.workspace]
members = ["packages/*"]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["packages"]
```

- [ ] **Step 2: Remove the scaffold entry point**

Run:

```bash
git rm main.py
```

- [ ] **Step 3: Create the package `pyproject.toml`**

Create `packages/okf-core/pyproject.toml`:

```toml
[project]
name = "okf-core"
version = "0.1.0"
description = "Core library for reading and indexing Open Knowledge Format (OKF) bundles"
readme = "README.md"
requires-python = ">=3.12"
dependencies = ["pyyaml>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/okf_core"]
```

- [ ] **Step 4: Create a minimal package `__init__.py`**

Create `packages/okf-core/src/okf_core/__init__.py`:

```python
"""okf_core — read and index Open Knowledge Format (OKF) bundles."""
from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
```

- [ ] **Step 5: Vendor the OKF spec and write the package README**

Run:

```bash
cp ~/Programming/research/knowledge-catalog/okf/SPEC.md packages/okf-core/SPEC.md
```

Create `packages/okf-core/README.md`:

```markdown
# okf-core

Core library for **consuming** [Open Knowledge Format](SPEC.md) (OKF) bundles —
directories of markdown files with YAML frontmatter.

It can:

- parse and serialize individual OKF documents (`OKFDocument`),
- convert between concept ids and file paths,
- load a bundle directory into an in-memory concept graph with cross-links and
  reverse backlinks (`Bundle`),
- regenerate the bundle's `index.md` progressive-disclosure listings
  (`regenerate_indexes`).

It does **not** produce bundles (no data-source ingestion, web crawling, agent,
or LLM calls) and ships no UI. Its only runtime dependency is PyYAML.

## Usage

```python
from okf_core import Bundle, OKFDocument, regenerate_indexes

bundle = Bundle.load("path/to/bundle")
for concept in bundle:
    print(concept.id, concept.type, concept.title)

print(bundle.edges())               # [(source_id, target_id), ...]
print(bundle.backlinks("tables/users"))

regenerate_indexes("path/to/bundle")  # writes index.md files
```

See [SPEC.md](SPEC.md) for the format this library implements.
```

- [ ] **Step 6: Sync the workspace**

Run: `uv sync`
Expected: succeeds and creates a shared `.venv` at the repo root with `okf-core` installed editable and `pytest` available. A `uv.lock` is written.

- [ ] **Step 7: Write the smoke test**

Create `packages/okf-core/tests/test_import.py`:

```python
from __future__ import annotations


def test_okf_core_imports_with_version():
    import okf_core

    assert okf_core.__version__ == "0.1.0"
```

- [ ] **Step 8: Run the smoke test to verify it passes**

Run: `uv run pytest packages/okf-core/tests/test_import.py -v`
Expected: PASS (1 passed). This confirms the editable install and workspace wiring.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: scaffold okf-core package in uv workspace

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `document.py` — the OKFDocument model

**Files:**
- Create: `packages/okf-core/src/okf_core/document.py`
- Test: `packages/okf-core/tests/test_document.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `OKFDocumentError(ValueError)`
  - `REQUIRED_FRONTMATTER_KEYS = ("type", "title", "description", "timestamp")`
  - `OKFDocument` dataclass with fields `frontmatter: dict[str, Any]`, `body: str`; classmethod `parse(text: str) -> OKFDocument`; methods `serialize() -> str`, `validate() -> None`.

- [ ] **Step 1: Write the failing tests**

Create `packages/okf-core/tests/test_document.py`:

```python
from __future__ import annotations

import pytest

from okf_core.document import OKFDocument, OKFDocumentError


def test_roundtrip_preserves_frontmatter_and_body():
    src = (
        "---\n"
        "type: BigQuery Table\n"
        "title: Sample\n"
        "description: A sample table.\n"
        "tags: [a, b]\n"
        "timestamp: 2026-05-27T00:00:00+00:00\n"
        "---\n"
        "\n"
        "# Sample\n"
        "\n"
        "Body text.\n"
    )
    doc = OKFDocument.parse(src)
    assert doc.frontmatter["type"] == "BigQuery Table"
    assert doc.frontmatter["tags"] == ["a", "b"]
    assert doc.body.startswith("# Sample")

    serialized = doc.serialize()
    reparsed = OKFDocument.parse(serialized)
    assert reparsed.frontmatter == doc.frontmatter
    assert reparsed.body.strip() == doc.body.strip()


def test_parse_no_frontmatter_treats_all_as_body():
    src = "# Hello\n\nNo frontmatter here.\n"
    doc = OKFDocument.parse(src)
    assert doc.frontmatter == {}
    assert "Hello" in doc.body


def test_unterminated_frontmatter_raises():
    src = "---\ntype: X\nstill in frontmatter\n"
    with pytest.raises(OKFDocumentError):
        OKFDocument.parse(src)


def test_validate_rejects_missing_required_keys():
    doc = OKFDocument(frontmatter={"type": "X", "title": "Y"})
    with pytest.raises(OKFDocumentError) as exc:
        doc.validate()
    assert "description" in str(exc.value)
    assert "timestamp" in str(exc.value)


def test_validate_accepts_full_frontmatter():
    doc = OKFDocument(
        frontmatter={
            "type": "X",
            "title": "Y",
            "description": "Z",
            "timestamp": "2026-05-27T00:00:00+00:00",
        }
    )
    doc.validate()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/okf-core/tests/test_document.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'okf_core.document'`.

- [ ] **Step 3: Write the implementation**

Create `packages/okf-core/src/okf_core/document.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

REQUIRED_FRONTMATTER_KEYS = ("type", "title", "description", "timestamp")

_FRONTMATTER_DELIM = "---"


class OKFDocumentError(ValueError):
    pass


@dataclass
class OKFDocument:
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @classmethod
    def parse(cls, text: str) -> "OKFDocument":
        lines = text.splitlines()
        if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
            return cls(frontmatter={}, body=text)

        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == _FRONTMATTER_DELIM:
                end_idx = i
                break
        if end_idx is None:
            raise OKFDocumentError("Unterminated YAML frontmatter block")

        fm_text = "\n".join(lines[1:end_idx])
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError as e:
            raise OKFDocumentError(f"Invalid YAML in frontmatter: {e}") from e
        if not isinstance(fm, dict):
            raise OKFDocumentError("Frontmatter must be a YAML mapping")

        body = "\n".join(lines[end_idx + 1:])
        if body.startswith("\n"):
            body = body[1:]
        return cls(frontmatter=fm, body=body)

    def serialize(self) -> str:
        fm_text = yaml.safe_dump(
            self.frontmatter, sort_keys=False, allow_unicode=True
        ).rstrip()
        body = self.body if self.body.endswith("\n") else self.body + "\n"
        return f"{_FRONTMATTER_DELIM}\n{fm_text}\n{_FRONTMATTER_DELIM}\n\n{body}"

    def validate(self) -> None:
        missing = [k for k in REQUIRED_FRONTMATTER_KEYS if not self.frontmatter.get(k)]
        if missing:
            raise OKFDocumentError(
                f"Missing required frontmatter keys: {', '.join(missing)}"
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/okf-core/tests/test_document.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-core/src/okf_core/document.py packages/okf-core/tests/test_document.py
git commit -m "feat: add OKFDocument model

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `paths.py` — concept-id ↔ path helpers

**Files:**
- Create: `packages/okf-core/src/okf_core/paths.py`
- Test: `packages/okf-core/tests/test_paths.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `concept_id_to_path(bundle_root: Path, concept_id: tuple[str, ...]) -> Path`
  - `path_to_concept_id(bundle_root: Path, path: Path) -> tuple[str, ...]`
  - `parse_concept_id(s: str) -> tuple[str, ...]`

- [ ] **Step 1: Write the failing tests**

Create `packages/okf-core/tests/test_paths.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from okf_core.paths import concept_id_to_path, parse_concept_id, path_to_concept_id


def test_concept_id_to_path_and_back(tmp_path: Path):
    root = tmp_path / "bundle"
    cid = ("tables", "users")
    path = concept_id_to_path(root, cid)
    assert path == root / "tables" / "users.md"
    assert path_to_concept_id(root, path) == cid


def test_concept_id_to_path_rejects_empty():
    with pytest.raises(ValueError):
        concept_id_to_path(Path("/x"), ())


def test_parse_concept_id_strips_separators():
    assert parse_concept_id("/tables/users/") == ("tables", "users")


def test_parse_concept_id_rejects_empty():
    with pytest.raises(ValueError):
        parse_concept_id("/")


def test_parse_concept_id_rejects_invalid_segment():
    with pytest.raises(ValueError):
        parse_concept_id("tables/bad segment")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/okf-core/tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'okf_core.paths'`.

- [ ] **Step 3: Write the implementation**

Create `packages/okf-core/src/okf_core/paths.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

_SEGMENT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*")


def _validate_segment(seg: str) -> None:
    if not _SEGMENT_RE.fullmatch(seg):
        raise ValueError(f"Invalid concept id segment: {seg!r}")


def concept_id_to_path(bundle_root: Path, concept_id: tuple[str, ...]) -> Path:
    if not concept_id:
        raise ValueError("concept_id must have at least one segment")
    for seg in concept_id:
        _validate_segment(seg)
    *dirs, name = concept_id
    return bundle_root.joinpath(*dirs, f"{name}.md")


def path_to_concept_id(bundle_root: Path, path: Path) -> tuple[str, ...]:
    rel = path.relative_to(bundle_root).with_suffix("")
    return tuple(rel.parts)


def parse_concept_id(s: str) -> tuple[str, ...]:
    parts = tuple(p for p in s.split("/") if p)
    if not parts:
        raise ValueError(f"Empty concept id: {s!r}")
    for p in parts:
        _validate_segment(p)
    return parts
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/okf-core/tests/test_paths.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-core/src/okf_core/paths.py packages/okf-core/tests/test_paths.py
git commit -m "feat: add concept-id path helpers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `bundle.py` — the Bundle/Concept graph loader

**Files:**
- Create: `packages/okf-core/src/okf_core/bundle.py`
- Test: `packages/okf-core/tests/test_bundle.py`

**Interfaces:**
- Consumes: `okf_core.document.OKFDocument`, `okf_core.document.OKFDocumentError` (from Task 2).
- Produces:
  - `extract_links(body: str, doc_dir: Path, bundle_root: Path) -> list[str]`
  - `Concept` dataclass: `id: str`, `document: OKFDocument`, `links_to: list[str]`; read-only properties `type`, `title`, `description`, `resource`, `tags: list[str]`, `body`.
  - `Bundle` dataclass: classmethod `load(root: Path | str) -> Bundle`; `concepts: list[Concept]`; `root: Path`; `get(concept_id) -> Concept | None`; `edges() -> list[tuple[str, str]]`; `backlinks(concept_id) -> list[str]`; `types() -> list[str]`; supports `len()`, iteration, and `in`.

- [ ] **Step 1: Write the failing tests**

Create `packages/okf-core/tests/test_bundle.py`:

```python
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from okf_core.bundle import Bundle


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip(), encoding="utf-8")


def _make_bundle(root: Path) -> None:
    _write(
        root / "datasets" / "my_dataset.md",
        """
        ---
        type: BigQuery Dataset
        title: My dataset
        description: A test dataset.
        resource: https://example.com/dataset
        tags: [test]
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Parent dataset for [users](../tables/users.md).
        """,
    )
    _write(
        root / "tables" / "users.md",
        """
        ---
        type: BigQuery Table
        title: Users
        description: User profiles.
        resource: https://example.com/users
        tags: [users]
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Joinable with [events](events.md) and see [DAU](../references/metrics/dau.md).
        """,
    )
    _write(
        root / "tables" / "events.md",
        """
        ---
        type: BigQuery Table
        title: Events
        description: User events.
        resource: https://example.com/events
        tags: [events]
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        See [users](users.md).
        """,
    )
    _write(
        root / "references" / "metrics" / "dau.md",
        """
        ---
        type: Reference
        title: Daily active users
        description: DAU metric.
        resource: https://example.com/dau
        tags: [metric]
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        COUNT(DISTINCT user_id) per day.
        """,
    )
    # An index.md must NOT be loaded as a concept.
    _write(root / "index.md", "# My Bundle\n- tables/users\n- tables/events\n")


def test_load_collects_concepts_excluding_index(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    assert len(b) == 4
    ids = {c.id for c in b}
    assert "index" not in ids
    assert ids == {
        "datasets/my_dataset",
        "tables/users",
        "tables/events",
        "references/metrics/dau",
    }


def test_edges_capture_relative_cross_links(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    pairs = set(b.edges())
    assert ("datasets/my_dataset", "tables/users") in pairs
    assert ("tables/users", "tables/events") in pairs
    assert ("tables/users", "references/metrics/dau") in pairs
    assert ("tables/events", "tables/users") in pairs


def test_backlinks_reverse_the_graph(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    assert set(b.backlinks("tables/users")) == {
        "datasets/my_dataset",
        "tables/events",
    }
    assert b.backlinks("datasets/my_dataset") == []


def test_types_are_sorted_unique(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    assert b.types() == ["BigQuery Dataset", "BigQuery Table", "Reference"]


def test_concept_accessors_and_full_frontmatter_preserved(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    c = b.get("tables/users")
    assert c is not None
    assert c.type == "BigQuery Table"
    assert c.title == "Users"
    assert c.description == "User profiles."
    assert c.resource == "https://example.com/users"
    assert c.tags == ["users"]
    assert "tables/users" in b
    # Arbitrary frontmatter is preserved on the underlying document.
    assert c.document.frontmatter["timestamp"] == "2026-05-28T00:00:00+00:00"


def test_missing_link_targets_are_skipped(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "tables" / "lonely.md",
        """
        ---
        type: BigQuery Table
        title: Lonely
        description: Has a dangling link.
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Links to [missing](missing.md).
        """,
    )
    b = Bundle.load(root)
    assert len(b) == 1
    assert b.edges() == []


def test_absolute_bundle_root_links_resolve(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "datasets" / "sales.md",
        """
        ---
        type: BigQuery Dataset
        title: Sales
        description: Sales dataset.
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Contains [orders](/tables/orders.md).
        """,
    )
    _write(
        root / "tables" / "orders.md",
        """
        ---
        type: BigQuery Table
        title: Orders
        description: Orders table.
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Part of [sales](/datasets/sales.md).
        """,
    )
    b = Bundle.load(root)
    pairs = set(b.edges())
    assert ("datasets/sales", "tables/orders") in pairs
    assert ("tables/orders", "datasets/sales") in pairs


def test_load_raises_when_bundle_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Bundle.load(tmp_path / "nope")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/okf-core/tests/test_bundle.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'okf_core.bundle'`.

- [ ] **Step 3: Write the implementation**

Create `packages/okf-core/src/okf_core/bundle.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from okf_core.document import OKFDocument, OKFDocumentError

_INDEX_NAME = "index.md"
_LINK_RE = re.compile(r"\]\(([^)\s]+\.md)(?:#[A-Za-z0-9_\-]*)?\)")


def extract_links(body: str, doc_dir: Path, bundle_root: Path) -> list[str]:
    """Resolve the markdown links in ``body`` to concept ids.

    Relative links resolve against the document's directory; absolute links
    beginning with ``/`` resolve against ``bundle_root`` (the OKF-recommended
    form). External ``scheme://`` links are skipped. Results are normalized to
    concept ids (``.md`` removed) and deduped, preserving first-seen order.
    """
    out: list[str] = []
    seen: set[str] = set()
    bundle_root_resolved = bundle_root.resolve()
    for m in _LINK_RE.finditer(body):
        target = m.group(1)
        if "://" in target:
            continue
        if target.startswith("/"):
            base = bundle_root_resolved
            rel_target = target.lstrip("/")
        else:
            base = doc_dir
            rel_target = target
        try:
            resolved = (base / rel_target).resolve().relative_to(bundle_root_resolved)
        except ValueError:
            continue
        rel = resolved.as_posix()
        if rel.endswith(".md"):
            rel = rel[:-3]
        if rel and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


@dataclass
class Concept:
    id: str
    document: OKFDocument
    links_to: list[str] = field(default_factory=list)

    @property
    def type(self) -> str:
        return str(self.document.frontmatter.get("type") or "Unknown")

    @property
    def title(self) -> str:
        return str(self.document.frontmatter.get("title") or self.id)

    @property
    def description(self) -> str:
        return str(self.document.frontmatter.get("description") or "")

    @property
    def resource(self) -> str:
        return str(self.document.frontmatter.get("resource") or "")

    @property
    def tags(self) -> list[str]:
        raw = self.document.frontmatter.get("tags") or []
        if not isinstance(raw, list):
            raw = [raw]
        return [str(t) for t in raw]

    @property
    def body(self) -> str:
        return self.document.body


@dataclass
class Bundle:
    root: Path
    concepts: list[Concept] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_id: dict[str, Concept] = {c.id: c for c in self.concepts}

    @classmethod
    def load(cls, root: Path | str) -> "Bundle":
        root = Path(root)
        if not root.is_dir():
            raise FileNotFoundError(f"Bundle directory not found: {root}")
        concepts: list[Concept] = []
        for md_path in sorted(root.rglob("*.md")):
            if md_path.name == _INDEX_NAME:
                continue
            rel = md_path.relative_to(root).with_suffix("")
            concept_id = "/".join(rel.parts)
            try:
                doc = OKFDocument.parse(md_path.read_text(encoding="utf-8"))
            except OKFDocumentError:
                continue
            links = extract_links(doc.body or "", md_path.parent, root)
            concepts.append(Concept(id=concept_id, document=doc, links_to=links))
        return cls(root=root, concepts=concepts)

    def get(self, concept_id: str) -> Concept | None:
        return self._by_id.get(concept_id)

    def __contains__(self, concept_id: object) -> bool:
        return concept_id in self._by_id

    def __iter__(self):
        return iter(self.concepts)

    def __len__(self) -> int:
        return len(self.concepts)

    def edges(self) -> list[tuple[str, str]]:
        ids = set(self._by_id)
        out: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for c in self.concepts:
            for target in c.links_to:
                if target == c.id or target not in ids:
                    continue
                key = (c.id, target)
                if key in seen:
                    continue
                seen.add(key)
                out.append(key)
        return out

    def backlinks(self, concept_id: str) -> list[str]:
        return [src for src, tgt in self.edges() if tgt == concept_id]

    def types(self) -> list[str]:
        return sorted({c.type for c in self.concepts})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/okf-core/tests/test_bundle.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/okf-core/src/okf_core/bundle.py packages/okf-core/tests/test_bundle.py
git commit -m "feat: add Bundle concept-graph loader

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `synthesizer.py` + `index.py` — index.md regeneration

**Files:**
- Create: `packages/okf-core/src/okf_core/synthesizer.py`
- Create: `packages/okf-core/src/okf_core/index.py`
- Test: `packages/okf-core/tests/test_index.py`

**Interfaces:**
- Consumes: `okf_core.document.OKFDocument` (from Task 2).
- Produces:
  - `fallback_synthesizer(rel_path: str, children: list[tuple[str, str]]) -> str`
  - `regenerate_indexes(bundle_root: Path | str, *, synthesize: Callable[[str, list[tuple[str, str]]], str] = fallback_synthesizer) -> list[Path]`

- [ ] **Step 1: Write the failing tests**

Create `packages/okf-core/tests/test_index.py`:

```python
from __future__ import annotations

from pathlib import Path

from okf_core.document import OKFDocument
from okf_core.index import regenerate_indexes


def _stub_synth(rel: str, children: list[tuple[str, str]]) -> str:
    return f"stub: {len(children)} items"


def _write_doc(path: Path, type_: str, title: str, description: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = OKFDocument(
        frontmatter={
            "type": type_,
            "title": title,
            "description": description,
            "timestamp": "2026-05-27T00:00:00+00:00",
        },
        body=f"# {title}\n\n{description}\n",
    )
    path.write_text(doc.serialize(), encoding="utf-8")


def test_regenerate_groups_by_type_and_links_relative(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(
        root / "datasets" / "ga4.md",
        "BigQuery Dataset",
        "GA4 Dataset",
        "GA4 obfuscated ecommerce sample.",
    )
    _write_doc(
        root / "tables" / "events_.md",
        "BigQuery Table",
        "events_*",
        "Daily-sharded GA4 event tables.",
    )
    _write_doc(
        root / "tables" / "users.md",
        "BigQuery Table",
        "users",
        "Per-user dimension.",
    )

    written = regenerate_indexes(root, synthesize=_stub_synth)
    written_names = {p.parent.name for p in written}
    assert {"bundle", "datasets", "tables"} <= written_names | {root.name}

    tables_index = (root / "tables" / "index.md").read_text(encoding="utf-8")
    assert tables_index.startswith("# BigQuery Table")
    assert "[events_*](events_.md)" in tables_index
    assert "[users](users.md)" in tables_index
    assert "Daily-sharded GA4 event tables." in tables_index

    root_index = (root / "index.md").read_text(encoding="utf-8")
    assert "# Subdirectories" in root_index
    assert "(datasets/index.md) - GA4 obfuscated ecommerce sample." in root_index
    assert "(tables/index.md) - stub: 2 items" in root_index


def test_regenerate_skips_empty_directories(tmp_path: Path):
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "empty_dir").mkdir()

    written = regenerate_indexes(root, synthesize=_stub_synth)
    assert written == []
    assert not (root / "empty_dir" / "index.md").exists()


def test_regenerate_single_child_reuses_description(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(
        root / "datasets" / "only.md",
        "BigQuery Dataset",
        "Only Dataset",
        "The only dataset in this bundle.",
    )

    call_count = 0

    def counting_synth(rel: str, children: list[tuple[str, str]]) -> str:
        nonlocal call_count
        call_count += 1
        return f"stub: {len(children)} items"

    regenerate_indexes(root, synthesize=counting_synth)

    root_index = (root / "index.md").read_text(encoding="utf-8")
    assert "(datasets/index.md) - The only dataset in this bundle." in root_index
    assert call_count == 0


def test_default_fallback_synthesizer_summarizes_multi_child_dir(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(root / "tables" / "a.md", "BigQuery Table", "Alpha", "First.")
    _write_doc(root / "tables" / "b.md", "BigQuery Table", "Beta", "Second.")

    regenerate_indexes(root)  # no synthesize override -> deterministic fallback

    root_index = (root / "index.md").read_text(encoding="utf-8")
    assert "(tables/index.md) - Contains 2 entries: Alpha, Beta." in root_index


def test_regenerate_nonexistent_root_returns_empty(tmp_path: Path):
    assert regenerate_indexes(tmp_path / "nope") == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/okf-core/tests/test_index.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'okf_core.index'`.

- [ ] **Step 3: Write the synthesizer**

Create `packages/okf-core/src/okf_core/synthesizer.py`:

```python
from __future__ import annotations


def fallback_synthesizer(rel_path: str, children: list[tuple[str, str]]) -> str:
    """Deterministic one-line directory summary used by ``regenerate_indexes``.

    ``children`` is a list of ``(title, description)`` pairs. Returns
    ``"Contains N entries: <comma-joined titles>."`` (or ``"no titled entries"``
    when none of the children have a title), and ``""`` when there are no
    children.

    To generate richer (e.g. LLM-backed) summaries, pass any callable with this
    same ``(rel_path, children) -> str`` signature as
    ``regenerate_indexes(..., synthesize=...)``.
    """
    if not children:
        return ""
    titles = ", ".join(t for t, _ in children if t) or "no titled entries"
    return f"Contains {len(children)} entries: {titles}."
```

- [ ] **Step 4: Write the index generator**

Create `packages/okf-core/src/okf_core/index.py`:

```python
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable

from okf_core.document import OKFDocument
from okf_core.synthesizer import fallback_synthesizer

_INDEX_FILE = "index.md"

Synthesizer = Callable[[str, list[tuple[str, str]]], str]


def _load_doc(path: Path) -> OKFDocument | None:
    try:
        return OKFDocument.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_index_text(entries: list[tuple[str, str, str, str]]) -> str:
    # entries: (type, title, relative_link, description)
    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for typ, title, link, desc in entries:
        grouped[typ or "Other"].append((title, link, desc))

    sections: list[str] = []
    for typ in sorted(grouped):
        lines = [f"# {typ}", ""]
        for title, link, desc in sorted(grouped[typ], key=lambda e: e[0].lower()):
            suffix = f" - {desc}" if desc else ""
            lines.append(f"* [{title}]({link}){suffix}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


def _directories_to_index(bundle_root: Path) -> list[Path]:
    dirs: set[Path] = set()
    for md in bundle_root.rglob("*.md"):
        cur = md.parent
        while cur != bundle_root.parent:
            dirs.add(cur)
            if cur == bundle_root:
                break
            cur = cur.parent
    return sorted(dirs)


def regenerate_indexes(
    bundle_root: Path | str,
    *,
    synthesize: Synthesizer = fallback_synthesizer,
) -> list[Path]:
    bundle_root = Path(bundle_root)
    written: list[Path] = []
    if not bundle_root.exists():
        return written

    directories = sorted(
        _directories_to_index(bundle_root),
        key=lambda p: (-len(p.relative_to(bundle_root).parts), str(p)),
    )

    dir_descriptions: dict[Path, str] = {}

    for directory in directories:
        entries: list[tuple[str, str, str, str]] = []

        for child in sorted(directory.iterdir()):
            if child.name == _INDEX_FILE:
                continue
            if child.is_file() and child.suffix == ".md":
                doc = _load_doc(child)
                if doc is None:
                    continue
                fm = doc.frontmatter
                title = str(fm.get("title") or child.stem)
                desc = str(fm.get("description") or "")
                typ = str(fm.get("type") or "")
                entries.append((typ, title, child.name, desc))
            elif child.is_dir():
                desc = dir_descriptions.get(child, "")
                entries.append(
                    ("Subdirectories", child.name, f"{child.name}/{_INDEX_FILE}", desc)
                )

        if not entries:
            continue

        index_path = directory / _INDEX_FILE
        index_path.write_text(_build_index_text(entries), encoding="utf-8")
        written.append(index_path)

        if directory == bundle_root:
            continue

        pairs = [(title, desc) for _, title, _, desc in entries]
        if len(pairs) == 1 and pairs[0][1]:
            dir_descriptions[directory] = pairs[0][1]
        else:
            rel = str(directory.relative_to(bundle_root))
            dir_descriptions[directory] = synthesize(rel, pairs)

    return written
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/okf-core/tests/test_index.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add packages/okf-core/src/okf_core/synthesizer.py packages/okf-core/src/okf_core/index.py packages/okf-core/tests/test_index.py
git commit -m "feat: add index.md regeneration with deterministic synthesizer

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Public API + docs

**Files:**
- Modify: `packages/okf-core/src/okf_core/__init__.py` (replace minimal stub with full re-exports)
- Create: `packages/okf-core/tests/test_api.py`
- Modify: `README.md` (repo root)
- Modify: `CLAUDE.md` (repo root)

**Interfaces:**
- Consumes: everything produced by Tasks 2–5.
- Produces: the top-level `okf_core` public API — `OKFDocument`, `OKFDocumentError`, `REQUIRED_FRONTMATTER_KEYS`, `Concept`, `Bundle`, `extract_links`, `concept_id_to_path`, `path_to_concept_id`, `parse_concept_id`, `regenerate_indexes`, `fallback_synthesizer`, `__version__`.

- [ ] **Step 1: Write the failing test**

Create `packages/okf-core/tests/test_api.py`:

```python
from __future__ import annotations


def test_public_api_is_importable_from_top_level():
    import okf_core

    expected = {
        "OKFDocument",
        "OKFDocumentError",
        "REQUIRED_FRONTMATTER_KEYS",
        "Concept",
        "Bundle",
        "extract_links",
        "concept_id_to_path",
        "path_to_concept_id",
        "parse_concept_id",
        "regenerate_indexes",
        "fallback_synthesizer",
    }
    assert expected <= set(okf_core.__all__)
    for name in expected:
        assert hasattr(okf_core, name), f"okf_core.{name} is not exported"
    assert okf_core.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/okf-core/tests/test_api.py -v`
Expected: FAIL (the names are not yet exported from `okf_core/__init__.py`).

- [ ] **Step 3: Replace `__init__.py` with the full public API**

Overwrite `packages/okf-core/src/okf_core/__init__.py`:

```python
"""okf_core — read and index Open Knowledge Format (OKF) bundles."""
from __future__ import annotations

from okf_core.bundle import Bundle, Concept, extract_links
from okf_core.document import (
    REQUIRED_FRONTMATTER_KEYS,
    OKFDocument,
    OKFDocumentError,
)
from okf_core.index import regenerate_indexes
from okf_core.paths import (
    concept_id_to_path,
    parse_concept_id,
    path_to_concept_id,
)
from okf_core.synthesizer import fallback_synthesizer

__version__ = "0.1.0"

__all__ = [
    "Bundle",
    "Concept",
    "extract_links",
    "OKFDocument",
    "OKFDocumentError",
    "REQUIRED_FRONTMATTER_KEYS",
    "concept_id_to_path",
    "parse_concept_id",
    "path_to_concept_id",
    "regenerate_indexes",
    "fallback_synthesizer",
    "__version__",
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/okf-core/tests/test_api.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Update the root README**

Overwrite `README.md` (repo root):

```markdown
# okf-sdk

A uv workspace of Open Knowledge Format (OKF) tooling.

## Packages

- [`packages/okf-core`](packages/okf-core/) — core library for reading and
  indexing OKF bundles: parse documents, load a bundle into an in-memory concept
  graph (cross-links + backlinks), and regenerate `index.md` listings. Only
  runtime dependency is PyYAML.

## Development

```bash
uv sync            # create/update the shared .venv with all workspace members
uv run pytest      # run the full test suite
```

Add a new package under `packages/<name>/` with its own `pyproject.toml`; it is
picked up automatically by the `[tool.uv.workspace]` members glob.
```

- [ ] **Step 6: Update CLAUDE.md to reflect the new structure**

In `CLAUDE.md` (repo root), replace the `## Project status` section's body and the `## Commands` section so they describe the workspace. Apply these two edits:

Replace the `## Project status` paragraph with:

```markdown
## Project status

`okf-sdk` is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
of Open Knowledge Format tooling. The root `pyproject.toml` is a **virtual**
workspace root (no `[project]` of its own); packages live under `packages/*`.

The first and currently only member is **`packages/okf-core`** — a library for
reading and indexing OKF bundles (`OKFDocument`, `Bundle`, `regenerate_indexes`).
Its only runtime dependency is PyYAML. See
`docs/superpowers/specs/2026-06-25-okf-core-indexing-library-design.md` for the
design.
```

Replace the `## Commands` list with:

```markdown
## Commands

- `uv sync` — create/update the shared `.venv` with all workspace members (installed editable) plus the dev dependency group
- `uv run pytest` — run the full test suite (config in the root `pyproject.toml`)
- `uv run pytest packages/okf-core/tests/test_bundle.py::test_load_collects_concepts_excluding_index -v` — run a single test
- `uv add --package okf-core <package>` — add a runtime dependency to the okf-core member
- `uv add --dev <package>` — add a dev dependency to the workspace root
```

- [ ] **Step 7: Run the full test suite**

Run: `uv run pytest`
Expected: PASS — all tests across `test_import.py` (1), `test_document.py` (5), `test_paths.py` (5), `test_bundle.py` (8), `test_index.py` (5), `test_api.py` (1) green (25 passed).

- [ ] **Step 8: Commit**

```bash
git add packages/okf-core/src/okf_core/__init__.py packages/okf-core/tests/test_api.py README.md CLAUDE.md
git commit -m "feat: expose okf_core public API and update docs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- Run every command from the repo root (`okf-sdk/`). `uv run` auto-syncs the
  environment, so you don't need to activate `.venv` manually.
- If `uv sync` in Task 1 reports that the workspace root needs a `[project]`
  table, that indicates an older uv; the fix is to upgrade uv (`uv self update`).
  Do **not** add a `[project]` to the root — the virtual-root layout is
  intentional.
- The ported modules (`document.py`, `paths.py`, `index.py`) are near-verbatim
  copies of `~/Programming/research/knowledge-catalog/okf/src/reference_agent/bundle/`;
  if a test diverges, compare against that source rather than guessing.
