import sqlite3
from pathlib import Path

import pytest

from okf_core import MemoryStorage

from okf_core import WorkspaceRegistry

from okf_mcp.vector_store import VectorStore, VectorStoreError, workspace_db_path

DIM = 4
WORDS = ["alpha", "beta", "gamma", "delta"]


def _vec(text: str) -> list[float]:
    """Unit vector for the first known word in ``text`` (else the last axis)."""
    for i, w in enumerate(WORDS):
        if w in text:
            v = [0.0] * DIM
            v[i] = 1.0
            return v
    return [0.0] * (DIM - 1) + [1.0]


class FakeEmbedder:
    def __init__(self, dim: int = DIM):
        self.calls: list[list[str]] = []
        self.dim = dim

    def __call__(self, texts):
        self.calls.append(list(texts))
        out = []
        for t in texts:
            v = _vec(t)
            out.append(v + [0.0] * (self.dim - DIM) if self.dim > DIM else v[: self.dim])
        return out

    @property
    def embedded(self) -> list[str]:
        return [t for batch in self.calls for t in batch]


def _bundle(**files: str) -> MemoryStorage:
    s = MemoryStorage()
    for key, text in files.items():
        s.write_text(key.replace("__", "/").removesuffix("_md") + ".md", text)
    return s


def _store(tmp_path: Path) -> VectorStore:
    return VectorStore(tmp_path / "v.db")


def test_sync_embeds_every_index_file_once(tmp_path):
    s = _bundle(_index_md="alpha root", tables___index_md="beta tables")
    emb = FakeEmbedder()
    _store(tmp_path).sync(s, emb, bundle="b", description=None, model="m", max_chars=1000)
    assert sorted(emb.embedded) == ["alpha root", "beta tables"]


def test_second_sync_embeds_nothing_when_unchanged(tmp_path):
    s = _bundle(_index_md="alpha root")
    store, emb = _store(tmp_path), FakeEmbedder()
    store.sync(s, emb, bundle="b", description=None, model="m", max_chars=1000)
    emb.calls.clear()
    store.sync(s, emb, bundle="b", description=None, model="m", max_chars=1000)
    assert emb.embedded == []


def test_sync_reembeds_only_changed_file(tmp_path):
    s = _bundle(_index_md="alpha root", tables___index_md="beta tables")
    store, emb = _store(tmp_path), FakeEmbedder()
    store.sync(s, emb, bundle="b", description=None, model="m", max_chars=1000)
    emb.calls.clear()
    s.write_text("tables/_index.md", "gamma tables v2")
    store.sync(s, emb, bundle="b", description=None, model="m", max_chars=1000)
    assert emb.embedded == ["gamma tables v2"]


def test_sync_prunes_deleted_index_file(tmp_path):
    s = _bundle(_index_md="alpha root", tables___index_md="beta tables")
    store, emb = _store(tmp_path), FakeEmbedder()
    store.sync(s, emb, bundle="b", description=None, model="m", max_chars=1000)
    s.delete("tables/_index.md")
    store.sync(s, emb, bundle="b", description=None, model="m", max_chars=1000)
    paths = [h["path"] for h in store.query(_vec("beta"), bundles=["b"], top_k=10)]
    assert paths == ["_index.md"]


def test_sync_ignores_files_not_named_index_md(tmp_path):
    s = _bundle(_index_md="alpha root")
    s.write_text("tables/foo_index.md", "beta nope")
    emb = FakeEmbedder()
    _store(tmp_path).sync(s, emb, bundle="b", description=None, model="m", max_chars=1000)
    assert emb.embedded == ["alpha root"]


def test_text_truncated_to_max_chars(tmp_path):
    s = _bundle(_index_md="alpha 1234567890")
    store, emb = _store(tmp_path), FakeEmbedder()
    store.sync(s, emb, bundle="b", description=None, model="m", max_chars=8)
    assert emb.embedded == ["alpha 12"]
    emb.calls.clear()
    s.write_text("_index.md", "alpha 12XXXXXXXX")  # change after the cut
    store.sync(s, emb, bundle="b", description=None, model="m", max_chars=8)
    assert emb.embedded == []


def test_model_change_rebuilds_store_even_with_new_dimension(tmp_path):
    s = _bundle(_index_md="alpha root")
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(dim=4), bundle="b", description=None, model="m1", max_chars=1000)
    emb2 = FakeEmbedder(dim=6)
    store.sync(s, emb2, bundle="b", description=None, model="m2", max_chars=1000)
    assert emb2.embedded == ["alpha root"]
    hits = store.query(emb2(["alpha"])[0], bundles=["b"], top_k=5)
    assert [h["path"] for h in hits] == ["_index.md"]


