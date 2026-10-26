import pytest
from starlette.testclient import TestClient

from okf_core import WorkspaceRegistry
from okf_web.server import build_app, parse_args


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    for key in ("OKF_WORKSPACE", "OKF_BUNDLE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)  # keep a stray .env out of Settings
    return WorkspaceRegistry(tmp_path / "workspaces")


def _info(app):
    return TestClient(app).get("/api/info").json()


def test_no_workspace_exits(home):
    with pytest.raises(SystemExit, match="no workspaces"):
        build_app(parse_args([]))


def test_single_workspace_and_bundle_auto_selected(home):
    home.create("w").create_index("b")
    info = _info(build_app(parse_args([])))
    assert (info["workspace"], info["bundle"]) == ("w", "b")


def test_flags_select_target_and_read_only(home):
    for name in ("w", "v"):
        ws = home.create(name)
        ws.create_index("a")
        ws.create_index("b")
    info = _info(build_app(parse_args(["--workspace", "v", "--bundle", "b", "--read-only"])))
    assert (info["workspace"], info["bundle"], info["read_only"]) == ("v", "b", True)
    assert info["search_enabled"] is False


def test_env_selects_target(home, monkeypatch):
    ws = home.create("w")
    ws.create_index("a")
    ws.create_index("b", "Bee")
    monkeypatch.setenv("OKF_WORKSPACE", "w")
    monkeypatch.setenv("OKF_BUNDLE", "b")
    info = _info(build_app(parse_args([])))
    assert (info["workspace"], info["bundle"], info["description"]) == ("w", "b", "Bee")


def test_ambiguous_bundle_exits_listing_choices(home):
    ws = home.create("w")
    ws.create_index("a")
    ws.create_index("b")
    with pytest.raises(SystemExit, match="a, b"):
        build_app(parse_args([]))


def test_missing_named_bundle_exits(home):
    home.create("w").create_index("a")
    with pytest.raises(SystemExit, match="no bundle 'zz'"):
        build_app(parse_args(["--bundle", "zz"]))
