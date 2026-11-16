from datetime import datetime, timezone

import pytest
from okf_core import OKFDocument

from okf_claude import episodes
from okf_claude.episodes import Summary, SummaryError


def test_episode_id_uses_utc_day_and_short_session():
    started = datetime(2026, 11, 13, 23, 30, tzinfo=timezone.utc)
    assert episodes.episode_id("ab-cd-ef12-3456", started) == "episodes/2026-11-13-abcdef12"


def test_parse_summary_tolerates_fences_and_prose():
    text = 'Here you go:\n```json\n{"title": "T", "description": "D", "tags": ["a", ""], "body": "B"}\n```'
    s = episodes.parse_summary(text)
    assert (s.title, s.description, s.tags, s.body) == ("T", "D", ["a"], "B")


@pytest.mark.parametrize("text", ["no json", '{"title": "", "body": "x"}', "{bad json}"])
def test_parse_summary_rejects_bad_output(text):
    with pytest.raises(SummaryError):
        episodes.parse_summary(text)


def test_write_episode_creates_then_updates(bundle):
    started = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    s = Summary("Delete tool", "Added delete", "## Goal\nx", ["mcp"])
    r1 = episodes.write_episode(bundle, s, session_id="abcdef123", project="/p", started=started, reason="exit")
    assert r1["action"] == "created" and r1["concept_id"] == "episodes/2026-11-13-abcdef12"
    doc = OKFDocument.parse(bundle.read_text("episodes/2026-11-13-abcdef12.md"))
    assert doc.frontmatter["type"] == "episode"
    assert doc.frontmatter["project"] == "/p"
    assert doc.frontmatter["session_id"] == "abcdef123"
    index = OKFDocument.parse(bundle.read_text("episodes/_index.md"))
    assert index.frontmatter["description"] == episodes.EPISODE_DIR_DESCRIPTION

    s2 = Summary("Delete tool v2", "More", "## Goal\ny")
    r2 = episodes.write_episode(bundle, s2, session_id="abcdef123", project="/p", started=started)
    assert r2["action"] == "updated"
    assert OKFDocument.parse(bundle.read_text("episodes/2026-11-13-abcdef12.md")).body.strip() == "## Goal\ny"


def test_recent_episodes_newest_first_and_prefers_project(bundle):
    for i, (sid, project) in enumerate([("aaaa1111", "/p"), ("bbbb2222", "/q"), ("cccc3333", "/p")]):
        episodes.write_episode(bundle, Summary(f"E{i}", "", "b"), session_id=sid, project=project,
                               started=datetime(2026, 11, 10 + i, tzinfo=timezone.utc))
        doc = OKFDocument.parse(bundle.read_text(f"episodes/2026-11-{10 + i}-{sid}.md"))
        doc.frontmatter["timestamp"] = f"2026-11-{10 + i}T00:00:00Z"
        bundle.write_text(f"episodes/2026-11-{10 + i}-{sid}.md", doc.serialize())
    assert [e["title"] for e in episodes.recent_episodes(bundle, project="/p")] == ["E2", "E0"]
    assert [e["title"] for e in episodes.recent_episodes(bundle, project="/none")] == ["E2", "E1", "E0"]
    assert len(episodes.recent_episodes(bundle, limit=1)) == 1
    assert episodes.recent_episodes(bundle, limit=0) == []


def test_recent_episodes_empty_bundle(bundle):
    assert episodes.recent_episodes(bundle) == []


def test_summarize_with_claude_builds_isolated_command(okf_home, monkeypatch):
    seen = {}

    class Proc:
        returncode = 0
        stdout = '{"title": "T", "body": "B"}'
        stderr = ""

    def fake_run(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return Proc()

    monkeypatch.setattr(episodes.subprocess, "run", fake_run)
    s = episodes.summarize_with_claude("TRANSCRIPT", model="sonnet")
    assert s.title == "T"
    assert seen["cmd"][:4] == ["claude", "-p", "--model", "sonnet"]
    assert "--strict-mcp-config" in seen["cmd"] and "--no-session-persistence" in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--tools") + 1] == ""
    assert "TRANSCRIPT" in seen["input"] and "{{transcript}}" not in seen["input"]
    assert seen["env"][episodes.CHILD_ENV] == "1"
