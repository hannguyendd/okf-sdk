"""okf_core entry points work on any Storage, with parity to the local path."""

import pytest

from okf_core import Bundle, regenerate_indexes, validate_bundle
from okf_core.storage import LocalStorage, MemoryStorage

DOC = "---\ntype: Table\ntitle: {t}\ndescription: d\ntimestamp: x\n---\n\n{b}\n"


def _populate(s):
    s.write_text("tables/orders.md", DOC.format(t="Orders", b="see [c](../customers.md)"))
    s.write_text("customers.md", DOC.format(t="Customers", b="[o](/tables/orders.md)"))
    s.write_text("tables/_log.md", "# Update Log\n")


def test_bundle_load_from_memory_storage():
    s = MemoryStorage()
    _populate(s)
    b = Bundle.load(s)
    assert [c.id for c in b] == ["customers", "tables/orders"]
    assert b.get("tables/orders").links_to == ["customers"]
    assert b.edges() == [("customers", "tables/orders"), ("tables/orders", "customers")]
    assert b.storage is s


def test_bundle_load_missing_storage_root(tmp_path):
    with pytest.raises(FileNotFoundError):
        Bundle.load(LocalStorage(tmp_path / "nope"))


def test_bundle_root_stays_a_path_for_path_input(tmp_path):
    assert Bundle.load(tmp_path).root == tmp_path


def test_regenerate_indexes_on_storage_returns_keys():
    s = MemoryStorage()
    _populate(s)
    written = regenerate_indexes(s)
    assert sorted(written) == ["_index.md", "tables/_index.md"]
    assert "[Orders](orders.md)" in s.read_text("tables/_index.md")


def test_regenerate_indexes_on_path_returns_absolute_paths(tmp_path):
    _populate(LocalStorage(tmp_path))
    written = regenerate_indexes(tmp_path)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in written) == [
        "_index.md",
        "tables/_index.md",
    ]


def test_regenerate_indexes_missing_storage_is_empty():
    assert regenerate_indexes(MemoryStorage().child("none")) == []


def test_index_parity_local_vs_memory(tmp_path):
    local, mem = LocalStorage(tmp_path), MemoryStorage()
    for s in (local, mem):
        _populate(s)
        s.write_text("_index.md", "---\nokf_version: '0.1'\nfoo: bar\n---\n\n# x\n")
        regenerate_indexes(s)
    for key in ("_index.md", "tables/_index.md"):
        assert local.read_text(key) == mem.read_text(key)


def test_validate_bundle_on_storage():
    s = MemoryStorage()
    _populate(s)
    s.write_text("bad.md", "no frontmatter")
    s.write_text("tables/_index.md", "# Table\n\n* [Orders](orders.md)\n")
    s.write_text("_index.md", "# Table\n\n* [Customers](customers.md)\n")
    vs = validate_bundle(s)
    assert [(v.rule, v.path) for v in vs] == [("DOC-02", "bad.md")]


def test_validate_bundle_storage_missing_root(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_bundle(LocalStorage(tmp_path / "nope"))
