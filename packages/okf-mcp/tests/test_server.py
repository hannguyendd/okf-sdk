import asyncio

from okf_mcp.server import mcp


def test_all_tools_registered():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"add", "patch", "get", "list", "read_index"} <= names
