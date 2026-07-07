from __future__ import annotations

from pathlib import Path

from okf_core.document import OKFDocument
from okf_core.index import regenerate_indexes


def _stub_synth(rel: str, children: list[tuple[str, str]]) -> str:
    return f"stub: {len(children)} items"


def _write_doc(
    path: Path, type_: str, title: str, description: str, *, tags=None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = {
        "type": type_,
        "title": title,
        "description": description,
        "timestamp": "2026-05-27T00:00:00+00:00",
    }
    if tags is not None:
        fm["tags"] = tags
    doc = OKFDocument(
        frontmatter=fm,
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

    tables_index = (root / "tables" / "_index.md").read_text(encoding="utf-8")
    assert tables_index.startswith("# BigQuery Table")
    assert "[events_*](events_.md)" in tables_index
    assert "[users](users.md)" in tables_index
    assert "Daily-sharded GA4 event tables." in tables_index

    root_index = (root / "_index.md").read_text(encoding="utf-8")
    assert "# Subdirectories" in root_index
    assert "(datasets/_index.md) - stub: 1 items" in root_index
    assert "(tables/_index.md) - stub: 2 items" in root_index


def test_regenerate_skips_empty_directories(tmp_path: Path):
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "empty_dir").mkdir()

    written = regenerate_indexes(root, synthesize=_stub_synth)
    assert written == []
    assert not (root / "empty_dir" / "_index.md").exists()


def test_regenerate_single_child_synthesizes_not_reuses(tmp_path: Path):
    # The old single-child reuse shortcut is dropped: a directory with no
    # authored description always gets a synthesized caption, even with one child.
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

    root_index = (root / "_index.md").read_text(encoding="utf-8")
    assert "The only dataset in this bundle." not in root_index
    assert "(datasets/_index.md) - stub: 1 items" in root_index
    assert call_count == 1


def test_default_fallback_synthesizer_summarizes_multi_child_dir(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(root / "tables" / "a.md", "BigQuery Table", "Alpha", "First.")
    _write_doc(root / "tables" / "b.md", "BigQuery Table", "Beta", "Second.")

    regenerate_indexes(root)  # no synthesize override -> deterministic fallback

    root_index = (root / "_index.md").read_text(encoding="utf-8")
    assert "(tables/_index.md) - Contains 2 entries: Alpha, Beta." in root_index


def test_regenerate_excludes_log_file(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(
        root / "tables" / "users.md",
        "BigQuery Table",
        "users",
        "Per-user dimension.",
    )
    (root / "tables" / "_log.md").write_text(
        "# Update Log\n\n## 2026-06-30\n* **Creation**: Added [users](users.md).\n",
        encoding="utf-8",
    )

    regenerate_indexes(root, synthesize=_stub_synth)

    tables_index = (root / "tables" / "_index.md").read_text(encoding="utf-8")
    assert "_log" not in tables_index
    assert "(_log.md)" not in tables_index


def test_regenerate_appends_tags_suffix(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(
        root / "tables" / "orders.md",
        "BigQuery Table",
        "Orders",
        "Daily order facts.",
        tags=["billing", "daily"],
    )

    regenerate_indexes(root, synthesize=_stub_synth)

    tables_index = (root / "tables" / "_index.md").read_text(encoding="utf-8")
    assert (
        "* [Orders](orders.md) - Daily order facts. _(tags: billing, daily)_"
        in tables_index
    )


def test_regenerate_omits_tags_suffix_when_absent(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(root / "tables" / "users.md", "BigQuery Table", "users", "Per-user dim.")

    regenerate_indexes(root, synthesize=_stub_synth)

    tables_index = (root / "tables" / "_index.md").read_text(encoding="utf-8")
    assert "_(tags:" not in tables_index
    assert "* [users](users.md) - Per-user dim." in tables_index


def test_regenerate_tags_suffix_without_description(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(
        root / "tables" / "orders.md", "BigQuery Table", "Orders", "", tags=["billing"]
    )

    regenerate_indexes(root, synthesize=_stub_synth)

    tables_index = (root / "tables" / "_index.md").read_text(encoding="utf-8")
    assert "* [Orders](orders.md) _(tags: billing)_" in tables_index
    assert "orders.md) - _(tags" not in tables_index  # no stray " - "


def test_regenerate_normalizes_non_list_tags(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(
        root / "tables" / "orders.md",
        "BigQuery Table",
        "Orders",
        "Daily order facts.",
        tags="billing",
    )

    regenerate_indexes(root, synthesize=_stub_synth)

    tables_index = (root / "tables" / "_index.md").read_text(encoding="utf-8")
    assert "_(tags: billing)_" in tables_index


def test_regenerate_nonexistent_root_returns_empty(tmp_path: Path):
    assert regenerate_indexes(tmp_path / "nope") == []


def test_authored_description_preserved_across_reindex(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(root / "tables" / "orders.md", "Table", "Orders", "One row per order.")
    regenerate_indexes(root)  # creates tables/_index.md (no frontmatter)
    idx = root / "tables" / "_index.md"
    idx.write_text(
        "---\ndescription: Sales tables.\n---\n\n" + idx.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    regenerate_indexes(root)

    fm = OKFDocument.parse((root / "tables" / "_index.md").read_text()).frontmatter
    assert fm == {"description": "Sales tables."}


def test_authored_description_lifted_into_parent_caption(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(root / "tables" / "orders.md", "Table", "Orders", "One row per order.")
    regenerate_indexes(root)
    idx = root / "tables" / "_index.md"
    idx.write_text(
        "---\ndescription: Sales tables.\n---\n\n" + idx.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    regenerate_indexes(root)

    assert (
        "[tables](tables/_index.md) - Sales tables." in (root / "_index.md").read_text()
    )


def test_root_okf_version_preserved(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(root / "a.md", "Doc", "A", "First.")
    regenerate_indexes(root)
    root_idx = root / "_index.md"
    root_idx.write_text(
        '---\nokf_version: "0.1"\n---\n\n' + root_idx.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    regenerate_indexes(root)

    fm = OKFDocument.parse((root / "_index.md").read_text()).frontmatter
    assert fm == {"okf_version": "0.1"}


def test_non_allowlisted_index_frontmatter_pruned(tmp_path: Path):
    root = tmp_path / "bundle"
    _write_doc(root / "d" / "c.md", "Doc", "C", "Third.")
    regenerate_indexes(root)
    idx = root / "d" / "_index.md"
    idx.write_text(
        "---\ndescription: Keep me.\nbogus: drop me\n---\n\n"
        + idx.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    regenerate_indexes(root)

    fm = OKFDocument.parse((root / "d" / "_index.md").read_text()).frontmatter
    assert fm == {"description": "Keep me."}


def test_okf_version_dropped_from_subdir_index(tmp_path: Path):
    # okf_version is a root-only key; regeneration must not keep it in a subdir.
    root = tmp_path / "bundle"
    _write_doc(root / "sub" / "c.md", "Doc", "C", "Third.")
    regenerate_indexes(root)
    idx = root / "sub" / "_index.md"
    idx.write_text(
        '---\nokf_version: "0.1"\n---\n\n' + idx.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    regenerate_indexes(root)

    fm = OKFDocument.parse((root / "sub" / "_index.md").read_text()).frontmatter
    assert fm == {}
