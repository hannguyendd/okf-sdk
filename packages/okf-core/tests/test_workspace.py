from __future__ import annotations

from pathlib import Path

import pytest

from okf_core import Bundle
from okf_core.workspace import WorkspaceRegistry, okf_home


def test_okf_home_explicit_wins(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OKF_HOME", str(tmp_path / "env"))
    assert okf_home(tmp_path / "arg") == tmp_path / "arg"


def test_okf_home_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OKF_HOME", str(tmp_path / "env"))
    assert okf_home() == tmp_path / "env"


def test_okf_home_default_is_dot_okf_in_home(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OKF_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert okf_home() == tmp_path / ".okf"
    assert not (tmp_path / ".okf").exists()  # pure


def test_registry_default_root_under_okf_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OKF_HOME", str(tmp_path / "okf"))
    assert WorkspaceRegistry().root == tmp_path / "okf" / "workspaces"


def test_create_makes_parents_and_returns_workspace(tmp_path: Path):
    reg = WorkspaceRegistry(tmp_path / "okf" / "workspaces")
    ws = reg.create("team")
    assert ws.name == "team"
    assert ws.path == tmp_path / "okf" / "workspaces" / "team"
    assert ws.path.is_dir()


def test_create_duplicate_raises(tmp_path: Path):
    reg = WorkspaceRegistry(tmp_path)
    reg.create("a")
    with pytest.raises(FileExistsError):
        reg.create("a")


def test_list_sorted_and_empty_when_missing(tmp_path: Path):
    reg = WorkspaceRegistry(tmp_path / "nope")
    assert reg.list() == []
    reg = WorkspaceRegistry(tmp_path)
    reg.create("b")
    reg.create("a")
    (tmp_path / "stray.txt").write_text("x")
    assert [w.name for w in reg.list()] == ["a", "b"]


def test_get_and_exists(tmp_path: Path):
    reg = WorkspaceRegistry(tmp_path)
    reg.create("a")
    assert reg.exists("a") and not reg.exists("b")
    assert reg.get("a").path == tmp_path / "a"
    with pytest.raises(FileNotFoundError):
        reg.get("b")


@pytest.mark.parametrize("bad", ["", "..", ".hidden", "_x", "a/b", "a\\b", "-x", "a b"])
def test_invalid_names_rejected(tmp_path: Path, bad: str):
    reg = WorkspaceRegistry(tmp_path)
    with pytest.raises(ValueError):
        reg.create(bad)
    with pytest.raises(ValueError):
        reg.get(bad)
    ws = reg.create("ok")
    with pytest.raises(ValueError):
        ws.create_index(bad)
    with pytest.raises(ValueError):
        ws.index_root(bad)


def test_indexes_are_visible_top_level_dirs(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.create_index("zeta")
    ws.create_index("alpha")
    (ws.path / ".git").mkdir()
    (ws.path / "_meta").mkdir()
    (ws.path / "README.md").write_text("x")
    assert ws.indexes() == ["alpha", "zeta"]


def test_create_index_and_resolve(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    p = ws.create_index("docs")
    assert p == ws.path / "docs" and p.is_dir()
    assert ws.index_root("docs") == p
    with pytest.raises(FileExistsError):
        ws.create_index("docs")
    with pytest.raises(FileNotFoundError):
        ws.index_root("missing")


def test_load_index_returns_bundle(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    root = ws.create_index("docs")
    (root / "a.md").write_text("---\ntype: Note\ntitle: A\n---\nbody\n")
    bundle = ws.load_index("docs")
    assert isinstance(bundle, Bundle)
    assert "a" in bundle
