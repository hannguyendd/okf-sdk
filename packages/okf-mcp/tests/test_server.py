import asyncio
from types import SimpleNamespace

import pytest

from okf_backend import operations
from okf_backend.settings import BackendSettings
from okf_core import WorkspaceRegistry
from okf_mcp import server
from okf_mcp.server import mcp

_ENV = (
    "OKF_EMBEDDING_URL",
    "OKF_EMBEDDING_MODEL",
    "OKF_EMBEDDING_API_KEY",
    "OKF_EMBEDDING_MAX_CHARS",
)


def _ctx(headers=None):
    request = SimpleNamespace(headers=headers) if headers is not None else None
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


@pytest.fixture
def home(tmp_path, monkeypatch):
    """OKF_HOME at tmp_path with workspace ``w`` (no fixed workspace)."""
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    for key in _ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(server, "_fixed_workspace", None)
    WorkspaceRegistry(tmp_path / "workspaces").create("w")
    return tmp_path


def run(coro):
    return asyncio.run(coro)


H = {"x-okf-workspace": "w"}


def test_tool_set():
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == {
        "add", "patch", "get", "list", "read_index", "move", "delete",
        "reindex", "describe", "mkdir", "search",
    }
    for t in tools:
        props = t.inputSchema.get("properties", {})
        assert "workspace" not in props and "bundle" not in props
        assert "ctx" not in props


def test_header_selects_workspace(home):
    out = run(server.add(_ctx(H), "notes/a", {"type": "note"}, "x"))
    assert out["workspace"] == "w"
    assert (home / "workspaces" / "w" / "notes" / "a.md").is_file()
    assert run(server.get(_ctx(H), "notes/a"))["frontmatter"]["type"] == "note"


@pytest.mark.parametrize("hdr", ["../etc", "nope"])
def test_bad_header_fails_and_lists(home, hdr):
    with pytest.raises(ValueError, match="workspaces: w"):
        run(server.list_(_ctx({"x-okf-workspace": hdr})))


def test_missing_workspace_fails_and_lists(home):
    with pytest.raises(ValueError, match="no workspace.*workspaces: w"):
        run(server.list_(_ctx()))
    with pytest.raises(ValueError, match="no workspace"):
        run(server.list_(_ctx({"x-okf-workspace": ""})))


def test_fixed_workspace_wins_on_stdio(home, monkeypatch):
    monkeypatch.setattr(server, "_fixed_workspace", "w")
    assert run(server.list_(_ctx()))["workspace"] == "w"


def test_list_and_read_index_wrap_items(home):
    run(server.add(_ctx(H), "t/x", {"type": "Note", "title": "X"}, ""))
    listed = run(server.list_(_ctx(H)))
    assert listed["workspace"] == "w"
    assert [c["id"] for c in listed["items"]] == ["t/x"]
    idx = run(server.read_index(_ctx(H)))
    assert idx["workspace"] == "w" and idx["items"][0]["dir"] == ""


def test_other_tools_echo_workspace(home):
    run(server.add(_ctx(H), "t/x", {"type": "Note", "title": "X"}, ""))
    for out in (
        run(server.patch(_ctx(H), "t/x", {"title": "X2"}, None)),
        run(server.describe(_ctx(H), "t", "Things")),
        run(server.move(_ctx(H), "t/x", "u/x")),
        run(server.reindex(_ctx(H))),
        run(server.delete(_ctx(H), "u/x")),
    ):
        assert out["workspace"] == "w"


def test_mkdir_creates_directory(home):
    out = run(server.mkdir(_ctx(H), "newdir", "A place"))
    assert out["workspace"] == "w"
    idx = run(server.read_index(_ctx(H), "newdir"))
    assert idx["items"][0]["dir"] == "newdir"


def _capture_search(monkeypatch):
    seen = {}

    def fake(workspace, query, top_k, paths, **kw):
        seen.update(workspace=workspace.name, query=query, top_k=top_k, paths=paths, **kw)
        return [{"kind": "index", "dir": "a", "path": "a/_index.md"}]

    monkeypatch.setattr(operations, "search_workspace", fake)
    return seen


def test_search_passes_paths(home, monkeypatch):
    monkeypatch.setenv("OKF_EMBEDDING_URL", "http://h/v1")
    monkeypatch.setenv("OKF_EMBEDDING_MODEL", "m")
    monkeypatch.setenv("OKF_EMBEDDING_MAX_CHARS", "500")
    seen = _capture_search(monkeypatch)
    out = run(server.search(_ctx(H), "q", top_k=3, paths=["a"]))
    assert out["workspace"] == "w" and out["hits"][0]["dir"] == "a"
    assert seen["paths"] == ["a"] and seen["top_k"] == 3 and seen["max_chars"] == 500
    assert (seen["config"].url, seen["config"].model) == ("http://h/v1", "m")


def test_search_without_embedding_settings_errors_but_other_tools_work(home, tmp_path, monkeypatch):
    # Keep the repo's own .env and the developer's shell out of this test.
    monkeypatch.chdir(tmp_path)
    for key in ("OKF_EMBEDDING_URL", "OKF_EMBEDDING_MODEL"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="OKF_EMBEDDING_URL"):
        run(server.search(_ctx(H), "anything"))
    assert run(server.list_(_ctx(H)))["items"] == []


def test_settings_is_backend_settings():
    assert not hasattr(server, "Settings")
    assert BackendSettings(_env_file=None).embedding_max_chars == 6000


def test_main_requires_workspace_for_stdio(home, monkeypatch):
    seen = {}
    monkeypatch.setattr(mcp, "run", lambda transport="stdio", **kw: seen.update(transport=transport))
    with pytest.raises(SystemExit, match="--workspace is required.*workspaces: w"):
        server.main([])
    with pytest.raises(SystemExit, match="not used with streamable-http"):
        server.main(["--transport", "streamable-http", "--workspace", "w"])
    with pytest.raises(SystemExit, match="workspaces: w"):
        server.main(["--workspace", "nope"])
    server.main(["--workspace", "w"])
    assert seen["transport"] == "stdio" and server._fixed_workspace == "w"


def _make_v1(home, name="old"):
    d = home / "workspaces" / name / ".okf"
    d.mkdir(parents=True)
    (d / "workspace.json").write_text('{"version": 1, "bundles": {}}')


def test_v1_workspace_refused_by_tools(home, monkeypatch):
    _make_v1(home)
    with pytest.raises(ValueError, match="okf-migrate-v2"):
        run(server.list_(_ctx({"x-okf-workspace": "old"})))
    with pytest.raises(ValueError, match="okf-migrate-v2"):
        run(server.add(_ctx({"x-okf-workspace": "old"}), "n/a", {"type": "note"}, "x"))
    assert not (home / "workspaces" / "old" / "n").exists()
    monkeypatch.setattr(server, "_fixed_workspace", "old")
    with pytest.raises(ValueError, match="okf-migrate-v2"):
        run(server.list_(_ctx()))


def test_main_stdio_exits_for_v1_workspace(home, monkeypatch):
    _make_v1(home)
    monkeypatch.setattr(mcp, "run", lambda **kw: pytest.fail("must not start"))
    with pytest.raises(SystemExit, match="okf-migrate-v2"):
        server.main(["--workspace", "old"])


def test_main_http_port(home, monkeypatch):
    seen = {}
    monkeypatch.setattr(mcp, "run", lambda transport="stdio", **kw: seen.update(transport=transport))
    server.main(["--transport", "streamable-http", "--port", "9000"])
    assert seen["transport"] == "streamable-http"
    assert (mcp.settings.host, mcp.settings.port) == ("127.0.0.1", 9000)