def test_failed_sync_rolls_back(tmp_path):
    s = _bundle(_index_md="alpha root")
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)
    s.write_text("tables/_index.md", "beta tables")
    s.write_text("_index.md", "gamma root v2")

    def boom(texts):
        raise RuntimeError("server down")

    with pytest.raises(RuntimeError, match="server down"):
        store.sync(s, boom, bundle="b", description=None, model="m", max_chars=1000)

    hits = store.query(_vec("alpha"), bundles=["b"], top_k=10)
    assert [h["path"] for h in hits] == ["_index.md"]
    assert hits[0]["score"] == pytest.approx(1.0)  # still the old "alpha" vector


def test_dimension_change_under_same_model_rebuilds_store(tmp_path):
    s = _bundle(_index_md="alpha root")
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(dim=4), bundle="b", description=None, model="m", max_chars=1000)
    s.write_text("tables/_index.md", "beta tables")
    emb3 = FakeEmbedder(dim=3)
    store.sync(s, emb3, bundle="b", description=None, model="m", max_chars=1000)
    assert sorted(emb3.embedded) == ["alpha root", "beta tables"]
    hits = store.query(emb3(["alpha"])[0], bundles=["b"], top_k=10)
    assert sorted(h["path"] for h in hits) == ["_index.md", "tables/_index.md"]


def test_embedder_returning_wrong_vector_count_fails_sync_and_keeps_store(tmp_path):
    s = _bundle(_index_md="alpha root")
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)
    s.write_text("tables/_index.md", "beta tables")
    s.write_text("views/_index.md", "gamma views")
    with pytest.raises(VectorStoreError):
        store.sync(s, lambda texts: [_vec(texts[0])], bundle="b", description=None, model="m", max_chars=1000)
    hits = store.query(_vec("alpha"), bundles=["b"], top_k=10)
    assert [h["path"] for h in hits] == ["_index.md"]


def test_sync_does_not_hold_write_lock_while_embedding(tmp_path):
    db = tmp_path / "v.db"
    store = VectorStore(db)
    s = _bundle(_index_md="alpha root")

    def embed(texts):
        other = sqlite3.connect(db, timeout=0.2, isolation_level=None)
        try:  # a concurrent search elsewhere must still be able to write
            other.execute("BEGIN IMMEDIATE")
            other.execute("ROLLBACK")
        finally:
            other.close()
        return [_vec(t) for t in texts]

    store.sync(s, embed, bundle="b", description=None, model="m", max_chars=1000)


def test_unchanged_sync_needs_no_write_lock(tmp_path):
    db = tmp_path / "v.db"
    store = VectorStore(db, busy_timeout_ms=100)
    s = _bundle(_index_md="alpha root")
    store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)  # must not raise
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def test_locked_database_raises_vector_store_error(tmp_path):
    db = tmp_path / "v.db"
    store = VectorStore(db, busy_timeout_ms=100)
    s = _bundle(_index_md="alpha root")
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(VectorStoreError, match="locked"):
            store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def test_query_ranks_by_cosine_and_respects_top_k(tmp_path):
    s = _bundle(
        a___index_md="alpha a",
        b___index_md="beta b",
        c___index_md="alpha and beta",
    )
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)
    hits = store.query(_vec("beta"), bundles=["b"], top_k=2)
    assert [h["path"] for h in hits][0] == "b/_index.md"
    assert len(hits) == 2
    assert hits[0]["score"] >= hits[1]["score"]
    assert len(store.query(_vec("beta"), bundles=["b"], top_k=50)) == 3


def test_query_on_empty_bundle_returns_empty_list(tmp_path):
    s = MemoryStorage()
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)
    assert store.query(_vec("alpha"), bundles=["b"], top_k=5) == []


def test_query_dir_filter_and_hit_shape(tmp_path):
    s = _bundle(
        _index_md="alpha root",
        tables___index_md="alpha tables",
        tables__x___index_md="alpha x",
        views___index_md="alpha views",
    )
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)
    hits = store.query(_vec("alpha"), bundles=["b"], top_k=10, dir="tables")
    assert sorted(h["path"] for h in hits) == ["tables/_index.md", "tables/x/_index.md"]
    root = [h for h in store.query(_vec("alpha"), bundles=["b"], top_k=10) if h["path"] == "_index.md"]
    assert root[0]["dir"] == ""
    assert set(root[0]) == {"bundle", "kind", "dir", "path", "score", "excerpt"}
    assert root[0]["bundle"] == "b" and root[0]["kind"] == "index"



def test_hit_excerpt_prefers_description_then_first_200_chars(tmp_path):
    described = "---\ndescription: Orders and refunds\n---\n# Table\n* alpha\n"
    plain = "alpha " + "x" * 400
    s = _bundle(a___index_md=described, b___index_md=plain)
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), bundle="b", description=None, model="m", max_chars=1000)
    by_path = {h["path"]: h for h in store.query(_vec("alpha"), bundles=["b"], top_k=10)}
    assert by_path["a/_index.md"]["excerpt"] == "Orders and refunds"
    assert by_path["b/_index.md"]["excerpt"] == plain[:200]



