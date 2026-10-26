import pytest

from okf_web.server import build_app, parse_args


def test_no_root_serves_workspaces(tmp_path, monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.delenv("OKF_BUNDLE_ROOT", raising=False)
    monkeypatch.delenv("OKF_STORE_ROOT", raising=False)
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    info = TestClient(build_app(parse_args([]))).get("/api/info").json()
    assert info["mode"] == "workspace"
    assert info["location"] == str(tmp_path / "workspaces")


def test_workspaces_flag_overrides_bundle_root(tmp_path, monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.setenv("OKF_HOME", str(tmp_path / "home"))
    app = build_app(parse_args(["--bundle-root", str(tmp_path), "--workspaces"]))
    assert TestClient(app).get("/api/info").json()["mode"] == "workspace"


def test_bundle_root_flag_and_read_only(tmp_path, monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.delenv("OKF_STORE_ROOT", raising=False)
    app = build_app(parse_args(["--bundle-root", str(tmp_path), "--read-only"]))
    info = TestClient(app).get("/api/info").json()
    assert info["read_only"] is True and info["search_enabled"] is False


def test_store_mode_partitions_by_project(tmp_path, monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.delenv("OKF_BUNDLE_ROOT", raising=False)
    store, project = tmp_path / "store", tmp_path / "proj"
    store.mkdir(), project.mkdir()
    monkeypatch.setenv("OKF_STORE_ROOT", str(store))
    app = build_app(parse_args(["--project", str(project)]))
    loc = TestClient(app).get("/api/info").json()["location"]
    assert loc.startswith(str(store)) and "proj-" in loc


def test_both_roots_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("OKF_STORE_ROOT", str(tmp_path))
    monkeypatch.setenv("OKF_BUNDLE_ROOT", str(tmp_path))
    with pytest.raises(SystemExit):
        build_app(parse_args([]))


def test_search_enabled_when_embedding_env_set(tmp_path, monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.setenv("OKF_EMBEDDING_URL", "http://x/v1")
    monkeypatch.setenv("OKF_EMBEDDING_MODEL", "m")
    app = build_app(parse_args(["--bundle-root", str(tmp_path)]))
    assert TestClient(app).get("/api/info").json()["search_enabled"] is True
