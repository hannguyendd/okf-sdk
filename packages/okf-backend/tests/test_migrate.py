import json

import pytest

from okf_core import LocalStorage, MemoryStorage, OKFDocument

from okf_backend.migrate import main, migrate_workspace


def _v1(s):
    s.write_text(
        ".okf/workspace.json",
        json.dumps({"version": 1, "color": "red", "bundles": {"b": {"description": "Billing"}, "c": {"description": "C"}}}),
    )
    s.write_text(".okf/vectors.db", "x")
    s.write_text("b/_index.md", "---\nokf_version: '0.1'\n---\n")
    s.write_text("c/_index.md", "---\ndescription: Mine\nokf_version: '0.2'\n---\n")
    s.write_text("b/a.md", "---\ntype: t\n---\n[x](/t/y.md#h) [e](https://e/z.md) [r](../c/q.md)")


def _snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_migrates_links_descriptions_versions(tmp_path):
    s = LocalStorage(tmp_path / "w")
    _v1(s)
    log = migrate_workspace(s)
    assert "[x](/b/t/y.md#h) [e](https://e/z.md) [r](../c/q.md)" in s.read_text("b/a.md")
    assert OKFDocument.parse(s.read_text("b/_index.md")).frontmatter["description"] == "Billing"
    assert OKFDocument.parse(s.read_text("c/_index.md")).frontmatter == {"description": "Mine"}
    assert OKFDocument.parse(s.read_text("_index.md")).frontmatter["okf_version"] == "0.2"
    assert json.loads(s.read_text(".okf/workspace.json")) == {"version": 2, "color": "red"}
    assert not s.exists(".okf/vectors.db")
    assert any("kept _index.md description for c" in line for line in log)
    assert any("okf_version" in line and "differ" in line for line in log)


def test_second_run_is_noop(tmp_path):
    s = LocalStorage(tmp_path / "w")
    _v1(s)
    migrate_workspace(s)
    before = _snapshot(tmp_path / "w")
    assert migrate_workspace(s) == ["already v2"]
    assert _snapshot(tmp_path / "w") == before


def test_dry_run_writes_nothing(tmp_path):
    s = LocalStorage(tmp_path / "w")
    _v1(s)
    before = _snapshot(tmp_path / "w")
    log = migrate_workspace(s, dry_run=True)
    assert log
    assert _snapshot(tmp_path / "w") == before


def test_version_compared_numerically():
    s = MemoryStorage()
    s.write_text("a/_index.md", "---\nokf_version: '0.9'\n---\n")
    s.write_text("b/_index.md", "---\nokf_version: '0.10'\n---\n")
    migrate_workspace(s)
    assert OKFDocument.parse(s.read_text("_index.md")).frontmatter["okf_version"] == "0.10"


def test_missing_workspace_json_and_no_dirs():
    s = MemoryStorage()
    migrate_workspace(s)
    assert json.loads(s.read_text(".okf/workspace.json")) == {"version": 2}


def test_skips_hidden_and_underscore_dirs():
    s = MemoryStorage()
    s.write_text("b/a.md", "---\ntype: t\n---\n[y](/t.md)")
    s.write_text(".hid/a.md", "[y](/t.md)")
    s.write_text("_x/a.md", "[y](/t.md)")
    migrate_workspace(s)
    assert "[y](/b/t.md)" in s.read_text("b/a.md")
    assert s.read_text(".hid/a.md") == "[y](/t.md)"
    assert s.read_text("_x/a.md") == "[y](/t.md)"


def test_main_dry_run_and_real(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    s = LocalStorage(tmp_path / "workspaces" / "w1")
    _v1(s)
    before = _snapshot(tmp_path)
    main(["--dry-run"])
    assert _snapshot(tmp_path) == before
    assert "w1" in capsys.readouterr().out
    main([])
    assert json.loads(s.read_text(".okf/workspace.json"))["version"] == 2


def test_failure_writes_nothing_then_rerun_single_prefixed(tmp_path):
    s = LocalStorage(tmp_path / "w")
    s.write_text(".okf/workspace.json", json.dumps({"version": 1}))
    s.write_text("a/x.md", "---\ntype: t\n---\n[l](/t.md)")
    s.write_text("b/bad.md", "---\ntype: [unclosed\n---\nbody")
    before = _snapshot(tmp_path / "w")
    with pytest.raises(Exception):
        migrate_workspace(s)
    assert _snapshot(tmp_path / "w") == before
    s.write_text("b/bad.md", "---\ntype: t\n---\nbody")
    migrate_workspace(s)
    assert "[l](/a/t.md)" in s.read_text("a/x.md")
    assert "/a/a/" not in s.read_text("a/x.md")


@pytest.mark.parametrize("version", [3, "2", None, 1.5, True])
def test_unsupported_version_raises(version):
    s = MemoryStorage()
    s.write_text(".okf/workspace.json", json.dumps({"version": version}))
    with pytest.raises(ValueError, match=repr(version)):
        migrate_workspace(s)


def test_main_exit_nonzero_but_migrates_others(tmp_path, monkeypatch):
    monkeypatch.setenv("OKF_HOME", str(tmp_path))
    bad = LocalStorage(tmp_path / "workspaces" / "bad")
    bad.write_text(".okf/workspace.json", "{not json")
    good = LocalStorage(tmp_path / "workspaces" / "good")
    _v1(good)
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 1
    assert json.loads(good.read_text(".okf/workspace.json"))["version"] == 2
