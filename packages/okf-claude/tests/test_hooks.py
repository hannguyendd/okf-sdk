import pytest
import io
import json
from datetime import datetime, timezone

from okf_claude import episodes, hooks
from okf_claude.episodes import Summary


def _start(stdin_obj, **kw):
    out = io.StringIO()
    rc = hooks.session_start("team", stdin=io.StringIO(json.dumps(stdin_obj)), stdout=out, **kw)
    return rc, out.getvalue()


def test_session_start_without_episodes_gives_guidance(storage):
    rc, out = _start({"cwd": "/p", "source": "startup"})
    ctx = json.loads(out)["hookSpecificOutput"]
    assert rc == 0 and ctx["hookEventName"] == "SessionStart"
    assert "workspace `team`" in ctx["additionalContext"]
    assert "Recent sessions" not in ctx["additionalContext"]
    assert "{{" not in ctx["additionalContext"]


def test_session_start_lists_recent_episodes(storage):
    episodes.write_episode(storage, Summary("Fix search", "Fixed dims", "## Goal\nfix"),
                           session_id="abc12345", project="/p", started=datetime(2026, 11, 13, tzinfo=timezone.utc))
    _, out = _start({"cwd": "/p"})
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "`episodes/2026-11-13-abc12345`" in ctx and "**Fix search** — Fixed dims" in ctx
    assert "### Last session: Fix search" in ctx and "## Goal\nfix" in ctx


def test_session_start_missing_workspace_still_succeeds(okf_home):
    rc, out = _start({})
    assert rc == 0 and "OKF memory" in out


def test_session_start_noop_in_child(storage, monkeypatch):
    monkeypatch.setenv(episodes.CHILD_ENV, "1")
    assert _start({}) == (0, "")


def test_session_end_spawns_episode_command(okf_home):
    spawned = []
    event = {"session_id": "s1", "transcript_path": "/t.jsonl", "cwd": "/p", "reason": "exit"}
    rc = hooks.session_end("team", model="haiku", stdin=io.StringIO(json.dumps(event)), spawn=spawned.append)
    assert rc == 0
    (cmd,) = spawned
    i = cmd.index("episode")
    assert cmd[i:] == ["episode", "--workspace", "team", "--model", "haiku",
                       "--transcript", "/t.jsonl", "--session-id", "s1", "--cwd", "/p", "--reason", "exit"]


def test_session_end_skips_bad_event_and_child(okf_home, monkeypatch):
    spawned = []
    assert hooks.session_end("team", model="haiku", stdin=io.StringIO("{}"), spawn=spawned.append) == 0
    monkeypatch.setenv(episodes.CHILD_ENV, "1")
    event = json.dumps({"session_id": "s", "transcript_path": "/t"})
    assert hooks.session_end("team", model="haiku", stdin=io.StringIO(event), spawn=spawned.append) == 0
    assert spawned == []


def test_write_episode_from_transcript(storage, transcript_file):
    seen = []

    def summarize(text):
        seen.append(text)
        return Summary("Delete tool", "Safe delete", "## Goal\ndelete")

    r = hooks.write_episode_from_transcript("team", transcript_path=str(transcript_file),
                                            session_id="deadbeef99", cwd="/p", summarize=summarize)
    assert r["concept_id"] == "episodes/2026-11-13-deadbeef"
    assert "Make it safe by default" in seen[0]
    assert "created episodes/2026-11-13-deadbeef in team" in episodes.log_path().read_text()


