from pathlib import Path

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
    assert operations._concept_path(tmp_path, "tables/orders") == tmp_path / "tables" / "orders.md"


def test_concept_path_rejects_reserved(tmp_path):
    with pytest.raises(ValueError):
        operations._concept_path(tmp_path, "tables/index")


def test_concept_path_rejects_bad_segment(tmp_path):
    with pytest.raises(ValueError):
        operations._concept_path(tmp_path, "tables/bad name")


def test_append_log_creates_file(tmp_path):
    log = tmp_path / "log.md"
    operations._append_log(log, "* **Creation**: Added [A](a.md).", "2026-06-29")
    text = log.read_text()
    assert "# Update Log" in text
    assert "## 2026-06-29" in text
    assert "* **Creation**: Added [A](a.md)." in text


def test_append_log_prepends_under_existing_today(tmp_path):
    log = tmp_path / "log.md"
    log.write_text("# Update Log\n\n## 2026-06-29\n* **Creation**: Added [A](a.md).\n")
    operations._append_log(log, "* **Update**: Updated [B](b.md).", "2026-06-29")
    lines = log.read_text().splitlines()
    i = lines.index("## 2026-06-29")
    assert lines[i + 1] == "* **Update**: Updated [B](b.md)."  # newest first
    assert lines[i + 2] == "* **Creation**: Added [A](a.md)."


def test_append_log_inserts_new_today_above_older(tmp_path):
    log = tmp_path / "log.md"
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
        operations.add_concept(tmp_path, "tables/index", {"type": "X"}, "")


def test_add_preserves_caller_timestamp(tmp_path):
    operations.add_concept(
        tmp_path, "a", {"type": "X", "timestamp": "2020-01-01T00:00:00Z"}, ""
    )
    doc = OKFDocument.parse((tmp_path / "a.md").read_text())
    assert doc.frontmatter["timestamp"] == "2020-01-01T00:00:00Z"


def test_add_writes_log_and_index(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    log = tmp_path / "tables" / "log.md"
    assert "Added [Orders](orders.md)" in log.read_text()
    assert (tmp_path / "tables" / "index.md").exists()
    assert (tmp_path / "index.md").exists()


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
    operations.add_concept(tmp_path, "a", {"type": "X", "timestamp": "2020-01-01T00:00:00Z"}, "")
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
    assert "Updated [A2](a.md)" in (tmp_path / "log.md").read_text()


def test_get_returns_doc(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "see [c](customers.md)"
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
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    operations.add_concept(tmp_path, "metrics/mau", {"type": "Metric", "title": "MAU"}, "")
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
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    res = operations.read_index(tmp_path)
    assert len(res) == 1
    assert res[0]["dir"] == ""
    assert res[0]["path"] == "index.md"
    assert "tables" in res[0]["content"]


def test_read_index_depth_two_descends(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
    res = operations.read_index(tmp_path, depth=2)
    dirs = {r["dir"] for r in res}
    assert "" in dirs and "tables" in dirs


def test_read_index_specific_dir(tmp_path):
    operations.add_concept(tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, "")
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
