import asyncio
from types import SimpleNamespace

import pytest

from okf_core import WorkspaceRegistry

from okf_mcp import operations, server
from okf_mcp.server import Settings, mcp

_ENV = (
    "OKF_WORKSPACE",
    "OKF_BUNDLE",
    "OKF_EMBEDDING_URL",
    "OKF_EMBEDDING_MODEL",
    "OKF_EMBEDDING_API_KEY",
    "OKF_EMBEDDING_MAX_CHARS",
)


class _Session:
    def check_client_capability(self, capability) -> bool:
        return False  # no elicitation: ambiguity becomes an error


def _ctx(headers=None):
    request = SimpleNamespace(headers=headers) if headers is not None else None
    return SimpleNamespace(session=_Session(), request_context=SimpleNamespace(request=request))


@pytest.fixture
def home(tmp_path, monkeypatch):
    """OKF_HOME at tmp_path with workspace ``w`` holding bundles ``b`` and ``c``."""
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    for key in _ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(server, "settings", Settings(_env_file=None))
    ws = WorkspaceRegistry(tmp_path / "workspaces").create("w")
    ws.create_index("b", "Billing data")
    ws.create_index("c")
    return tmp_path


def _use_settings(monkeypatch, **env):
    for key, val in env.items():
        monkeypatch.setenv(key, str(val))
    monkeypatch.setattr(server, "settings", Settings(_env_file=None))


def run(coro):
    return asyncio.run(coro)


def test_all_tools_registered():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert {
        "add", "patch", "get", "list", "read_index", "move", "reindex", "delete",
        "describe", "search", "list_workspaces", "list_bundles", "create_bundle",
        "describe_bundle",
    } <= names
    assert not any("bundle_root" in t.inputSchema.get("properties", {}) for t in tools)
    assert "create_workspace" not in names


def test_tool_schema_excludes_ctx():
    add_tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "add")
    assert "ctx" not in add_tool.inputSchema.get("properties", {})


def test_settings_read_workspace_and_bundle_env(monkeypatch):
    monkeypatch.setenv("OKF_WORKSPACE", "w")
    monkeypatch.setenv("OKF_BUNDLE", "b")
    s = Settings(_env_file=None)
    assert (s.workspace, s.bundle) == ("w", "b")


def test_settings_read_embedding_env_vars(monkeypatch):
    for key in _ENV:
        monkeypatch.delenv(key, raising=False)
    defaults = Settings(_env_file=None)
    assert (defaults.embedding_url, defaults.embedding_model, defaults.embedding_api_key) == (None, None, None)
    assert defaults.embedding_max_chars == 6000
    monkeypatch.setenv("OKF_EMBEDDING_URL", "http://h/v1")
    monkeypatch.setenv("OKF_EMBEDDING_MODEL", "m")
    monkeypatch.setenv("OKF_EMBEDDING_API_KEY", "k")
    monkeypatch.setenv("OKF_EMBEDDING_MAX_CHARS", "1234")
    s = Settings(_env_file=None)
    assert (s.embedding_url, s.embedding_model, s.embedding_api_key, s.embedding_max_chars) == (
        "http://h/v1", "m", "k", 1234,
    )


def test_add_echoes_target_and_writes_into_bundle(home):
    out = run(server.add(_ctx(), "t/x", {"type": "Note", "title": "X"}, "body", workspace="w", bundle="b"))
    assert (out["workspace"], out["bundle"]) == ("w", "b")
    assert (home / "workspaces" / "w" / "b" / "t" / "x.md").is_file()
    got = run(server.get(_ctx(), "t/x", workspace="w", bundle="b"))
    assert got["frontmatter"]["title"] == "X" and got["bundle"] == "b"


def test_concept_tools_use_header_then_env_defaults(home, monkeypatch):
    _use_settings(monkeypatch, OKF_WORKSPACE="w", OKF_BUNDLE="c")
    out = run(server.add(_ctx(), "x", {"type": "Note", "title": "X"}, "", ))
    assert out["bundle"] == "c"
    out = run(server.add(_ctx({"x-okf-bundle": "b"}), "y", {"type": "Note", "title": "Y"}, ""))
    assert out["bundle"] == "b"


def test_ambiguous_bundle_without_elicitation_lists_choices(home):
    with pytest.raises(ValueError, match="bundle=.*b, c"):
        run(server.list_(_ctx(), workspace="w"))


