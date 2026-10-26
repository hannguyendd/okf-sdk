import pytest
from starlette.testclient import TestClient

from okf_core import MemoryStorage
from okf_mcp import operations as ops
from okf_web.app import create_app


@pytest.fixture
def storage():
    s = MemoryStorage()
    ops.add_concept(s, "tables/orders", {"type": "table", "title": "Orders", "tags": ["a"]},
                    "See [users](users.md)\n")
    ops.add_concept(s, "tables/users", {"type": "table", "title": "Users"}, "x")
    ops.add_concept(s, "notes/n1", {"type": "note", "title": "N1"}, "x")
    ops.describe_directory(s, "tables", "Warehouse tables")
    return s


def client(storage, **kw):
    return TestClient(create_app(storage, **kw))


def test_info(storage):
    r = client(storage).get("/api/info")
    assert r.status_code == 200
    assert r.json() == {"mode": "bundle", "location": storage.location, "read_only": False, "search_enabled": False}


def test_tree_root_and_subdir(storage):
    c = client(storage)
    root = c.get("/api/tree").json()
    assert root["dir"] == ""
    assert [d["name"] for d in root["directories"]] == ["notes", "tables"]
    tables = next(d for d in root["directories"] if d["name"] == "tables")
    assert tables == {"name": "tables", "dir": "tables", "description": "Warehouse tables"}
    assert root["concepts"] == []

    sub = c.get("/api/tree", params={"dir": "tables"}).json()
    assert sub["description"] == "Warehouse tables"
    assert [x["id"] for x in sub["concepts"]] == ["tables/orders", "tables/users"]
    assert sub["concepts"][0]["title"] == "Orders"
    assert sub["concepts"][0]["tags"] == ["a"]


def test_tree_rejects_escape(storage):
    assert client(storage).get("/api/tree", params={"dir": "../x"}).status_code == 400


def test_get_concept_and_missing(storage):
    c = client(storage)
    got = c.get("/api/concepts/tables/orders").json()
    assert got["frontmatter"]["title"] == "Orders"
    assert got["links_to"] == ["tables/users"]
    r = c.get("/api/concepts/nope/x")
    assert r.status_code == 404 and "not found" in r.json()["error"]


def test_list_and_index(storage):
    c = client(storage)
    assert len(c.get("/api/concepts").json()) == 3
    assert [x["id"] for x in c.get("/api/concepts", params={"type": "note"}).json()] == ["notes/n1"]
    idx = c.get("/api/index", params={"depth": 2}).json()
    assert idx[0]["dir"] == ""


def test_add_patch_move_delete_cycle(storage):
    c = client(storage)
    r = c.post("/api/concepts", json={"concept_id": "notes/n2", "frontmatter": {"type": "note"}, "body": "hi"})
    assert r.status_code == 201 and r.json()["action"] == "created"
    assert c.post("/api/concepts", json={"concept_id": "notes/n2", "frontmatter": {"type": "note"}, "body": ""}).status_code == 400
    r = c.patch("/api/concepts/notes/n2", json={"body": "changed"})
    assert r.json()["action"] == "updated"
    assert c.get("/api/concepts/notes/n2").json()["body"].strip() == "changed"
    r = c.post("/api/move", json={"from_concept_id": "notes/n2", "to_concept_id": "notes/n3"})
    assert r.json()["action"] == "moved"
    assert c.delete("/api/concepts/notes/n3").json()["action"] == "deleted"
    assert c.get("/api/concepts/notes/n3").status_code == 404


def test_delete_blocked_then_forced(storage):
    c = client(storage)
    r = c.delete("/api/concepts/tables/users")
    assert r.json()["action"] == "blocked"
    assert r.json()["referenced_by"] == ["tables/orders"]
    assert c.delete("/api/concepts/tables/users", params={"force": "true"}).json()["action"] == "deleted"


def test_describe_and_reindex(storage):
    c = client(storage)
    r = c.post("/api/describe", json={"dir": "notes", "description": "My notes"})
    assert r.status_code == 200
    assert c.get("/api/tree", params={"dir": "notes"}).json()["description"] == "My notes"
    r = c.post("/api/reindex")
    assert r.json()["action"] == "reindexed"


def test_read_only_blocks_writes(storage):
    c = client(storage, read_only=True)
    assert c.get("/api/info").json()["read_only"] is True
    assert c.get("/api/concepts/tables/orders").status_code == 200
    assert c.post("/api/reindex").status_code == 403
    assert c.delete("/api/concepts/tables/users").status_code == 403
    assert c.patch("/api/concepts/tables/users", json={"body": "z"}).status_code == 403


def test_search_unconfigured_is_400(storage):
    r = client(storage).get("/api/search", params={"q": "orders"})
    assert r.status_code == 400 and "embedding" in r.json()["error"]


def test_search_uses_embedder(storage, monkeypatch):
    from okf_web import app as app_mod

    seen = {}

    def fake(root, query, top_k, dir, **kw):
        seen.update(query=query, top_k=top_k, dir=dir)
        return [{"dir": "tables", "path": "tables/_index.md", "score": 0.9, "excerpt": "x"}]

    monkeypatch.setattr(app_mod.operations, "search_indexes", fake)
    c = client(storage, search_config=object())
    assert c.get("/api/info").json()["search_enabled"] is True
    r = c.get("/api/search", params={"q": "orders", "top_k": 3, "dir": "tables"})
    assert r.json()[0]["dir"] == "tables"
    assert seen == {"query": "orders", "top_k": 3, "dir": "tables"}


def test_serves_static_index(storage, tmp_path):
    (tmp_path / "index.html").write_text("<html>app</html>")
    c = TestClient(create_app(storage, static_dir=tmp_path))
    assert "app" in c.get("/").text
    assert "app" in c.get("/some/spa/route").text
    assert c.get("/api/nope").status_code == 404
