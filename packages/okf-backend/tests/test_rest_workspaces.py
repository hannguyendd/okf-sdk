import pytest
from starlette.testclient import TestClient

from okf_core import WorkspaceRegistry
from okf_backend.api import create_app


@pytest.fixture
def registry(tmp_path):
    reg = WorkspaceRegistry(tmp_path / "workspaces")
    reg.create("work")
    reg.create("empty")
    return reg


def client(registry, **kw):
    return TestClient(create_app(registry=registry, **kw))


def test_info_reports_workspace_mode(registry):
    info = client(registry).get("/api/info").json()
    assert info["mode"] == "workspace"
    assert info["location"] == registry.storage.location


def test_list_workspaces_has_no_indexes(registry):
    r = client(registry).get("/api/workspaces").json()
    assert r == [
        {"name": "empty", "color": None},
        {"name": "work", "color": None},
    ]


def test_create_workspace(registry):
    c = client(registry)
    r = c.post("/api/workspaces", json={"name": "new"})
    assert r.status_code == 201 and r.json() == {"name": "new", "color": None}
    assert c.post("/api/workspaces", json={"name": "new"}).status_code == 400  # exists
    assert c.post("/api/workspaces", json={"name": "../x"}).status_code == 400
    assert {"name": "new", "color": None} in c.get("/api/workspaces").json()


def test_set_workspace_color(registry):
    c = client(registry)
    r = c.post("/api/workspaces/work/color", json={"color": "pink"})
    assert r.status_code == 200 and r.json() == {"name": "work", "color": "pink"}
    assert next(w for w in c.get("/api/workspaces").json() if w["name"] == "work")["color"] == "pink"
    assert c.post("/api/workspaces/work/color", json={"color": "#ff0000"}).status_code == 400
    assert c.post("/api/workspaces/nope/color", json={"color": "pink"}).status_code == 404
    assert c.post("/api/workspaces/work/color", json={"color": None}).json() == {"name": "work", "color": None}
    assert client(registry, read_only=True).post("/api/workspaces/work/color", json={"color": "red"}).status_code == 403


BASE = "/api/workspaces/work"


def test_concept_crud_at_workspace_root(registry):
    c = client(registry)
    r = c.post(f"{BASE}/concepts", json={"concept_id": "notes/a", "frontmatter": {"type": "note", "title": "A"}, "body": "x"})
    assert r.status_code == 201
    assert (registry.get("work").path / "notes" / "a.md").is_file()
    assert c.get(f"{BASE}/concepts/notes/a").json()["id"] == "notes/a"
    assert [d["name"] for d in c.get(f"{BASE}/tree").json()["directories"]] == ["notes"]
    # another workspace is isolated
    assert c.get("/api/workspaces/empty/tree").json()["directories"] == []
    assert c.post(f"{BASE}/reindex").json()["action"] == "reindexed"
    assert c.get(f"{BASE}/indexes/b/tree").status_code == 404


def test_unknown_workspace_is_404(registry):
    assert client(registry).get("/api/workspaces/zzz/tree").status_code == 404


def test_read_only_blocks_workspace_writes(registry):
    c = client(registry, read_only=True)
    assert c.post("/api/workspaces", json={"name": "n"}).status_code == 403
    assert c.post(f"{BASE}/reindex").status_code == 403
    assert c.get("/api/workspaces").status_code == 200


def test_create_directory_route(registry):
    c = client(registry)
    base = BASE
    r = c.post(f"{base}/dirs", json={"dir": "guides", "description": "How-tos"})
    assert r.status_code == 201 and r.json()["dir"] == "guides"
    tree = c.get(f"{base}/tree").json()
    assert {"name": "guides", "dir": "guides", "description": "How-tos"} in tree["directories"]
    assert c.post(f"{base}/dirs", json={"dir": "guides"}).status_code == 400
    assert c.post(f"{base}/dirs", json={"dir": "../x"}).status_code == 400
    assert client(registry, read_only=True).post(f"{base}/dirs", json={"dir": "y"}).status_code == 403


def test_index_overview(registry):
    c = client(registry)
    base = BASE
    assert c.get(f"{base}/overview").json() == {"concepts": 0, "directories": 0, "types": {}, "recent": []}
    for cid, typ in [("ideas/a", "Note"), ("ideas/b", "Note"), ("plan", "Playbook")]:
        c.post(f"{base}/concepts", json={"concept_id": cid, "frontmatter": {"type": typ, "title": cid}, "body": "x"})
    c.post(f"{base}/dirs", json={"dir": "later"})
    o = c.get(f"{base}/overview").json()
    assert o["concepts"] == 3 and o["directories"] == 2
    assert o["types"] == {"Note": 2, "Playbook": 1}
    assert len(o["recent"]) == 3 and {r["id"] for r in o["recent"]} == {"ideas/a", "ideas/b", "plan"}
    assert all(r["timestamp"] for r in o["recent"])


def test_list_dirs_and_backlinks(registry):
    c = client(registry)
    base = BASE
    c.post(f"{base}/concepts", json={"concept_id": "a/x", "frontmatter": {"type": "Note"}, "body": "see [y](../b/y.md)"})
    c.post(f"{base}/concepts", json={"concept_id": "b/y", "frontmatter": {"type": "Note"}, "body": "plain"})
    c.post(f"{base}/dirs", json={"dir": "a/deeper"})
    assert c.get(f"{base}/dirs").json() == {"dirs": ["a", "a/deeper", "b"]}
    assert c.get(f"{base}/concepts/b/y").json()["linked_from"] == ["a/x"]
    assert c.get(f"{base}/concepts/a/x").json()["linked_from"] == []
