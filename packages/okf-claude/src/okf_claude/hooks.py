"""Claude Code hook handlers.

Hooks receive the event as JSON on stdin. They must never break a session: every
handler catches its own errors, logs them to ``<OKF_HOME>/logs/okf-claude.log``,
and exits 0.

- ``session-start`` prints OKF guidance plus recent episodes as additional context.
- ``session-end`` starts a detached ``episode`` run and returns at once (SessionEnd
  hooks have a short timeout, and summarizing takes a model call).
- ``episode`` (internal) summarizes the transcript and writes the episode.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, TextIO

from okf_claude import episodes, transcript
from okf_claude.episodes import CHILD_ENV, Summary, log

MIN_USER_PROMPTS = 2
BODY_PREVIEW_CHARS = 1500


def _read_event(stdin: TextIO) -> dict:
    try:
        data = json.load(stdin)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def build_context(workspace: str, bundle: str, recent: list[dict]) -> str:
    if recent:
        lines = ["", "## Recent sessions (newest first)", ""]
        for e in recent:
            when = e["timestamp"][:10]
            desc = f" — {e['description']}" if e["description"] else ""
            lines.append(f"- `{e['id']}` ({when}) **{e['title']}**{desc}")
        body = recent[0]["body"].strip()
        if body:
            if len(body) > BODY_PREVIEW_CHARS:
                body = body[:BODY_PREVIEW_CHARS].rstrip() + "\n\n[... truncated; `mcp__okf__get` for the rest]"
            lines += ["", f"### Last session: {recent[0]['title']}", "", body]
        recent_text = "\n".join(lines)
    else:
        recent_text = ""
    text = episodes.prompt_text("session_start.md")
    return (
        text.replace("{{workspace}}", workspace)
        .replace("{{bundle}}", bundle)
        .replace("{{recent}}", recent_text)
        .rstrip()
        + "\n"
    )


def session_start(
    workspace: str, bundle: str, *, recent: int = 5, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout
) -> int:
    if os.environ.get(CHILD_ENV):
        return 0
    try:
        event = _read_event(stdin)
        try:
            storage = episodes.bundle_storage(workspace, bundle)
            items = episodes.recent_episodes(storage, project=event.get("cwd"), limit=recent)
        except Exception as exc:  # missing bundle etc.: still give guidance
            log(f"session-start: could not read episodes: {exc}")
            items = []
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": build_context(workspace, bundle, items),
            }
        }
        stdout.write(json.dumps(output))
    except Exception as exc:
        log(f"session-start failed: {exc!r}")
    return 0


def _self_command() -> list[str]:
    exe = Path(sys.executable).parent / "okf-claude"
    return [str(exe)] if exe.exists() else [sys.executable, "-m", "okf_claude"]


def session_end(
    workspace: str,
    bundle: str,
    *,
    model: str,
    stdin: TextIO = sys.stdin,
    spawn: Callable[[list[str]], object] | None = None,
) -> int:
    if os.environ.get(CHILD_ENV):
        return 0
    try:
        event = _read_event(stdin)
        path = event.get("transcript_path")
        session_id = event.get("session_id")
        if not path or not session_id:
            log("session-end: event has no transcript_path/session_id; skipped")
            return 0
        cmd = _self_command() + [
            "episode",
            "--workspace", workspace,
            "--bundle", bundle,
            "--model", model,
            "--transcript", str(path),
            "--session-id", str(session_id),
        ]
        if event.get("cwd"):
            cmd += ["--cwd", str(event["cwd"])]
        if event.get("reason"):
            cmd += ["--reason", str(event["reason"])]
        (spawn or _spawn_detached)(cmd)
    except Exception as exc:
        log(f"session-end failed: {exc!r}")
    return 0


def _spawn_detached(cmd: list[str]) -> None:
    path = episodes.log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as err:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=err,
            start_new_session=True,
        )


def write_episode_from_transcript(
    workspace: str,
    bundle: str,
    *,
    transcript_path: str,
    session_id: str,
    cwd: str | None = None,
    reason: str | None = None,
    model: str = "haiku",
    summarize: Callable[[str], Summary] | None = None,
) -> dict | None:
    """Summarize a transcript and write it as an episode; ``None`` if skipped."""
    turns = transcript.read_turns(transcript_path)
    if transcript.user_prompt_count(turns) < MIN_USER_PROMPTS:
        log(f"episode {session_id}: fewer than {MIN_USER_PROMPTS} prompts; skipped")
        return None
    text = transcript.render(turns)
    summary = (summarize or (lambda t: episodes.summarize_with_claude(t, model=model)))(text)
    storage = episodes.bundle_storage(workspace, bundle)
    result = episodes.write_episode(
        storage,
        summary,
        session_id=session_id,
        project=cwd,
        started=transcript.started_at(turns),
        reason=reason,
    )
    log(f"episode {session_id}: {result['action']} {result['concept_id']} in {workspace}/{bundle}")
    return result


def episode(**kwargs) -> int:
    try:
        write_episode_from_transcript(**kwargs)
    except Exception as exc:
        log(f"episode {kwargs.get('session_id')} failed: {exc!r}")
        return 1
    return 0
