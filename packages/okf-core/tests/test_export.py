import pytest

from okf_core import MemoryStorage, export_subtree


def test_export_subtree_rebases_links():
    src, dst = MemoryStorage(), MemoryStorage()
    src.write_text("p/a.md", "see [b](/p/q/b.md) and [o](/other/o.md)")
    src.write_text("p/q/b.md", "b")
    src.write_text("other/o.md", "o")
    assert export_subtree(src, "p", dst) == 2
    assert dst.read_text("a.md") == "see [b](/q/b.md) and [o](/other/o.md)"
    assert dst.read_text("q/b.md") == "b"
    assert not dst.exists("other/o.md")


def test_export_subtree_missing_path_raises():
    src = MemoryStorage()
    src.write_text("a.md", "x")
    with pytest.raises(FileNotFoundError):
        export_subtree(src, "nope", MemoryStorage())