def test_write_episode_skips_short_sessions(storage, tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
    called = []
    r = hooks.write_episode_from_transcript("team", transcript_path=str(t), session_id="s",
                                            summarize=lambda x: called.append(x))
    assert r is None and called == []


def test_episode_failure_returns_1_and_logs(storage, transcript_file):
    def boom(_):
        raise RuntimeError("no model")

    rc = hooks.episode(workspace="team", transcript_path=str(transcript_file),
                       session_id="s", summarize=boom)
    assert rc == 1
    assert "no model" in episodes.log_path().read_text()


def _make_v1(okf_home, name="team"):
    d = okf_home / "workspaces" / name / ".okf"
    d.mkdir(parents=True)
    (d / "workspace.json").write_text('{"version": 1, "bundles": {}}')
    return d.parent


def test_session_start_on_v1_workspace_exits_zero_and_logs(okf_home):
    _make_v1(okf_home)
    rc, out = _start({"cwd": "/p"})
    assert rc == 0 and "OKF memory" in out
    assert "okf-migrate-v2" in episodes.log_path().read_text()


def test_episode_on_v1_workspace_writes_nothing_and_logs(okf_home, transcript_file):
    ws = _make_v1(okf_home)
    called = []
    rc = hooks.episode(workspace="team", transcript_path=str(transcript_file),
                       session_id="s", summarize=lambda t: called.append(t))
    assert rc == 1 and called == []  # fails before spending a summarizer call
    assert "okf-migrate-v2" in episodes.log_path().read_text()
    assert [p.name for p in ws.iterdir()] == [".okf"]


def test_session_start_includes_root_description_and_listing(storage):
    from okf_backend import operations

    operations.create_directory(storage, "decisions", "Architecture decisions and why.")
    operations.describe_directory(storage, "", "Memory for the widget repo.")
    _, out = _start({"cwd": "/p"})
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "## What this memory holds" in ctx
    assert "Memory for the widget repo." in ctx
    assert "[decisions](decisions/_index.md)" in ctx and "Architecture decisions and why." in ctx
    assert "### Subdirectories" in ctx  # listing headings demoted under the section
    assert ctx.index("What this memory holds") < ctx.index("When to use it")
    assert "{{" not in ctx


def test_session_start_empty_workspace_says_so(storage):
    _, out = _start({})
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "No overview is available" in ctx


def test_session_start_bad_root_index_still_succeeds(storage):
    storage.write_text("_index.md", "---\n: [unclosed\n---\nbody")
    rc, out = _start({})
    assert rc == 0 and "When to use it" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


def _ctx(workspaces, **kw):
    out = io.StringIO()
    assert hooks.session_start(workspaces, stdin=io.StringIO("{}"), stdout=out, **kw) == 0
    return json.loads(out.getvalue())["hookSpecificOutput"]["additionalContext"]


def test_session_start_several_workspaces(okf_home):
    from okf_backend import operations
    from okf_core import WorkspaceRegistry

    reg = WorkspaceRegistry()
    a, b = reg.create("backend").storage, reg.create("team").storage
    operations.describe_directory(a, "", "Backend service rules.")
    operations.describe_directory(b, "", "Team-wide conventions.")
    episodes.write_episode(b, Summary("Team sync", "Synced", ""), session_id="t1234567", project=None,
                           started=datetime(2026, 11, 20, tzinfo=timezone.utc))
    episodes.write_episode(a, Summary("Backend work", "Did it", ""), session_id="b1234567", project=None,
                           started=datetime(2026, 11, 21, tzinfo=timezone.utc))

    ctx = _ctx(["backend", "team"], episodes_workspace="team")
    assert "- `backend`: server `okf-backend`, tools `mcp__okf-backend__*`" in ctx
    assert "## Workspace `backend` (`mcp__okf-backend__*`)" in ctx and "Backend service rules." in ctx
    assert "## Workspace `team` (`mcp__okf-team__*`)" in ctx and "Team-wide conventions." in ctx
    assert "`mcp__<server>__search(query)`" in ctx and "mcp__okf__" not in ctx
    assert "## Recent sessions in `team`" in ctx and "Team sync" in ctx and "Backend work" not in ctx
    assert "`episodes/` in `team`" in ctx
    assert "{{" not in ctx


def test_session_start_single_workspace_unchanged_naming(storage):
    ctx = _ctx(["team"])
    assert "workspace `team`, served by the `okf` MCP server" in ctx
    assert "`mcp__okf__search(query)`" in ctx and "Workspace `team`" not in ctx


def test_session_start_several_with_one_missing_still_works(storage):
    ctx = _ctx(["team", "ghost"])
    assert "## Workspace `ghost`" in ctx and "No overview is available" in ctx


def test_session_start_cli_accepts_repeated_workspace(storage, capsys, monkeypatch):
    from okf_claude import cli

    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    with pytest.raises(SystemExit) as exc:
        cli.main(["hook", "session-start", "-w", "team", "-w", "other", "--episodes", "team"])
    assert exc.value.code == 0
    assert "okf-other" in capsys.readouterr().out
