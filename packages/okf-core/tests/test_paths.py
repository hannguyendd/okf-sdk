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
