import json

import pytest
from okf_core import WorkspaceRegistry


@pytest.fixture
def okf_home(tmp_path, monkeypatch):
    home = tmp_path / "okf-home"
    monkeypatch.setenv("OKF_HOME", str(home))
    monkeypatch.delenv("OKF_CLAUDE_CHILD", raising=False)
    return home


@pytest.fixture
def bundle(okf_home):
    reg = WorkspaceRegistry()
    ws = reg.create("team")
    return ws.create_index("notes")


def _entry(kind, content, ts, **extra):
    return {"type": kind, "timestamp": ts, "message": {"role": kind, "content": content}, **extra}


@pytest.fixture
def transcript_file(tmp_path):
    lines = [
        _entry("user", "<command-name>/clear</command-name>", "2026-11-13T09:00:00Z"),
        _entry("user", "Add a delete tool to okf-mcp", "2026-11-13T09:00:01Z"),
        _entry("assistant", [{"type": "text", "text": "I'll add delete_concept."},
                             {"type": "tool_use", "name": "Edit", "input": {}}], "2026-11-13T09:00:02Z"),
        _entry("user", [{"type": "tool_result", "content": "ok"}], "2026-11-13T09:00:03Z"),
        _entry("user", "meta", "2026-11-13T09:00:04Z", isMeta=True),
        _entry("assistant", [{"type": "text", "text": "subagent"}], "2026-11-13T09:00:05Z", isSidechain=True),
        {"type": "summary", "summary": "x"},
        _entry("user", [{"type": "text", "text": "Make it safe by default"}], "2026-11-13T09:01:00Z"),
        _entry("assistant", "Done: refuses when inbound links exist unless force.", "2026-11-13T09:02:00Z"),
    ]
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\nnot json\n")
    return path
