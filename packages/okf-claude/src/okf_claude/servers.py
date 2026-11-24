"""MCP server naming: which server serves which workspace.

Shared by the installer (which registers the servers) and the SessionStart hook
(which tells the agent their tool names), so the two always agree.
"""

from __future__ import annotations

import re

SERVER_NAME = "okf"
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def dedupe(workspaces: list[str]) -> list[str]:
    """Drop empty and repeated names, keeping first-seen order."""
    return list(dict.fromkeys(w for w in workspaces if w))


def server_names(workspaces: list[str]) -> dict[str, str]:
    """``{workspace: server name}``: ``okf`` for one workspace, ``okf-<ws>`` for several.

    Raises ``ValueError`` if two workspaces map to the same server name.
    """
    workspaces = dedupe(workspaces)
    if len(workspaces) <= 1:
        return {w: SERVER_NAME for w in workspaces}
    names: dict[str, str] = {}
    seen: dict[str, str] = {}
    for ws in workspaces:
        name = f"{SERVER_NAME}-{_UNSAFE.sub('-', ws)}"
        if name in seen:
            raise ValueError(
                f"workspaces {seen[name]!r} and {ws!r} would share MCP server name {name!r}"
            )
        seen[name] = ws
        names[ws] = name
    return names


def tool_prefix(server: str) -> str:
    return f"mcp__{server}__"
