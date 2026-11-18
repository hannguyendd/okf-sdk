from __future__ import annotations

import json
from pathlib import Path

import pytest

from okf_core import MemoryStorage, regenerate_indexes, validate_bundle
from okf_core.workspace import Workspace, WorkspaceRegistry, okf_home


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


def _json(ws) -> Path:
    return ws.path / ".okf" / "workspace.json"


def test_workspace_on_memory_storage():
    reg = WorkspaceRegistry(root=MemoryStorage())
    ws = reg.create("w")
    assert [w.name for w in reg.list()] == ["w"]
    assert ws.path is None


def test_v1_workspace_json_points_to_migration(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.storage.write_text(".okf/workspace.json", '{"version": 1, "bundles": {}}')
    with pytest.raises(ValueError, match="okf-migrate-v2"):
        ws.color()


@pytest.mark.parametrize("text", ["{not json", '{"version": 3}', "[]"])
def test_corrupt_workspace_json_raises_and_is_not_overwritten(tmp_path: Path, text: str):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.storage.write_text(".okf/workspace.json", text)
    with pytest.raises(ValueError):
        ws.color()
    with pytest.raises(ValueError):
        ws.set_color("pink")
    assert _json(ws).read_text() == text


def test_set_color_writes_v2(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.set_color("pink")
    assert json.loads(ws.storage.read_text(".okf/workspace.json")) == {"version": 2, "color": "pink"}


def test_workspace_root_is_the_bundle_and_ignores_metadata(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.set_color("blue")
    ws.storage.write_text(".okf/vectors.db", "x")
    ws.storage.write_text("notes/a.md", "---\ntype: note\n---\nhi\n")
    assert [c.id for c in ws.load().concepts] == ["notes/a"]
    written = regenerate_indexes(ws.storage)
    assert not any(k.startswith(".okf") for k in written)
    assert validate_bundle(ws.path) == []


def test_bundle_methods_are_gone():
    for gone in (
        "indexes", "create_index", "bundle_storage", "index_root",
        "load_index", "description", "set_description", "bundles_info",
    ):
        assert not hasattr(Workspace, gone)


def test_color_roundtrip_and_clear(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    assert ws.color() is None
    assert ws.set_color(" green ") == "green"
    assert ws.color() == "green"
    assert json.loads(_json(ws).read_text()) == {"version": 2, "color": "green"}
    assert ws.set_color(None) is None
    assert ws.color() is None
    assert "color" not in json.loads(_json(ws).read_text())


@pytest.mark.parametrize("bad", ["#ff0000", "Green", "teal"])
def test_set_color_rejects_unknown(tmp_path: Path, bad: str):
    ws = WorkspaceRegistry(tmp_path).create("w")
    with pytest.raises(ValueError, match="Invalid color"):
        ws.set_color(bad)
    assert json.loads(_json(ws).read_text()) == {"version": 2}


def test_create_writes_v2_marker(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    assert json.loads(_json(ws).read_text()) == {"version": 2}
    assert ws.color() is None


_CONCEPT = "---\ntype: note\ntitle: T\n---\nhi\n"


def _hidden_workspace(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.set_color("pink")
    ws.storage.write_text(".okf/vectors.db", "x")
    ws.storage.write_text(".okf/stray.md", "not a concept")
    ws.storage.write_text(".git/notes.md", "not a concept")
    ws.storage.write_text("notes/.cache/c.md", "not a concept")
    ws.storage.write_text("notes/a.md", _CONCEPT)
    return ws


def test_root_index_never_lists_hidden_dirs(tmp_path: Path):
    ws = _hidden_workspace(tmp_path)
    written = regenerate_indexes(ws.storage)
    assert sorted(written) == ["_index.md", "notes/_index.md"]
    root = ws.storage.read_text("_index.md")
    assert ".okf" not in root and ".git" not in root
    assert ".cache" not in ws.storage.read_text("notes/_index.md")


def test_hidden_md_not_loaded_or_validated(tmp_path: Path):
    ws = _hidden_workspace(tmp_path)
    assert [c.id for c in ws.load().concepts] == ["notes/a"]
    regenerate_indexes(ws.storage)
    assert validate_bundle(ws.path) == []


def test_create_writes_v2_marker_on_memory_storage():
    ws = WorkspaceRegistry(root=MemoryStorage()).create("w")
    assert json.loads(ws.storage.read_text(".okf/workspace.json")) == {"version": 2}
