import sqlite3
from pathlib import Path

import pytest

from okf_core import LocalStorage, MemoryStorage, open_storage

from okf_mcp.vector_store import VectorStore, VectorStoreError, default_db_path

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
    _store(tmp_path).sync(s, emb, model="m", max_chars=1000)
    assert sorted(emb.embedded) == ["alpha root", "beta tables"]


def test_second_sync_embeds_nothing_when_unchanged(tmp_path):
    s = _bundle(_index_md="alpha root")
    store, emb = _store(tmp_path), FakeEmbedder()
    store.sync(s, emb, model="m", max_chars=1000)
    emb.calls.clear()
    store.sync(s, emb, model="m", max_chars=1000)
    assert emb.embedded == []


def test_sync_reembeds_only_changed_file(tmp_path):
    s = _bundle(_index_md="alpha root", tables___index_md="beta tables")
    store, emb = _store(tmp_path), FakeEmbedder()
    store.sync(s, emb, model="m", max_chars=1000)
    emb.calls.clear()
    s.write_text("tables/_index.md", "gamma tables v2")
    store.sync(s, emb, model="m", max_chars=1000)
    assert emb.embedded == ["gamma tables v2"]


def test_sync_prunes_deleted_index_file(tmp_path):
    s = _bundle(_index_md="alpha root", tables___index_md="beta tables")
    store, emb = _store(tmp_path), FakeEmbedder()
    store.sync(s, emb, model="m", max_chars=1000)
    s.delete("tables/_index.md")
    store.sync(s, emb, model="m", max_chars=1000)
    paths = [h["path"] for h in store.query(s, _vec("beta"), top_k=10)]
    assert paths == ["_index.md"]


def test_sync_ignores_files_not_named_index_md(tmp_path):
    s = _bundle(_index_md="alpha root")
    s.write_text("tables/foo_index.md", "beta nope")
    emb = FakeEmbedder()
    _store(tmp_path).sync(s, emb, model="m", max_chars=1000)
    assert emb.embedded == ["alpha root"]


def test_text_truncated_to_max_chars(tmp_path):
    s = _bundle(_index_md="alpha 1234567890")
    store, emb = _store(tmp_path), FakeEmbedder()
    store.sync(s, emb, model="m", max_chars=8)
    assert emb.embedded == ["alpha 12"]
    emb.calls.clear()
    s.write_text("_index.md", "alpha 12XXXXXXXX")  # change after the cut
    store.sync(s, emb, model="m", max_chars=8)
    assert emb.embedded == []


def test_model_change_rebuilds_store_even_with_new_dimension(tmp_path):
    s = _bundle(_index_md="alpha root")
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(dim=4), model="m1", max_chars=1000)
    emb2 = FakeEmbedder(dim=6)
    store.sync(s, emb2, model="m2", max_chars=1000)
    assert emb2.embedded == ["alpha root"]
    hits = store.query(s, emb2(["alpha"])[0], top_k=5)
    assert [h["path"] for h in hits] == ["_index.md"]


def test_failed_sync_rolls_back(tmp_path):
    s = _bundle(_index_md="alpha root")
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), model="m", max_chars=1000)
    s.write_text("tables/_index.md", "beta tables")
    s.write_text("_index.md", "gamma root v2")

    def boom(texts):
        raise RuntimeError("server down")

    with pytest.raises(RuntimeError, match="server down"):
        store.sync(s, boom, model="m", max_chars=1000)

    hits = store.query(s, _vec("alpha"), top_k=10)
    assert [h["path"] for h in hits] == ["_index.md"]
    assert hits[0]["score"] == pytest.approx(1.0)  # still the old "alpha" vector


def test_dimension_change_under_same_model_rebuilds_store(tmp_path):
    s = _bundle(_index_md="alpha root")
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(dim=4), model="m", max_chars=1000)
    s.write_text("tables/_index.md", "beta tables")
    emb3 = FakeEmbedder(dim=3)
    store.sync(s, emb3, model="m", max_chars=1000)
    assert sorted(emb3.embedded) == ["alpha root", "beta tables"]
    hits = store.query(s, emb3(["alpha"])[0], top_k=10)
    assert sorted(h["path"] for h in hits) == ["_index.md", "tables/_index.md"]


