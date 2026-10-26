from __future__ import annotations

import json
from pathlib import Path

import pytest

from okf_core import Bundle, MemoryStorage
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
    storage = ws.create_index("docs")
    p = ws.path / "docs"
    assert storage.location == str(p) and p.is_dir()
    assert ws.index_root("docs") == p
    assert ws.bundle_storage("docs").location == str(p)
    with pytest.raises(FileNotFoundError):
        ws.bundle_storage("missing")
    with pytest.raises(FileExistsError):
        ws.create_index("docs")
    with pytest.raises(FileNotFoundError):
        ws.index_root("missing")


def test_load_index_returns_bundle(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.create_index("docs")
    (ws.path / "docs" / "a.md").write_text("---\ntype: Note\ntitle: A\n---\nbody\n")
    bundle = ws.load_index("docs")
    assert isinstance(bundle, Bundle)
    assert "a" in bundle


def _json(ws) -> Path:
    return ws.path / ".okf" / "workspace.json"


def test_description_roundtrip_writes_json(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.create_index("notes", description="  Team notes  ")
    assert ws.description("notes") == "Team notes"
    assert json.loads(_json(ws).read_text()) == {
        "version": 1,
        "bundles": {"notes": {"description": "Team notes"}},
    }
    assert _json(ws).read_text().endswith("\n")


def test_metadata_dir_is_not_an_index(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.create_index("a", description="x")
    assert (ws.path / ".okf").is_dir()
    assert ws.indexes() == ["a"]


@pytest.mark.parametrize("cleared", ["  ", "", None])
def test_set_description_blank_or_none_clears(tmp_path: Path, cleared):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.create_index("a", description="x")
    assert ws.set_description("a", cleared) is None
    assert ws.description("a") is None


def test_set_description_too_long_raises(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.create_index("a")
    with pytest.raises(ValueError):
        ws.set_description("a", "x" * 1001)
    assert ws.set_description("a", "x" * 1000) == "x" * 1000


def test_set_description_unknown_bundle_raises(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    with pytest.raises(FileNotFoundError):
        ws.set_description("missing", "x")


def test_hand_made_bundle_has_null_description_and_can_be_described(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    (ws.path / "manual").mkdir()
    assert ws.bundles_info() == [{"name": "manual", "description": None}]
    ws.set_description("manual", "Hand made")
    assert ws.bundles_info() == [{"name": "manual", "description": "Hand made"}]


def test_stale_entry_hidden_and_pruned_on_write(tmp_path: Path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.create_index("a")
    _json(ws).parent.mkdir()
    _json(ws).write_text(json.dumps(
        {"version": 1, "bundles": {"gone": {"description": "old"}, "a": {"description": None}}}
    ))
    assert ws.bundles_info() == [{"name": "a", "description": None}]
    ws.set_description("a", "kept")
    assert set(json.loads(_json(ws).read_text())["bundles"]) == {"a"}


@pytest.mark.parametrize(
    "text",
    ["{not json", '{"version": 2, "bundles": {}}', '{"version": 1, "bundles": []}', "[]"],
)
def test_corrupt_workspace_json_raises_and_is_not_overwritten(tmp_path: Path, text: str):
    ws = WorkspaceRegistry(tmp_path).create("w")
    ws.create_index("a")
    _json(ws).parent.mkdir()
    _json(ws).write_text(text)
    with pytest.raises(ValueError):
        ws.description("a")
    with pytest.raises(ValueError):
        ws.set_description("a", "x")
    assert _json(ws).read_text() == text


def test_workspace_on_memory_storage():
    reg = WorkspaceRegistry(root=MemoryStorage())
    ws = reg.create("w")
    ws.create_index("b", "d")
    assert [w.name for w in reg.list()] == ["w"]
    assert ws.bundles_info() == [{"name": "b", "description": "d"}]
    assert ws.path is None
