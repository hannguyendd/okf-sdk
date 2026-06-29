from pathlib import Path

import pytest

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
