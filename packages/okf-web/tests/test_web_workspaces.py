import pytest
from starlette.testclient import TestClient

from okf_core import WorkspaceRegistry
from okf_web.app import create_app


@pytest.fixture
def registry(tmp_path):
    reg = WorkspaceRegistry(tmp_path / "workspaces")
    ws = reg.create("work")
    ws.create_index("notes", "Meeting notes")
    ws.create_index("docs")
    reg.create("empty")
    return reg


def client(registry, **kw):
    return TestClient(create_app(registry=registry, **kw))


def test_info_reports_workspace_mode(registry):
    info = client(registry).get("/api/info").json()
    assert info["mode"] == "workspace"
    assert info["location"] == registry.storage.location


def test_list_workspaces_with_indexes(registry):
    r = client(registry).get("/api/workspaces").json()
    assert r == [
        {"name": "empty", "indexes": []},
        {"name": "work", "indexes": [
            {"name": "docs", "description": None},
            {"name": "notes", "description": "Meeting notes"},
        ]},
    ]


def test_create_workspace_and_index(registry):
    c = client(registry)
    assert c.post("/api/workspaces", json={"name": "new"}).status_code == 201
    assert c.post("/api/workspaces", json={"name": "new"}).status_code == 400  # exists
    assert c.post("/api/workspaces", json={"name": "../x"}).status_code == 400
    r = c.post("/api/workspaces/new/indexes", json={"name": "mem", "description": "Memory"})
    assert r.status_code == 201 and r.json() == {"name": "mem", "description": "Memory"}
    assert c.post("/api/workspaces/new/indexes", json={"name": "mem"}).status_code == 400
    assert c.post("/api/workspaces/nope/indexes", json={"name": "mem"}).status_code == 404
    assert c.post("/api/workspaces/new/indexes", json={"name": "big", "description": "x" * 1001}).status_code == 400
    assert {"name": "new", "indexes": [{"name": "mem", "description": "Memory"}]} in c.get("/api/workspaces").json()


def test_index_scoped_bundle_routes(registry):
    c = client(registry)
    base = "/api/workspaces/work/indexes/notes"
    r = c.post(f"{base}/concepts", json={"concept_id": "ideas/a", "frontmatter": {"type": "note", "title": "A"}, "body": "x"})
    assert r.status_code == 201
    assert (registry.get("work").index_root("notes") / "ideas" / "a.md").is_file()
    assert c.get(f"{base}/concepts/ideas/a").json()["frontmatter"]["title"] == "A"
    assert [d["name"] for d in c.get(f"{base}/tree").json()["directories"]] == ["ideas"]
    # a different index is isolated
    assert c.get("/api/workspaces/work/indexes/docs/tree").json()["directories"] == []
    assert c.post(f"{base}/reindex").json()["action"] == "reindexed"


def test_unknown_index_is_404(registry):
    assert client(registry).get("/api/workspaces/work/indexes/zzz/tree").status_code == 404
    assert client(registry).get("/api/workspaces/zzz/indexes/notes/tree").status_code == 404


def test_read_only_blocks_workspace_writes(registry):
    c = client(registry, read_only=True)
    assert c.post("/api/workspaces", json={"name": "n"}).status_code == 403
    assert c.post("/api/workspaces/work/indexes", json={"name": "n"}).status_code == 403
    assert c.post("/api/workspaces/work/indexes/notes/reindex").status_code == 403
    assert c.get("/api/workspaces").status_code == 200
