from pathlib import Path
import asyncio
from types import SimpleNamespace

import pytest
from mcp import types as mcp_types

from okf_mcp import operations, server
from okf_mcp.server import Settings, mcp


class _FakeSession:
    """Stand-in for the MCP ServerSession's ``list_roots``.

    ``root_paths=None`` simulates a client without the roots capability (raises);
    a list yields ``file://`` roots for those paths.
    """

    def __init__(self, root_paths):
        self._root_paths = root_paths

    async def list_roots(self):
        if self._root_paths is None:
            raise RuntimeError("client has no roots capability")
        return mcp_types.ListRootsResult(
            roots=[
                mcp_types.Root(uri=f"file://{p}", name=None) for p in self._root_paths
            ]
        )


def _ctx(root_paths):
    return SimpleNamespace(session=_FakeSession(root_paths))


def _use_settings(monkeypatch, **env):
    """Install a fresh Settings on the server module built only from ``env``."""
    for key in ("OKF_STORE_ROOT", "OKF_BUNDLE_ROOT"):
        monkeypatch.delenv(key, raising=False)
    for key, val in env.items():
        monkeypatch.setenv(key, str(val))
    fresh = Settings(_env_file=None)
    monkeypatch.setattr(server, "settings", fresh)
    return fresh


def test_all_tools_registered():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {
        "add",
        "patch",
        "get",
        "list",
        "read_index",
        "move",
        "reindex",
        "delete",
        "describe",
    } <= names


def test_tool_schema_excludes_ctx():
    add_tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "add")
    assert "ctx" not in add_tool.inputSchema.get("properties", {})


def test_settings_reads_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("OKF_BUNDLE_ROOT", raising=False)
    target = tmp_path / "bundle"
    target.mkdir()
    (tmp_path / ".env").write_text(f"OKF_BUNDLE_ROOT={target}\n")
    monkeypatch.chdir(tmp_path)
    assert Path(Settings().bundle_root) == target


def test_settings_reads_store_root(tmp_path, monkeypatch):
    monkeypatch.delenv("OKF_BUNDLE_ROOT", raising=False)
    monkeypatch.setenv("OKF_STORE_ROOT", str(tmp_path))
    assert Path(Settings(_env_file=None).store_root) == tmp_path


def test_root_prefers_explicit_arg(tmp_path, monkeypatch):
    _use_settings(monkeypatch, OKF_STORE_ROOT=tmp_path, OKF_BUNDLE_ROOT=tmp_path)
    target = tmp_path / "explicit"
    target.mkdir()
    got = asyncio.run(server._root(str(target), _ctx(["/whatever"])))
    assert got == target.resolve()


def test_root_errors_when_both_env_set(tmp_path, monkeypatch):
    _use_settings(monkeypatch, OKF_STORE_ROOT=tmp_path, OKF_BUNDLE_ROOT=tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(server._root(None, _ctx(["/whatever"])))


def test_root_store_mode_uses_derived_folder(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    project = tmp_path / "proj" / "web-app"
    _use_settings(monkeypatch, OKF_STORE_ROOT=store)
    got = asyncio.run(server._root(None, _ctx([str(project)])))
    assert got == store.resolve() / operations.derive_project_folder(project)
    assert got.is_dir()


def test_root_store_mode_falls_back_to_cwd(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    monkeypatch.chdir(tmp_path)
    _use_settings(monkeypatch, OKF_STORE_ROOT=store)
    got = asyncio.run(server._root(None, _ctx(None)))
    assert got == store.resolve() / operations.derive_project_folder(tmp_path)


def test_root_legacy_bundle_mode(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _use_settings(monkeypatch, OKF_BUNDLE_ROOT=bundle)
    got = asyncio.run(server._root(None, _ctx(None)))
    assert got == bundle.resolve()


def test_root_errors_when_nothing_configured(monkeypatch):
    _use_settings(monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(server._root(None, _ctx(None)))
