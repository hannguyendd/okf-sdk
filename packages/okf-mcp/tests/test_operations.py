import re

import pytest
from okf_core import LocalStorage, OKFDocument

from okf_mcp import operations


def test_concept_key_builds_nested_key():
    assert operations._concept_key("tables/orders") == "tables/orders.md"


def test_concept_key_rejects_reserved():
    with pytest.raises(ValueError):
        operations._concept_key("tables/_index")


def test_concept_key_rejects_bad_segment():
    with pytest.raises(ValueError):
        operations._concept_key("tables/bad name")


def test_append_log_creates_file(tmp_path):
    log = tmp_path / "_log.md"
    operations._append_log(LocalStorage(tmp_path), "_log.md", "* **Creation**: Added [A](a.md).", "2026-06-29")
    text = log.read_text()
    assert "# Update Log" in text
    assert "## 2026-06-29" in text
    assert "* **Creation**: Added [A](a.md)." in text


def test_append_log_prepends_under_existing_today(tmp_path):
    log = tmp_path / "_log.md"
    log.write_text("# Update Log\n\n## 2026-06-29\n* **Creation**: Added [A](a.md).\n")
    operations._append_log(LocalStorage(tmp_path), "_log.md", "* **Update**: Updated [B](b.md).", "2026-06-29")
    lines = log.read_text().splitlines()
    i = lines.index("## 2026-06-29")
    assert lines[i + 1] == "* **Update**: Updated [B](b.md)."  # newest first
    assert lines[i + 2] == "* **Creation**: Added [A](a.md)."


def test_append_log_inserts_new_today_above_older(tmp_path):
    log = tmp_path / "_log.md"
    log.write_text("# Update Log\n\n## 2026-06-01\n* **Creation**: Added [A](a.md).\n")
    operations._append_log(LocalStorage(tmp_path), "_log.md", "* **Update**: Updated [A](a.md).", "2026-06-29")
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
    assert "**Deletion**: Removed `Orders`." in log
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
        frontmatter={
            "type": type_,
            "title": title,
            "timestamp": "2026-06-30T00:00:00Z",
        },
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


