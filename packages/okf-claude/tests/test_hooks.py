import io
import json
from datetime import datetime, timezone

from okf_claude import episodes, hooks
from okf_claude.episodes import Summary


def _start(stdin_obj, **kw):
    out = io.StringIO()
    rc = hooks.session_start("team", "notes", stdin=io.StringIO(json.dumps(stdin_obj)), stdout=out, **kw)
    return rc, out.getvalue()


def test_session_start_without_episodes_gives_guidance(bundle):
    rc, out = _start({"cwd": "/p", "source": "startup"})
    ctx = json.loads(out)["hookSpecificOutput"]
    assert rc == 0 and ctx["hookEventName"] == "SessionStart"
    assert "`notes` (workspace\n`team`)" in ctx["additionalContext"]
    assert "Recent sessions" not in ctx["additionalContext"]
    assert "{{" not in ctx["additionalContext"]


def test_session_start_lists_recent_episodes(bundle):
    episodes.write_episode(bundle, Summary("Fix search", "Fixed dims", "## Goal\nfix"),
                           session_id="abc12345", project="/p", started=datetime(2026, 11, 13, tzinfo=timezone.utc))
    _, out = _start({"cwd": "/p"})
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "`episodes/2026-11-13-abc12345`" in ctx and "**Fix search** — Fixed dims" in ctx
    assert "### Last session: Fix search" in ctx and "## Goal\nfix" in ctx


def test_session_start_missing_bundle_still_succeeds(okf_home):
    rc, out = _start({})
    assert rc == 0 and "OKF memory" in out


def test_session_start_noop_in_child(bundle, monkeypatch):
    monkeypatch.setenv(episodes.CHILD_ENV, "1")
    assert _start({}) == (0, "")


def test_session_end_spawns_episode_command(okf_home):
    spawned = []
    event = {"session_id": "s1", "transcript_path": "/t.jsonl", "cwd": "/p", "reason": "exit"}
    rc = hooks.session_end("team", "notes", model="haiku", stdin=io.StringIO(json.dumps(event)), spawn=spawned.append)
    assert rc == 0
    (cmd,) = spawned
    i = cmd.index("episode")
    assert cmd[i:] == ["episode", "--workspace", "team", "--bundle", "notes", "--model", "haiku",
                       "--transcript", "/t.jsonl", "--session-id", "s1", "--cwd", "/p", "--reason", "exit"]


def test_session_end_skips_bad_event_and_child(okf_home, monkeypatch):
    spawned = []
    assert hooks.session_end("team", "notes", model="haiku", stdin=io.StringIO("{}"), spawn=spawned.append) == 0
    monkeypatch.setenv(episodes.CHILD_ENV, "1")
    event = json.dumps({"session_id": "s", "transcript_path": "/t"})
    assert hooks.session_end("team", "notes", model="haiku", stdin=io.StringIO(event), spawn=spawned.append) == 0
    assert spawned == []


def test_write_episode_from_transcript(bundle, transcript_file):
    seen = []

    def summarize(text):
        seen.append(text)
        return Summary("Delete tool", "Safe delete", "## Goal\ndelete")

    r = hooks.write_episode_from_transcript("team", "notes", transcript_path=str(transcript_file),
                                            session_id="deadbeef99", cwd="/p", summarize=summarize)
    assert r["concept_id"] == "episodes/2026-11-13-deadbeef"
    assert "Make it safe by default" in seen[0]
    assert "created episodes/2026-11-13-deadbeef in team/notes" in episodes.log_path().read_text()


def test_write_episode_skips_short_sessions(bundle, tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
    called = []
    r = hooks.write_episode_from_transcript("team", "notes", transcript_path=str(t), session_id="s",
                                            summarize=lambda x: called.append(x))
    assert r is None and called == []


def test_episode_failure_returns_1_and_logs(bundle, transcript_file):
    def boom(_):
        raise RuntimeError("no model")

    rc = hooks.episode(workspace="team", bundle="notes", transcript_path=str(transcript_file),
                       session_id="s", summarize=boom)
    assert rc == 1
    assert "no model" in episodes.log_path().read_text()
