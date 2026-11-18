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


@pytest.mark.parametrize(
    "key, hidden",
    [
        ("", False),
        ("notes/a.md", False),
        ("_index.md", False),
        ("notes/_log.md", False),
        (".okf", True),
        (".okf/workspace.json", True),
        (".git/x.md", True),
        ("notes/.cache/x.md", True),
        ("notes/.x.md", True),
    ],
)
def test_is_hidden(key: str, hidden: bool):
    from okf_core.paths import is_hidden

    assert is_hidden(key) is hidden


def test_iter_visible_files_prunes_hidden():
    from okf_core import MemoryStorage
    from okf_core.paths import iter_visible_files

    s = MemoryStorage()
    for k in ("a.md", ".okf/x.md", ".git/y.md", "n/b.md", "n/.c/z.md", "n/.d.md", "n/t.txt"):
        s.write_text(k, "x")
    assert list(iter_visible_files(s, suffix=".md")) == ["a.md", "n/b.md"]
    assert list(iter_visible_files(s, "n")) == ["n/b.md", "n/t.txt"]
