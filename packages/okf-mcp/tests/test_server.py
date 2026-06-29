import asyncio

from okf_mcp.server import Settings, mcp


def test_all_tools_registered():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"add", "patch", "get", "list", "read_index", "move"} <= names


def test_settings_reads_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("OKF_BUNDLE_ROOT", raising=False)
    target = tmp_path / "bundle"
    target.mkdir()
    (tmp_path / ".env").write_text(f"OKF_BUNDLE_ROOT={target}\n")
    monkeypatch.chdir(tmp_path)
    assert Settings().bundle_root == target
