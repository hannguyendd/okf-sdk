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
        "search",
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


_EMBED_ENV = (
    "OKF_EMBEDDING_URL",
    "OKF_EMBEDDING_MODEL",
    "OKF_EMBEDDING_API_KEY",
    "OKF_EMBEDDING_MAX_CHARS",
    "OKF_VECTOR_DB",
)


def _clear_embed_env(monkeypatch):
    for key in _EMBED_ENV:
        monkeypatch.delenv(key, raising=False)


def test_settings_read_embedding_env_vars(tmp_path, monkeypatch):
    _clear_embed_env(monkeypatch)
    defaults = Settings(_env_file=None)
    assert defaults.embedding_url is None
    assert defaults.embedding_model is None
    assert defaults.embedding_api_key is None
    assert defaults.vector_db is None
    assert defaults.embedding_max_chars == 6000

    monkeypatch.setenv("OKF_EMBEDDING_URL", "http://h/v1")
    monkeypatch.setenv("OKF_EMBEDDING_MODEL", "m")
    monkeypatch.setenv("OKF_EMBEDDING_API_KEY", "k")
    monkeypatch.setenv("OKF_EMBEDDING_MAX_CHARS", "1234")
    monkeypatch.setenv("OKF_VECTOR_DB", str(tmp_path / "v.db"))
    s = Settings(_env_file=None)
    assert (s.embedding_url, s.embedding_model, s.embedding_api_key) == (
        "http://h/v1",
        "m",
        "k",
    )
    assert s.embedding_max_chars == 1234
    assert s.vector_db == str(tmp_path / "v.db")


def test_search_tool_passes_settings_and_root_to_operation(tmp_path, monkeypatch):
    _clear_embed_env(monkeypatch)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _use_settings(
        monkeypatch,
        OKF_BUNDLE_ROOT=bundle,
        OKF_EMBEDDING_URL="http://h/v1",
        OKF_EMBEDDING_MODEL="m",
        OKF_EMBEDDING_API_KEY="k",
        OKF_EMBEDDING_MAX_CHARS=500,
        OKF_VECTOR_DB=tmp_path / "v.db",
    )
    seen = {}

    def fake(root, query, top_k, dir, **kw):
        seen.update(root=root, query=query, top_k=top_k, dir=dir, **kw)
        return [{"path": "x/_index.md"}]

    monkeypatch.setattr(operations, "search_indexes", fake)
    out = asyncio.run(server.search(_ctx(None), "find me", top_k=3, dir="x"))

    assert out == [{"path": "x/_index.md"}]
    assert seen["root"] == bundle.resolve()
    assert (seen["query"], seen["top_k"], seen["dir"]) == ("find me", 3, "x")
    cfg = seen["config"]
    assert (cfg.url, cfg.model, cfg.api_key) == ("http://h/v1", "m", "k")
    assert seen["max_chars"] == 500
    assert seen["db_path"] == str(tmp_path / "v.db")


def test_search_tool_without_embedding_settings_errors_but_other_tools_work(
    tmp_path, monkeypatch
):
    _clear_embed_env(monkeypatch)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _use_settings(monkeypatch, OKF_BUNDLE_ROOT=bundle)
    with pytest.raises(ValueError, match="OKF_EMBEDDING_URL"):
        asyncio.run(server.search(_ctx(None), "anything"))
    assert asyncio.run(server.list_(_ctx(None))) == []
