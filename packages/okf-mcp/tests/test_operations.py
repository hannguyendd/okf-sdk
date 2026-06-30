import pytest
from okf_core import OKFDocument

from okf_mcp import operations


def test_resolve_prefers_arg(tmp_path):
    other = tmp_path / "b"
    other.mkdir()
    assert operations.resolve_bundle_root(str(other), tmp_path) == other.resolve()


def test_resolve_falls_back_to_env_default(tmp_path):
    assert operations.resolve_bundle_root(None, tmp_path) == tmp_path.resolve()


def test_resolve_requires_a_root():
    with pytest.raises(ValueError):
        operations.resolve_bundle_root(None, None)


def test_resolve_rejects_non_directory(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        operations.resolve_bundle_root(str(f), None)


def test_concept_path_builds_nested_path(tmp_path):
    assert (
        operations._concept_path(tmp_path, "tables/orders")
        == tmp_path / "tables" / "orders.md"
    )


def test_concept_path_rejects_reserved(tmp_path):
    with pytest.raises(ValueError):
        operations._concept_path(tmp_path, "tables/_index")


def test_concept_path_rejects_bad_segment(tmp_path):
    with pytest.raises(ValueError):
        operations._concept_path(tmp_path, "tables/bad name")


def test_append_log_creates_file(tmp_path):
    log = tmp_path / "_log.md"
    operations._append_log(log, "* **Creation**: Added [A](a.md).", "2026-06-29")
    text = log.read_text()
    assert "# Update Log" in text
    assert "## 2026-06-29" in text
    assert "* **Creation**: Added [A](a.md)." in text


def test_append_log_prepends_under_existing_today(tmp_path):
    log = tmp_path / "_log.md"
    log.write_text("# Update Log\n\n## 2026-06-29\n* **Creation**: Added [A](a.md).\n")
    operations._append_log(log, "* **Update**: Updated [B](b.md).", "2026-06-29")
    lines = log.read_text().splitlines()
    i = lines.index("## 2026-06-29")
    assert lines[i + 1] == "* **Update**: Updated [B](b.md)."  # newest first
    assert lines[i + 2] == "* **Creation**: Added [A](a.md)."


def test_append_log_inserts_new_today_above_older(tmp_path):
    log = tmp_path / "_log.md"
    log.write_text("# Update Log\n\n## 2026-06-01\n* **Creation**: Added [A](a.md).\n")
    operations._append_log(log, "* **Update**: Updated [A](a.md).", "2026-06-29")
    lines = log.read_text().splitlines()
    assert lines.index("## 2026-06-29") < lines.index("## 2026-06-01")


def test_add_writes_concept(tmp_path):
    res = operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "# Schema\n"
    )
    f = tmp_path / "tables" / "orders.md"
    assert f.exists()
    doc = OKFDocument.parse(f.read_text())
    assert doc.frontmatter["type"] == "Table"
    assert doc.frontmatter["title"] == "Orders"
    assert "timestamp" in doc.frontmatter
    assert "# Schema" in doc.body
    assert res["action"] == "created"
    assert res["path"] == "tables/orders.md"


