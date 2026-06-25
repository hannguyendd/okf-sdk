from __future__ import annotations


def test_okf_core_imports_with_version():
    import okf_core

    assert okf_core.__version__ == "0.1.0"
