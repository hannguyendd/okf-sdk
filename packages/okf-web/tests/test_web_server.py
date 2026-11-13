import pytest
from starlette.testclient import TestClient

from okf_web.server import build_app, parse_args


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    for key in ("OKF_EMBEDDING_URL", "OKF_EMBEDDING_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)  # keep a stray .env out of Settings
    return tmp_path


def test_serves_workspaces_under_okf_home(home):
    info = TestClient(build_app(parse_args([]))).get("/api/info").json()
    assert info["mode"] == "workspace"
    assert info["location"] == str((home / "workspaces").resolve())


def test_read_only_flag(home):
    info = TestClient(build_app(parse_args(["--read-only"]))).get("/api/info").json()
    assert info["read_only"] is True and info["search_enabled"] is False


def test_search_enabled_when_embedding_env_set(home, monkeypatch):
    monkeypatch.setenv("OKF_EMBEDDING_URL", "http://x/v1")
    monkeypatch.setenv("OKF_EMBEDDING_MODEL", "m")
    assert TestClient(build_app(parse_args([]))).get("/api/info").json()["search_enabled"] is True


def test_root_mode_flags_are_gone():
    for flag in ("--bundle-root", "--project", "--workspaces"):
        with pytest.raises(SystemExit):
            parse_args([flag, "x"] if flag != "--workspaces" else [flag])


def test_static_flag_serves_another_frontend(home, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<p>okf-web2</p>")
    c = TestClient(build_app(parse_args(["--static", str(dist)])))
    assert c.get("/").text == "<p>okf-web2</p>"
    assert c.get("/w/x/y").text == "<p>okf-web2</p>"  # SPA fallback
    assert c.get("/api/info").json()["mode"] == "workspace"


def test_static_flag_requires_a_build(home, tmp_path):
    with pytest.raises(SystemExit, match="no index.html"):
        build_app(parse_args(["--static", str(tmp_path / "missing")]))