def test_list_and_read_index_wrap_items(home):
    run(server.add(_ctx(), "t/x", {"type": "Note", "title": "X"}, "", workspace="w", bundle="b"))
    listed = run(server.list_(_ctx(), workspace="w", bundle="b"))
    assert (listed["workspace"], listed["bundle"]) == ("w", "b")
    assert [c["id"] for c in listed["items"]] == ["t/x"]
    idx = run(server.read_index(_ctx(), workspace="w", bundle="b"))
    assert idx["bundle"] == "b" and idx["items"][0]["dir"] == ""


def test_other_concept_tools_echo_target(home):
    t = {"workspace": "w", "bundle": "b"}
    run(server.add(_ctx(), "t/x", {"type": "Note", "title": "X"}, "", **t))
    for out in (
        run(server.patch(_ctx(), "t/x", {"title": "X2"}, None, **t)),
        run(server.describe(_ctx(), "t", "Things", **t)),
        run(server.move(_ctx(), "t/x", "u/x", **t)),
        run(server.reindex(_ctx(), **t)),
        run(server.delete(_ctx(), "u/x", **t)),
    ):
        assert (out["workspace"], out["bundle"]) == ("w", "b")


def test_list_workspaces_counts_bundles(home):
    WorkspaceRegistry(home / "workspaces").create("empty")
    assert run(server.list_workspaces()) == [
        {"name": "empty", "bundles": 0},
        {"name": "w", "bundles": 2},
    ]


def test_list_bundles_includes_descriptions(home):
    assert run(server.list_bundles(_ctx(), workspace="w")) == {
        "workspace": "w",
        "bundles": [
            {"name": "b", "description": "Billing data"},
            {"name": "c", "description": None},
        ],
    }


def test_list_bundles_single_workspace_needs_no_argument(home):
    assert run(server.list_bundles(_ctx()))["workspace"] == "w"


def test_create_bundle_and_describe_bundle(home):
    assert run(server.create_bundle(_ctx(), "n", "New one", workspace="w")) == {
        "workspace": "w", "bundle": "n", "description": "New one",
    }
    assert run(server.describe_bundle(_ctx(), "Changed", bundle="n", workspace="w")) == {
        "workspace": "w", "bundle": "n", "description": "Changed",
    }
    assert run(server.describe_bundle(_ctx(), None, bundle="n", workspace="w"))["description"] is None
    with pytest.raises(FileExistsError):
        run(server.create_bundle(_ctx(), "n", workspace="w"))


def _capture_search(monkeypatch):
    seen = {}

    def fake(workspace, query, top_k, bundles, dir, **kw):
        seen.update(workspace=workspace.name, query=query, top_k=top_k, bundles=bundles, dir=dir, **kw)
        return [{"bundle": "b", "path": "x/_index.md"}]

    monkeypatch.setattr(operations, "search_workspace", fake)
    return seen


def test_search_scope_default_bundle_vs_all_vs_filter(home, monkeypatch):
    _use_settings(monkeypatch, OKF_EMBEDDING_URL="http://h/v1", OKF_EMBEDDING_MODEL="m", OKF_EMBEDDING_MAX_CHARS=500)
    seen = _capture_search(monkeypatch)

    out = run(server.search(_ctx(), "q", workspace="w"))
    assert out == {"workspace": "w", "bundles": ["b", "c"], "hits": [{"bundle": "b", "path": "x/_index.md"}]}
    assert seen["bundles"] == ["b", "c"] and seen["max_chars"] == 500
    assert (seen["config"].url, seen["config"].model) == ("http://h/v1", "m")

    run(server.search(_ctx(), "q", bundles=["c"], top_k=3, dir="d", workspace="w"))
    assert (seen["bundles"], seen["top_k"], seen["dir"]) == (["c"], 3, "d")

    _use_settings(monkeypatch, OKF_WORKSPACE="w", OKF_BUNDLE="b")
    out = run(server.search(_ctx(), "q"))
    assert out["bundles"] == ["b"] and seen["bundles"] == ["b"]


def test_search_without_embedding_settings_errors_but_other_tools_work(home):
    with pytest.raises(ValueError, match="OKF_EMBEDDING_URL"):
        run(server.search(_ctx(), "anything", workspace="w"))
    assert run(server.list_(_ctx(), workspace="w", bundle="b"))["items"] == []


def test_main_parses_transport_and_port(monkeypatch):
    seen = {}
    monkeypatch.setattr(mcp, "run", lambda transport="stdio", **kw: seen.update(transport=transport))
    server.main(["--transport", "streamable-http", "--port", "9000"])
    assert seen["transport"] == "streamable-http"
    assert (mcp.settings.host, mcp.settings.port) == ("127.0.0.1", 9000)
    server.main([])
    assert seen["transport"] == "stdio"
