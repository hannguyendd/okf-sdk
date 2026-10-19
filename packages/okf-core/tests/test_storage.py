import threading

import pytest

from okf_core.storage import (
    Entry,
    LocalStorage,
    MemoryStorage,
    Storage,
    normalize_key,
    open_storage,
    register_backend,
)


@pytest.fixture(params=["local", "memory"])
def store(request, tmp_path):
    if request.param == "local":
        root = tmp_path / "bundle"
        root.mkdir()
        return LocalStorage(root)
    return MemoryStorage()


# ---- key validation -------------------------------------------------------


@pytest.mark.parametrize("bad", ["/abs", "a/../b", "..", "a//b", "a\\b", "./a", "a/."])
def test_normalize_key_rejects(bad):
    with pytest.raises(ValueError):
        normalize_key(bad)


def test_normalize_key_accepts():
    assert normalize_key("") == ""
    assert normalize_key("a/b.md") == "a/b.md"
    assert normalize_key("a/b/") == "a/b"


# ---- contract (both backends) --------------------------------------------


def test_write_read_roundtrip_creates_parents(store):
    store.write_text("a/b/c.md", "héllo\r\nworld")
    assert store.read_text("a/b/c.md") == "héllo\r\nworld"
    assert store.is_dir("a/b")
    assert store.exists("a/b/c.md") and not store.is_dir("a/b/c.md")


def test_write_overwrites(store):
    store.write_text("x.md", "1")
    store.write_text("x.md", "2")
    assert store.read_text("x.md") == "2"


def test_read_missing(store):
    with pytest.raises(FileNotFoundError):
        store.read_text("nope.md")


def test_exists_and_is_dir_root(store):
    assert store.is_dir("")
    assert store.exists("")
    assert not store.exists("missing")
    assert not store.is_dir("missing")


def test_delete(store):
    store.write_text("d/x.md", "1")
    store.delete("d/x.md")
    assert not store.exists("d/x.md")
    assert store.is_dir("d")  # directories are left behind
    with pytest.raises(FileNotFoundError):
        store.delete("d/x.md")


def test_list_dir_sorted_with_kinds(store):
    store.write_text("b.md", "1")
    store.write_text("a/x.md", "1")
    store.write_text("c.md", "1")
    assert store.list_dir("") == [
        Entry("a", True),
        Entry("b.md", False),
        Entry("c.md", False),
    ]
    assert store.list_dir("a") == [Entry("x.md", False)]


def test_list_dir_missing_or_file(store):
    store.write_text("f.md", "1")
    with pytest.raises(FileNotFoundError):
        store.list_dir("nope")
    with pytest.raises(FileNotFoundError):
        store.list_dir("f.md")


def test_mkdir(store):
    store.mkdir("empty/inner")
    assert store.is_dir("empty/inner")
    assert store.list_dir("empty") == [Entry("inner", True)]


def test_iter_files_recursive_sorted_filtered(store):
    store.write_text("z.md", "1")
    store.write_text("a/y.md", "1")
    store.write_text("a/b/x.md", "1")
    store.write_text("a/note.txt", "1")
    assert list(store.iter_files()) == ["a/b/x.md", "a/note.txt", "a/y.md", "z.md"]
    assert list(store.iter_files(suffix=".md")) == ["a/b/x.md", "a/y.md", "z.md"]
    assert list(store.iter_files("a", ".md")) == ["a/b/x.md", "a/y.md"]
    assert list(store.iter_files("missing")) == []


def test_move(store):
    store.write_text("a.md", "body")
    store.move("a.md", "new/dir/b.md")
    assert store.read_text("new/dir/b.md") == "body"
    assert not store.exists("a.md")


def test_move_errors(store):
    store.write_text("a.md", "1")
    store.write_text("b.md", "2")
    with pytest.raises(FileNotFoundError):
        store.move("missing.md", "c.md")
    with pytest.raises(FileExistsError):
        store.move("a.md", "b.md")
    assert store.read_text("a.md") == "1" and store.read_text("b.md") == "2"


