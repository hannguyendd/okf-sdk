"""The local API refuses requests a web page in the user's browser could forge."""

import pytest
from starlette.testclient import TestClient

from okf_core import WorkspaceRegistry
from okf_backend.api import LOOPBACK_HOSTS, create_app
from okf_backend.server import build_app, parse_args

NEW = {"concept_id": "notes/a", "frontmatter": {"type": "note"}, "body": "x"}


@pytest.fixture
def registry(tmp_path):
    reg = WorkspaceRegistry(tmp_path / "workspaces")
    reg.create("w")
    return reg


def local(registry, **kw):
    """A client that talks to the API the way the portal does: from 127.0.0.1:8765."""
    app = create_app(registry, allowed_hosts=LOOPBACK_HOSTS, **kw)
    return TestClient(app, base_url="http://127.0.0.1:8765")


def test_same_origin_json_write_is_allowed(registry):
    c = local(registry)
    r = c.post("/api/workspaces/w/concepts", json=NEW, headers={"origin": "http://127.0.0.1:8765"})
    assert r.status_code == 201


def test_cli_write_without_origin_is_allowed(registry):
    assert local(registry).post("/api/workspaces/w/concepts", json=NEW).status_code == 201


@pytest.mark.parametrize("origin", ["https://evil.example", "http://127.0.0.1:9999", "null"])
def test_cross_origin_write_is_refused(registry, origin):
    c = local(registry)
    r = c.post("/api/workspaces/w/concepts", json=NEW, headers={"origin": origin})
    assert r.status_code == 403
    assert not registry.get("w").storage.exists("notes/a.md")


def test_cross_site_fetch_metadata_is_refused(registry):
    r = local(registry).delete("/api/workspaces/w/concepts/x", headers={"sec-fetch-site": "cross-site"})
    assert r.status_code == 403


def test_simple_form_post_is_refused(registry):
    """A cross-site <form> or fetch(no-cors) can only send text/plain without a preflight."""
    c = local(registry)
    r = c.post(
        "/api/workspaces/w/concepts",
        content=b'{"concept_id": "notes/a", "frontmatter": {"type": "note"}, "body": "x"}',
        headers={"content-type": "text/plain"},
    )
    assert r.status_code == 415
    assert not registry.get("w").storage.exists("notes/a.md")


def test_dns_rebinding_host_is_refused(registry):
    c = TestClient(create_app(registry, allowed_hosts=LOOPBACK_HOSTS), base_url="http://evil.example:8765")
    assert c.get("/api/workspaces").status_code == 403


@pytest.mark.parametrize("host", ["localhost:5173", "127.0.0.1", "[::1]:8765"])
def test_loopback_hosts_are_allowed(registry, host):
    c = TestClient(create_app(registry, allowed_hosts=LOOPBACK_HOSTS))
    assert c.get("/api/workspaces", headers={"host": host}).status_code == 200


def test_vite_dev_proxy_shape_is_allowed(registry):
    """Vite's proxy keeps Host and Origin as the dev server's own (localhost:5173)."""
    c = TestClient(create_app(registry, allowed_hosts=LOOPBACK_HOSTS), base_url="http://localhost:5173")
    r = c.post("/api/workspaces/w/concepts", json=NEW, headers={"origin": "http://localhost:5173"})
    assert r.status_code == 201


def test_server_allows_loopback_and_bind_host(tmp_path, monkeypatch):
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    default = TestClient(build_app(parse_args([])), base_url="http://127.0.0.1:8765")
    assert default.get("/api/info").status_code == 200
    rebinding = TestClient(build_app(parse_args([])), base_url="http://evil.example:8765")
    assert rebinding.get("/api/info").status_code == 403
    lan = TestClient(build_app(parse_args(["--host", "192.168.1.5"])), base_url="http://192.168.1.5:8765")
    assert lan.get("/api/info").status_code == 200