def test_embedder_returning_wrong_vector_count_fails_sync_and_keeps_store(tmp_path):
    s = _bundle(_index_md="alpha root")
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), model="m", max_chars=1000)
    s.write_text("tables/_index.md", "beta tables")
    s.write_text("views/_index.md", "gamma views")
    with pytest.raises(VectorStoreError):
        store.sync(s, lambda texts: [_vec(texts[0])], model="m", max_chars=1000)
    hits = store.query(s, _vec("alpha"), top_k=10)
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

    store.sync(s, embed, model="m", max_chars=1000)


def test_unchanged_sync_needs_no_write_lock(tmp_path):
    db = tmp_path / "v.db"
    store = VectorStore(db, busy_timeout_ms=100)
    s = _bundle(_index_md="alpha root")
    store.sync(s, FakeEmbedder(), model="m", max_chars=1000)
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        store.sync(s, FakeEmbedder(), model="m", max_chars=1000)  # must not raise
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
            store.sync(s, FakeEmbedder(), model="m", max_chars=1000)
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
    store.sync(s, FakeEmbedder(), model="m", max_chars=1000)
    hits = store.query(s, _vec("beta"), top_k=2)
    assert [h["path"] for h in hits][0] == "b/_index.md"
    assert len(hits) == 2
    assert hits[0]["score"] >= hits[1]["score"]
    assert len(store.query(s, _vec("beta"), top_k=50)) == 3


def test_query_on_empty_bundle_returns_empty_list(tmp_path):
    s = MemoryStorage()
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), model="m", max_chars=1000)
    assert store.query(s, _vec("alpha"), top_k=5) == []


def test_query_dir_filter_and_hit_shape(tmp_path):
    s = _bundle(
        _index_md="alpha root",
        tables___index_md="alpha tables",
        tables__x___index_md="alpha x",
        views___index_md="alpha views",
    )
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), model="m", max_chars=1000)
    hits = store.query(s, _vec("alpha"), top_k=10, dir="tables")
    assert sorted(h["path"] for h in hits) == ["tables/_index.md", "tables/x/_index.md"]
    root = [h for h in store.query(s, _vec("alpha"), top_k=10) if h["path"] == "_index.md"]
    assert root[0]["dir"] == ""
    assert set(root[0]) == {"dir", "path", "score", "excerpt"}


def test_rows_scoped_by_storage_location(tmp_path):
    class Named(MemoryStorage):
        def __init__(self, name):
            super().__init__()
            self._name = name

        @property
        def location(self):
            return self._name

    one, two = Named("one"), Named("two")
    one.write_text("_index.md", "alpha one")
    two.write_text("other/_index.md", "alpha two")
    store = _store(tmp_path)
    emb = FakeEmbedder()
    store.sync(one, emb, model="m", max_chars=1000)
    store.sync(two, emb, model="m", max_chars=1000)
    assert [h["path"] for h in store.query(one, _vec("alpha"), top_k=10)] == ["_index.md"]
    assert [h["path"] for h in store.query(two, _vec("alpha"), top_k=10)] == [
        "other/_index.md"
    ]


def test_hit_excerpt_prefers_description_then_first_200_chars(tmp_path):
    described = "---\ndescription: Orders and refunds\n---\n# Table\n* alpha\n"
    plain = "alpha " + "x" * 400
    s = _bundle(a___index_md=described, b___index_md=plain)
    store = _store(tmp_path)
    store.sync(s, FakeEmbedder(), model="m", max_chars=1000)
    by_path = {h["path"]: h for h in store.query(s, _vec("alpha"), top_k=10)}
    assert by_path["a/_index.md"]["excerpt"] == "Orders and refunds"
    assert by_path["b/_index.md"]["excerpt"] == plain[:200]


def test_default_db_path_is_sibling_and_stable(tmp_path):
    expected = tmp_path / "b.vectors.db"
    root = tmp_path / "b"
    root.mkdir()
    assert default_db_path(LocalStorage(root)) == expected
    assert default_db_path(LocalStorage(str(root) + "/")) == expected
    assert default_db_path(open_storage(root.as_uri())) == expected
    with pytest.raises(VectorStoreError, match="OKF_VECTOR_DB"):
        default_db_path(MemoryStorage())
