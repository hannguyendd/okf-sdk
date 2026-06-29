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