def _sync(store, storage, emb, bundle, description=None, model="m"):
    store.sync(storage, emb, bundle=bundle, description=description, model=model, max_chars=1000)


def test_rows_scoped_by_bundle_name(tmp_path):
    one, two = _bundle(_index_md="alpha one"), _bundle(other___index_md="alpha two")
    store, emb = _store(tmp_path), FakeEmbedder()
    _sync(store, one, emb, "a")
    _sync(store, two, emb, "b")
    hits = store.query(_vec("alpha"), 10, bundles=["a"])
    assert [(h["bundle"], h["path"]) for h in hits] == [("a", "_index.md")]


def test_query_merges_bundles_and_ranks_together(tmp_path):
    a = _bundle(_index_md="alpha and beta")
    b = _bundle(x___index_md="beta only")
    store, emb = _store(tmp_path), FakeEmbedder()
    _sync(store, a, emb, "a")
    _sync(store, b, emb, "b")
    hits = store.query(_vec("beta"), 10, bundles=["a", "b"])
    assert [(h["bundle"], h["path"]) for h in hits] == [("b", "x/_index.md"), ("a", "_index.md")]


def test_description_row_is_embedded_and_returned(tmp_path):
    store = _store(tmp_path)
    _sync(store, _bundle(_index_md="beta root"), FakeEmbedder(), "b", "gamma orders and billing")
    hits = store.query(_vec("gamma"), 1, bundles=["b"])
    assert hits[0] == {
        "bundle": "b", "kind": "bundle", "dir": "", "path": None,
        "score": pytest.approx(1.0), "excerpt": "gamma orders and billing",
    }


def test_description_change_reembeds_only_description(tmp_path):
    store, s = _store(tmp_path), _bundle(_index_md="beta root")
    _sync(store, s, FakeEmbedder(), "b", "gamma one")
    emb = FakeEmbedder()
    _sync(store, s, emb, "b", "gamma two")
    assert emb.embedded == ["gamma two"]
    assert [h["excerpt"] for h in store.query(_vec("gamma"), 10, bundles=["b"]) if h["kind"] == "bundle"] == ["gamma two"]


def test_cleared_description_removes_row(tmp_path):
    store, s = _store(tmp_path), _bundle(_index_md="beta root")
    _sync(store, s, FakeEmbedder(), "b", "gamma one")
    _sync(store, s, FakeEmbedder(), "b", None)
    assert all(h["kind"] == "index" for h in store.query(_vec("gamma"), 10, bundles=["b"]))


def test_dir_filter_excludes_description_rows(tmp_path):
    store = _store(tmp_path)
    _sync(store, _bundle(t___index_md="alpha t"), FakeEmbedder(), "b", "alpha desc")
    hits = store.query(_vec("alpha"), 10, bundles=["b"], dir="t")
    assert [h["path"] for h in hits] == ["t/_index.md"]


def test_model_change_wipes_all_bundles(tmp_path):
    store = _store(tmp_path)
    a, b = _bundle(_index_md="alpha a"), _bundle(_index_md="alpha b", x___index_md="beta x")
    _sync(store, a, FakeEmbedder(), "a", model="m1")
    _sync(store, b, FakeEmbedder(), "b", "gamma", model="m1")
    _sync(store, a, FakeEmbedder(), "a", model="m2")
    assert store.query(_vec("alpha"), 10, bundles=["b"]) == []
    emb = FakeEmbedder()
    _sync(store, b, emb, "b", "gamma", model="m2")
    assert sorted(emb.embedded) == ["alpha b", "beta x", "gamma"]


def test_prune_bundles_removes_gone_bundle_rows(tmp_path):
    store = _store(tmp_path)
    _sync(store, _bundle(_index_md="alpha a"), FakeEmbedder(), "a")
    _sync(store, _bundle(_index_md="alpha b"), FakeEmbedder(), "gone", "alpha desc")
    store.prune_bundles({"a"})
    assert store.query(_vec("alpha"), 10, bundles=["gone"]) == []
    assert len(store.query(_vec("alpha"), 10, bundles=["a"])) == 1


def test_prune_bundles_noop_needs_no_write_lock(tmp_path):
    db = tmp_path / "v.db"
    store = VectorStore(db, busy_timeout_ms=100)
    _sync(store, _bundle(_index_md="alpha a"), FakeEmbedder(), "a")
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        store.prune_bundles({"a"})  # must not raise
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def test_workspace_db_path(tmp_path):
    ws = WorkspaceRegistry(tmp_path).create("w")
    assert workspace_db_path(ws) == tmp_path / "w" / ".okf" / "vectors.db"
    mem = WorkspaceRegistry(MemoryStorage()).create("w")
    with pytest.raises(VectorStoreError):
        workspace_db_path(mem)