def test_child_scopes_keys(store):
    child = store.child("proj-1")
    child.write_text("t/x.md", "1")
    assert store.read_text("proj-1/t/x.md") == "1"
    assert child.read_text("t/x.md") == "1"
    assert child.list_dir("") == [Entry("t", True)]
    assert list(child.iter_files()) == ["t/x.md"]
    assert child.is_dir("")
    assert store.child("fresh").is_dir("") is False
    child.mkdir("")
    assert store.is_dir("proj-1")


def test_lock_is_exclusive_across_threads(store):
    events: list[str] = []
    inside = threading.Event()

    def other():
        with store.lock():
            events.append("other")

    with store.lock():
        t = threading.Thread(target=other)
        t.start()
        inside.wait(0.05)
        events.append("main")
    t.join(2)
    assert events == ["main", "other"]


def test_lock_is_reentrant(store):
    with store.lock():
        with store.lock():
            store.write_text("x.md", "1")
    assert store.read_text("x.md") == "1"


def test_lock_shared_between_instances_of_same_root(tmp_path):
    a, b = LocalStorage(tmp_path), LocalStorage(tmp_path)
    with a.lock():
        with b.lock():  # must not deadlock (same process, same root)
            pass


# ---- LocalStorage specifics ----------------------------------------------


def test_local_write_is_atomic_leaves_no_temp_files(tmp_path):
    s = LocalStorage(tmp_path)
    s.write_text("a.md", "1")
    s.write_text("a.md", "2")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.md"]


def test_local_write_failure_keeps_old_content(tmp_path, monkeypatch):
    s = LocalStorage(tmp_path)
    s.write_text("a.md", "old")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError):
        s.write_text("a.md", "new")
    monkeypatch.undo()
    assert s.read_text("a.md") == "old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.md"]


def test_local_no_newline_translation(tmp_path):
    s = LocalStorage(tmp_path)
    s.write_text("a.md", "a\r\nb\n")
    assert (tmp_path / "a.md").read_bytes() == b"a\r\nb\n"
    assert s.read_text("a.md") == "a\r\nb\n"


def test_local_root_property_and_location(tmp_path):
    s = LocalStorage(tmp_path)
    assert s.root == tmp_path.resolve()
    assert str(tmp_path.resolve()) in s.location


def test_local_child_is_local(tmp_path):
    c = LocalStorage(tmp_path).child("p")
    assert isinstance(c, LocalStorage)
    assert c.root == tmp_path.resolve() / "p"


def test_local_lock_file_is_not_a_concept(tmp_path):
    s = LocalStorage(tmp_path)
    with s.lock():
        pass
    assert list(s.iter_files(suffix=".md")) == []


# ---- selection ------------------------------------------------------------


def test_open_storage_passthrough():
    m = MemoryStorage()
    assert open_storage(m) is m


def test_open_storage_path_and_str(tmp_path):
    assert isinstance(open_storage(tmp_path), LocalStorage)
    s = open_storage(str(tmp_path))
    assert isinstance(s, LocalStorage) and s.root == tmp_path.resolve()


def test_open_storage_file_uri(tmp_path):
    s = open_storage(tmp_path.as_uri())
    assert isinstance(s, LocalStorage) and s.root == tmp_path.resolve()


def test_open_storage_windows_drive_is_a_path():
    s = open_storage("C:\\bundles\\x")
    assert isinstance(s, LocalStorage)


def test_open_storage_registered_scheme():
    seen = []

    def factory(location):
        seen.append(location)
        return MemoryStorage()

    register_backend("fake", factory)
    s = open_storage("fake://bucket/prefix")
    assert isinstance(s, MemoryStorage)
    assert seen == ["fake://bucket/prefix"]


def test_open_storage_unknown_scheme():
    with pytest.raises(ValueError, match="nosuch"):
        open_storage("nosuch://x")


def test_open_storage_entry_point(monkeypatch):
    class EP:
        name = "ep"

        @staticmethod
        def load():
            return lambda location: MemoryStorage()

    monkeypatch.setattr(
        "okf_core.storage._entry_points", lambda: [EP()], raising=True
    )
    assert isinstance(open_storage("ep://thing"), MemoryStorage)


def test_storage_is_abstract():
    with pytest.raises(TypeError):
        Storage()  # type: ignore[abstract]