def test_add_rejects_existing(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    with pytest.raises(ValueError):
        operations.add_concept(tmp_path, "a", {"type": "X"}, "")


def test_add_requires_type(tmp_path):
    with pytest.raises(ValueError):
        operations.add_concept(tmp_path, "a", {"title": "no type"}, "")


def test_add_rejects_reserved_id(tmp_path):
    with pytest.raises(ValueError):
        operations.add_concept(tmp_path, "tables/_index", {"type": "X"}, "")


def test_add_preserves_caller_timestamp(tmp_path):
    operations.add_concept(
        tmp_path, "a", {"type": "X", "timestamp": "2020-01-01T00:00:00Z"}, ""
    )
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["timestamp"] == "2020-01-01T00:00:00Z"


def test_add_writes_log_and_index(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    log = tmp_path / "tables" / "_log.md"
    assert "Added [Orders](orders.md)" in log.read_text()
    assert (tmp_path / "tables" / "_index.md").exists()
    assert (tmp_path / "_index.md").exists()


def test_patch_merges_only_given_keys(tmp_path):
    operations.add_concept(
        tmp_path, "a", {"type": "X", "title": "Old", "description": "keep"}, "body"
    )
    operations.patch_concept(tmp_path, "a", {"title": "New"})
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["title"] == "New"
    assert doc.frontmatter["description"] == "keep"
    assert doc.frontmatter["type"] == "X"


def test_patch_ignores_none_values(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X", "title": "Old"}, "")
    operations.patch_concept(tmp_path, "a", {"title": None})
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["title"] == "Old"


def test_patch_replaces_body_only_when_given(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "original")
    operations.patch_concept(tmp_path, "a", {"title": "T"})
    assert OKFDocument.parse((tmp_path / "a.md").read_text()).body.strip() == "original"
    operations.patch_concept(tmp_path, "a", body="replaced")
    assert OKFDocument.parse((tmp_path / "a.md").read_text()).body.strip() == "replaced"


def test_patch_refreshes_timestamp(tmp_path):
    operations.add_concept(
        tmp_path, "a", {"type": "X", "timestamp": "2020-01-01T00:00:00Z"}, ""
    )
    operations.patch_concept(tmp_path, "a", {"title": "T"})
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["timestamp"] != "2020-01-01T00:00:00Z"


def test_patch_keeps_caller_timestamp(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    operations.patch_concept(tmp_path, "a", {"timestamp": "2030-01-01T00:00:00Z"})
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["timestamp"] == "2030-01-01T00:00:00Z"


def test_patch_missing_errors(tmp_path):
    with pytest.raises(ValueError):
        operations.patch_concept(tmp_path, "nope", {"title": "X"})


def test_patch_logs_update(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X", "title": "A"}, "")
    operations.patch_concept(tmp_path, "a", {"title": "A2"})
    assert "Updated [A2](a.md)" in (tmp_path / "_log.md").read_text()


def test_get_returns_doc(tmp_path):
    operations.add_concept(
        tmp_path,
        "tables/orders",
        {"type": "Table", "title": "Orders"},
        "see [c](customers.md)",
    )
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    res = operations.get_concept(tmp_path, "tables/orders")
    assert res["id"] == "tables/orders"
    assert res["frontmatter"]["type"] == "Table"
    assert "tables/customers" in res["links_to"]


def test_get_missing_errors(tmp_path):
    with pytest.raises(ValueError):
        operations.get_concept(tmp_path, "nope")


def test_list_all(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.add_concept(
        tmp_path, "metrics/mau", {"type": "Metric", "title": "MAU"}, ""
    )
    ids = {c["id"] for c in operations.list_concepts(tmp_path)}
    assert ids == {"tables/orders", "metrics/mau"}


def test_list_filters_by_type(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(tmp_path, "metrics/mau", {"type": "Metric"}, "")
    res = operations.list_concepts(tmp_path, type="Metric")
    assert [c["id"] for c in res] == ["metrics/mau"]


def test_list_filters_by_prefix(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(tmp_path, "metrics/mau", {"type": "Metric"}, "")
    res = operations.list_concepts(tmp_path, prefix="tables/")
    assert [c["id"] for c in res] == ["tables/orders"]


def test_read_index_depth_one(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    res = operations.read_index(tmp_path)
    assert len(res) == 1
    assert res[0]["dir"] == ""
    assert res[0]["path"] == "_index.md"
    assert "tables" in res[0]["content"]


def test_read_index_depth_two_descends(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    res = operations.read_index(tmp_path, depth=2)
    dirs = {r["dir"] for r in res}
    assert "" in dirs and "tables" in dirs


def test_read_index_specific_dir(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    res = operations.read_index(tmp_path, dir="tables")
    assert res[0]["dir"] == "tables"
    assert "Orders" in res[0]["content"]


def test_read_index_bad_depth(tmp_path):
    with pytest.raises(ValueError):
        operations.read_index(tmp_path, depth=4)


def test_read_index_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        operations.read_index(tmp_path, dir="../outside")


def test_read_index_missing_is_empty(tmp_path):
    assert operations.read_index(tmp_path) == []


def test_move_renames_in_place(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    res = operations.move_concept(tmp_path, "tables/orders", "tables/sales")
    assert not (tmp_path / "tables" / "orders.md").exists()
    assert (tmp_path / "tables" / "sales.md").exists()
    assert res["action"] == "moved"
    assert res["from"] == "tables/orders"
    assert res["to"] == "tables/sales"
    assert res["relinked"] == []


def test_move_across_directories(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.move_concept(tmp_path, "tables/orders", "models/orders")
    assert not (tmp_path / "tables" / "orders.md").exists()
    assert (tmp_path / "models" / "orders.md").exists()


def test_move_preserves_timestamp(tmp_path):
    operations.add_concept(
        tmp_path, "a", {"type": "X", "timestamp": "2020-01-01T00:00:00Z"}, ""
    )
    operations.move_concept(tmp_path, "a", "b")
    doc = OKFDocument.parse((tmp_path / "b.md").read_text())
    assert doc.frontmatter["timestamp"] == "2020-01-01T00:00:00Z"


def test_move_logs_dest_and_source(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    res = operations.move_concept(tmp_path, "tables/orders", "models/orders")
    dest_log = (tmp_path / "models" / "_log.md").read_text()
    src_log = (tmp_path / "tables" / "_log.md").read_text()
    assert "Moved [Orders](orders.md) from `tables/orders`" in dest_log
    assert "Moved [Orders](orders.md) to `models/orders`" in src_log
    assert set(res["logs"]) == {"models/_log.md", "tables/_log.md"}


def test_move_in_dir_logs_once(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    res = operations.move_concept(tmp_path, "tables/orders", "tables/sales")
    assert res["logs"] == ["tables/_log.md"]
    assert (
        "Moved [Orders](sales.md) from `tables/orders`"
        in (tmp_path / "tables" / "_log.md").read_text()
    )


def test_move_regenerates_indexes(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    res = operations.move_concept(tmp_path, "tables/orders", "models/orders")
    assert (tmp_path / "models" / "_index.md").exists()
    assert "models/_index.md" in res["indexes"]


def test_move_rewrites_moved_doc_own_links(tmp_path):
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table"}, "see [c](customers.md)"
    )
    operations.move_concept(tmp_path, "tables/orders", "models/orders")
    moved = OKFDocument.parse((tmp_path / "models" / "orders.md").read_text())
    assert "(../tables/customers.md)" in moved.body


def test_move_missing_source_errors(tmp_path):
    with pytest.raises(ValueError):
        operations.move_concept(tmp_path, "nope", "dest")


def test_move_existing_dest_errors(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    operations.add_concept(tmp_path, "b", {"type": "X"}, "")
    with pytest.raises(ValueError):
        operations.move_concept(tmp_path, "a", "b")


def test_move_same_id_errors(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    with pytest.raises(ValueError):
        operations.move_concept(tmp_path, "a", "a")


def test_move_rejects_reserved_dest(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    with pytest.raises(ValueError):
        operations.move_concept(tmp_path, "a", "tables/_index")


def test_move_rewrites_inbound_relative_link(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table"}, "see [o](orders.md)"
    )
    res = operations.move_concept(tmp_path, "tables/orders", "models/orders")
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert "(../models/orders.md)" in cust.body
    assert "tables/customers" in res["relinked"]


def test_move_rewrites_inbound_absolute_link(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "metrics/rev", {"type": "Metric"}, "[o](/tables/orders.md)"
    )
    operations.move_concept(tmp_path, "tables/orders", "models/orders")
    rev = OKFDocument.parse((tmp_path / "metrics" / "rev.md").read_text())
    assert "(/models/orders.md)" in rev.body


def test_move_leaves_unrelated_concepts_untouched(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(tmp_path, "tables/suppliers", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table"}, "[s](./suppliers.md)"
    )
    res = operations.move_concept(tmp_path, "tables/orders", "models/orders")
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert "(./suppliers.md)" in cust.body  # unchanged, ./ style preserved
    assert "tables/customers" not in res["relinked"]


def test_move_inbound_preserves_frontmatter(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path,
        "tables/customers",
        {"type": "Table", "timestamp": "2020-01-01T00:00:00Z"},
        "[o](orders.md)",
    )
    operations.move_concept(tmp_path, "tables/orders", "models/orders")
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert cust.frontmatter["timestamp"] == "2020-01-01T00:00:00Z"


def test_delete_unreferenced_removes_file_and_index(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table", "title": "Customers"}, ""
    )
    res = operations.delete_concept(tmp_path, "tables/orders")
    assert not (tmp_path / "tables" / "orders.md").exists()
    assert res["action"] == "deleted"
    assert res["concept_id"] == "tables/orders"
    assert res["unlinked"] == []
    idx = (tmp_path / "tables" / "_index.md").read_text()
    assert "Customers" in idx
    assert "orders.md" not in idx


def test_delete_blocked_when_referenced(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table"}, "see [O](orders.md)"
    )
    res = operations.delete_concept(tmp_path, "tables/orders")
    assert res["action"] == "blocked"
    assert res["referenced_by"] == ["tables/customers"]
    assert (tmp_path / "tables" / "orders.md").exists()
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert "(orders.md)" in cust.body  # untouched


def test_delete_force_unlinks_relative_reference(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table"}, "see [O](orders.md) now"
    )
    res = operations.delete_concept(tmp_path, "tables/orders", force=True)
    assert not (tmp_path / "tables" / "orders.md").exists()
    assert res["unlinked"] == ["tables/customers"]
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert "see O now" in cust.body
    assert "(orders.md)" not in cust.body


def test_delete_force_unlinks_absolute_reference(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "metrics/rev", {"type": "Metric"}, "[O](/tables/orders.md)"
    )
    operations.delete_concept(tmp_path, "tables/orders", force=True)
    rev = OKFDocument.parse((tmp_path / "metrics" / "rev.md").read_text())
    assert rev.body.strip() == "O"


def test_delete_force_unlinks_anchored_reference(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(
        tmp_path, "tables/customers", {"type": "Table"}, "[O](orders.md#schema)"
    )
    operations.delete_concept(tmp_path, "tables/orders", force=True)
    cust = OKFDocument.parse((tmp_path / "tables" / "customers.md").read_text())
    assert cust.body.strip() == "O"


def test_delete_logs_deletion_entry(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    res = operations.delete_concept(tmp_path, "tables/orders")
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert "* **Deletion**: Removed `Orders`." in log
    assert "Removed [" not in log  # backticked label, not a markdown link
    assert res["log"] == "tables/_log.md"


def test_delete_force_unreferenced_behaves_like_default(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table"}, "")
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    res = operations.delete_concept(tmp_path, "tables/orders", force=True)
    assert res["action"] == "deleted"
    assert res["unlinked"] == []


def test_delete_missing_errors(tmp_path):
    with pytest.raises(ValueError):
        operations.delete_concept(tmp_path, "nope")


def test_delete_rejects_reserved(tmp_path):
    with pytest.raises(ValueError):
        operations.delete_concept(tmp_path, "tables/_index")


def _write_concept(path, type_, title):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = OKFDocument(
        frontmatter={"type": type_, "title": title, "timestamp": "2026-06-30T00:00:00Z"},
        body=f"# {title}\n",
    )
    path.write_text(doc.serialize(), encoding="utf-8")


def test_reindex_regenerates_missing_indexes(tmp_path):
    _write_concept(tmp_path / "tables" / "orders.md", "Table", "Orders")
    _write_concept(tmp_path / "tables" / "customers.md", "Table", "Customers")
    assert not (tmp_path / "tables" / "_index.md").exists()

    res = operations.reindex_bundle(tmp_path)

    assert res["action"] == "reindexed"
    assert res["count"] == len(res["indexes"])
    assert "tables/_index.md" in res["indexes"]
    assert "_index.md" in res["indexes"]
    tables_index = (tmp_path / "tables" / "_index.md").read_text()
    assert "[Orders](orders.md)" in tables_index
    assert "[Customers](customers.md)" in tables_index


def test_reindex_repairs_stale_log_entry(tmp_path):
    _write_concept(tmp_path / "tables" / "orders.md", "Table", "Orders")
    (tmp_path / "tables" / "_log.md").write_text(
        "# Update Log\n\n## 2026-06-30\n* **Creation**: Added [Orders](orders.md).\n",
        encoding="utf-8",
    )
    # A stale index left behind by the old bug, listing _log.md as a concept.
    (tmp_path / "tables" / "_index.md").write_text(
        "# Other\n\n* [_log](_log.md)\n", encoding="utf-8"
    )

    operations.reindex_bundle(tmp_path)

    tables_index = (tmp_path / "tables" / "_index.md").read_text()
    assert "_log" not in tables_index
    assert "[Orders](orders.md)" in tables_index


def test_reindex_returns_relative_posix_paths(tmp_path):
    _write_concept(tmp_path / "tables" / "orders.md", "Table", "Orders")
    res = operations.reindex_bundle(tmp_path)
    assert all(not p.startswith("/") for p in res["indexes"])