def test_add_log_entry_has_time_prefix(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert re.search(r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Creation\*\*:", log, re.M)


def test_patch_log_entry_has_time_prefix(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    operations.patch_concept(tmp_path, "a", {"title": "A2"})
    log = (tmp_path / "_log.md").read_text()
    assert re.search(r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Update\*\*:", log, re.M)


def test_move_log_entries_have_time_prefix(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.move_concept(tmp_path, "tables/orders", "models/orders")
    dest = (tmp_path / "models" / "_log.md").read_text()
    src = (tmp_path / "tables" / "_log.md").read_text()
    pat = r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Move\*\*:"
    assert re.search(pat, dest, re.M)
    assert re.search(pat, src, re.M)


def test_delete_log_entry_has_time_prefix(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    operations.delete_concept(tmp_path, "tables/orders")
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert re.search(r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Deletion\*\*:", log, re.M)


def test_log_heading_and_time_are_utc(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    fixed = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
    monkeypatch.setattr(operations, "_now_utc", lambda: fixed)
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert "## 2026-06-30" in log
    assert "* **23:59:59Z** **Creation**: Added [Orders](orders.md)." in log


def test_move_entries_share_one_instant(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    times = iter(
        [
            datetime(2026, 6, 30, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 30, 2, 0, 0, tzinfo=timezone.utc),
        ]
    )
    monkeypatch.setattr(operations, "_now_utc", lambda: next(times))
    operations.move_concept(tmp_path, "tables/orders", "models/orders")
    dest = (tmp_path / "models" / "_log.md").read_text()
    src = (tmp_path / "tables" / "_log.md").read_text()
    # _log_move computes _now_utc() once and reuses it for both entries.
    assert "**01:00:00Z**" in dest
    assert "**01:00:00Z**" in src


def test_describe_sets_description_and_logs(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    res = operations.describe_directory(tmp_path, "tables", "Sales tables.")

    assert res["action"] == "described"
    assert res["description"] == "Sales tables."
    assert res["dir"] == "tables"
    fm = OKFDocument.parse((tmp_path / "tables" / "_index.md").read_text()).frontmatter
    assert fm["description"] == "Sales tables."
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert "**Update**: Set description for this directory." in log


def test_describe_lifts_into_parent_caption(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.describe_directory(tmp_path, "tables", "Sales tables.")
    assert (
        "[tables](tables/_index.md) - Sales tables."
        in (tmp_path / "_index.md").read_text()
    )


def test_describe_empty_clears(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.describe_directory(tmp_path, "tables", "Sales tables.")
    res = operations.describe_directory(tmp_path, "tables", "   ")

    assert res["action"] == "cleared"
    assert res["description"] is None
    fm = OKFDocument.parse((tmp_path / "tables" / "_index.md").read_text()).frontmatter
    assert "description" not in fm
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert "**Update**: Cleared description for this directory." in log


def test_describe_overwrites_existing(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.describe_directory(tmp_path, "tables", "First.")
    operations.describe_directory(tmp_path, "tables", "Second.")
    fm = OKFDocument.parse((tmp_path / "tables" / "_index.md").read_text()).frontmatter
    assert fm["description"] == "Second."


def test_describe_errors_without_index(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError):
        operations.describe_directory(tmp_path, "empty", "nope")


def test_describe_errors_on_missing_dir(tmp_path):
    with pytest.raises(ValueError):
        operations.describe_directory(tmp_path, "nope", "x")


def test_describe_rejects_escaping_dir(tmp_path):
    with pytest.raises(ValueError):
        operations.describe_directory(tmp_path, "../outside", "nope")


def test_describe_log_entry_has_time_prefix(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.describe_directory(tmp_path, "tables", "Sales tables.")
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert re.search(r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Update\*\*:", log, re.M)


# ---- storage backends ------------------------------------------------------

from okf_core import MemoryStorage, register_backend  # noqa: E402


def _flow(root):
    """add/patch/move/delete/describe/read_index/list/reindex on any root."""
    operations.add_concept(root, "t/a", {"type": "Table", "title": "A"}, "see [b](b.md)")
    operations.add_concept(root, "t/b", {"type": "Table", "title": "B"}, "x")
    operations.patch_concept(root, "t/b", {"title": "B2"}, None)
    mv = operations.move_concept(root, "t/b", "u/b")
    assert mv["relinked"] == ["t/a"]
    assert operations.get_concept(root, "t/a")["links_to"] == ["u/b"]
    assert operations.delete_concept(root, "u/b")["action"] == "blocked"
    operations.describe_directory(root, "u", "Moved things")
    idx = operations.read_index(root, None, 2)
    assert [i["dir"] for i in idx] == ["", "t", "u"]
    assert [c["id"] for c in operations.list_concepts(root)] == ["t/a", "u/b"]
    done = operations.delete_concept(root, "u/b", force=True)
    assert done["unlinked"] == ["t/a"]
    return operations.reindex_bundle(root)


def test_operations_run_on_memory_storage_with_parity(tmp_path):
    mem, local = MemoryStorage(), LocalStorage(tmp_path)
    r_mem, r_local = _flow(mem), _flow(local)
    assert r_mem["indexes"] == r_local["indexes"]
    for key in r_local["indexes"]:
        assert mem.read_text(key) == local.read_text(key)
    assert mem.exists("t/_log.md") and local.exists("t/_log.md")


def test_write_operations_hold_the_storage_lock():
    held = []

    class Spy(MemoryStorage):
        def lock(self):
            held.append(1)
            return super().lock()

    spy = Spy()
    operations.add_concept(spy, "a", {"type": "T"}, "")
    operations.patch_concept(spy, "a", {"title": "x"}, None)
    operations.move_concept(spy, "a", "b")
    operations.describe_directory(spy, "", "d")
    operations.delete_concept(spy, "b")
    operations.reindex_bundle(spy)
    assert len(held) == 6


def test_read_index_rejects_escape_on_storage():
    with pytest.raises(ValueError, match="escapes"):
        operations.read_index(MemoryStorage(), "../x")


# --- search_workspace / create_bundle -------------------------------------

import shutil  # noqa: E402

from okf_core import MemoryStorage, WorkspaceRegistry  # noqa: E402

from okf_mcp.embeddings import EmbeddingConfig, EmbeddingError  # noqa: E402
from okf_mcp.vector_store import VectorStoreError  # noqa: E402

_WORDS = ["alpha", "beta", "gamma", "delta"]


def _search_vec(text):
    v = [0.0] * len(_WORDS)
    for i, w in enumerate(_WORDS):
        if w in text:
            v[i] = 1.0
            return v
    return [0.0, 0.0, 0.0, 1.0]


class _SearchEmbedder:
    def __init__(self):
        self.calls = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return [_search_vec(t) for t in texts]


def _workspace(tmp_path):
    ws = WorkspaceRegistry(tmp_path / "ws").create("w")
    a = ws.create_index("a")
    a.write_text("tables/_index.md", "alpha tables")
    a.write_text("views/_index.md", "beta views")
    b = ws.create_index("b", description="gamma billing data")
    b.write_text("_index.md", "beta billing root")
    return ws


def _search(ws, query, tmp_path, emb, **kw):
    kw.setdefault("config", EmbeddingConfig(url="http://h/v1", model="m"))
    return operations.search_workspace(ws, query, db_path=tmp_path / "v.db", embed=emb, **kw)


def test_search_returns_closest_index_first_with_hit_shape(tmp_path):
    hits = _search(_workspace(tmp_path), "alpha please", tmp_path, _SearchEmbedder())
    assert hits[0] == {
        "bundle": "a", "kind": "index", "dir": "tables", "path": "tables/_index.md",
        "score": pytest.approx(1.0), "excerpt": "alpha tables",
    }


def test_search_workspace_all_bundles_by_default(tmp_path):
    hits = _search(_workspace(tmp_path), "beta", tmp_path, _SearchEmbedder(), top_k=10)
    assert {h["bundle"] for h in hits} == {"a", "b"}


def test_search_workspace_bundle_filter(tmp_path):
    hits = _search(_workspace(tmp_path), "beta", tmp_path, _SearchEmbedder(), bundles=["a"], top_k=10)
    assert hits and {h["bundle"] for h in hits} == {"a"}


def test_search_workspace_unknown_bundle_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _search(_workspace(tmp_path), "beta", tmp_path, _SearchEmbedder(), bundles=["nope"])


def test_search_workspace_dir_needs_single_bundle(tmp_path):
    ws, emb = _workspace(tmp_path), _SearchEmbedder()
    with pytest.raises(ValueError, match="exactly one bundle"):
        _search(ws, "beta", tmp_path, emb, dir="views")
    hits = _search(ws, "beta", tmp_path, emb, bundles=["a"], dir="views")
    assert [h["path"] for h in hits] == ["views/_index.md"]


def test_search_workspace_finds_bundle_description(tmp_path):
    hits = _search(_workspace(tmp_path), "gamma", tmp_path, _SearchEmbedder())
    assert hits[0]["kind"] == "bundle" and hits[0]["bundle"] == "b"
    assert hits[0]["excerpt"] == "gamma billing data" and hits[0]["path"] is None


def test_search_workspace_ignores_deleted_bundle(tmp_path):
    ws, emb = _workspace(tmp_path), _SearchEmbedder()
    _search(ws, "gamma", tmp_path, emb, top_k=10)
    shutil.rmtree(ws.path / "b")
    hits = _search(ws, "gamma", tmp_path, emb, top_k=10)
    assert all(h["bundle"] != "b" for h in hits)


def test_search_syncs_before_querying(tmp_path):
    ws, emb = _workspace(tmp_path), _SearchEmbedder()
    _search(ws, "delta", tmp_path, emb)
    ws.bundle_storage("a").write_text("later/_index.md", "delta later")
    hits = _search(ws, "delta", tmp_path, emb)
    assert hits[0]["path"] == "later/_index.md"


def test_search_reembeds_changed_bundle_description(tmp_path):
    ws, emb = _workspace(tmp_path), _SearchEmbedder()
    _search(ws, "gamma", tmp_path, emb)
    ws.set_description("b", "delta new purpose")
    hits = _search(ws, "delta", tmp_path, emb)
    assert hits[0]["kind"] == "bundle" and hits[0]["excerpt"] == "delta new purpose"


@pytest.mark.parametrize("query", ["", "   "])
def test_search_rejects_blank_query_without_embedding(tmp_path, query):
    emb = _SearchEmbedder()
    with pytest.raises(ValueError):
        _search(_workspace(tmp_path), query, tmp_path, emb)
    assert emb.calls == []


@pytest.mark.parametrize("top_k", [0, 21])
def test_search_rejects_top_k_out_of_range(tmp_path, top_k):
    with pytest.raises(ValueError):
        _search(_workspace(tmp_path), "alpha", tmp_path, _SearchEmbedder(), top_k=top_k)


def test_search_rejects_dir_escaping_bundle(tmp_path):
    with pytest.raises(ValueError):
        _search(_workspace(tmp_path), "alpha", tmp_path, _SearchEmbedder(), bundles=["a"], dir="../x")


def test_search_errors_when_embedding_not_configured(tmp_path):
    with pytest.raises(ValueError, match="OKF_EMBEDDING_URL.*OKF_EMBEDDING_MODEL"):
        operations.search_workspace(_workspace(tmp_path), "alpha", config=None, db_path=tmp_path / "v.db")


def test_search_raises_when_embedder_fails(tmp_path):
    def boom(texts):
        raise EmbeddingError("down")

    with pytest.raises(EmbeddingError):
        _search(_workspace(tmp_path), "alpha", tmp_path, boom)


def test_search_default_db_is_in_workspace_metadata(tmp_path):
    ws = _workspace(tmp_path)
    operations.search_workspace(
        ws, "alpha", config=EmbeddingConfig(url="http://h/v1", model="m"), embed=_SearchEmbedder()
    )
    assert (ws.path / ".okf" / "vectors.db").is_file()
    assert ws.indexes() == ["a", "b"]


def test_search_on_non_local_workspace_requires_local_db():
    ws = WorkspaceRegistry(MemoryStorage()).create("w")
    with pytest.raises(VectorStoreError):
        operations.search_workspace(
            ws, "alpha", config=EmbeddingConfig(url="http://h/v1", model="m"), embed=_SearchEmbedder()
        )


def test_search_on_empty_workspace_returns_empty_list(tmp_path):
    ws = WorkspaceRegistry(tmp_path / "ws").create("w")
    assert _search(ws, "alpha", tmp_path, _SearchEmbedder()) == []


def test_create_bundle_is_immediately_browsable_with_description(tmp_path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    assert operations.create_bundle(ws, "n", " d ") == {"bundle": "n", "description": "d"}
    assert operations.read_index(ws.bundle_storage("n")) == []
    assert operations.list_concepts(ws.bundle_storage("n")) == []
    assert ws.description("n") == "d"


def test_create_bundle_without_description(tmp_path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    assert operations.create_bundle(ws, "n") == {"bundle": "n", "description": None}


def test_create_bundle_existing_raises(tmp_path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    operations.create_bundle(ws, "n")
    with pytest.raises(FileExistsError):
        operations.create_bundle(ws, "n")


def test_write_tools_never_touch_embedder_or_vector_file(tmp_path, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("write tool contacted the embedding server")

    monkeypatch.setattr("okf_mcp.embeddings.embed_texts", forbidden)
    root = tmp_path / "bundle"
    root.mkdir()
    fm = {"type": "Table", "title": "Orders", "description": "d"}
    operations.add_concept(root, "tables/orders", fm, "body")
    operations.patch_concept(root, "tables/orders", {"title": "Orders2"}, None)
    operations.move_concept(root, "tables/orders", "models/orders")
    operations.describe_directory(root, "models", "Models")
    operations.reindex_bundle(root)
    operations.delete_concept(root, "models/orders", False)
    assert not (tmp_path / "bundle.vectors.db").exists()


def test_search_after_dimension_change_still_covers_every_bundle(tmp_path):
    ws = _workspace(tmp_path)
    _search(ws, "beta", tmp_path, _SearchEmbedder(), top_k=10)

    class _Wider(_SearchEmbedder):  # same model name, new dimension
        def __call__(self, texts):
            self.calls.append(list(texts))
            return [_search_vec(t) + [0.0] for t in texts]

    ws.bundle_storage("b").write_text("x/_index.md", "beta extra")  # only b changed
    hits = _search(ws, "beta", tmp_path, _Wider(), top_k=10)
    assert {h["bundle"] for h in hits} == {"a", "b"}
