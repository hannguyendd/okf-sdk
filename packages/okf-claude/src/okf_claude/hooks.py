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
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, TextIO

from okf_core import INDEX_FILENAME, OKFDocument, Storage


from okf_claude import episodes, transcript
from okf_claude.episodes import CHILD_ENV, Summary, log

MIN_USER_PROMPTS = 2
BODY_PREVIEW_CHARS = 1500
OVERVIEW_CHARS = 3000


def _read_event(stdin: TextIO) -> dict:
    try:
        data = json.load(stdin)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def root_overview(storage: Storage) -> dict:
    """The workspace root ``_index.md``: ``{description, listing}`` (either may be "").

    ``description`` is the authored frontmatter description of the workspace;
    ``listing`` is the generated body (subdirectories and concepts with their
    descriptions). The agent reads both at session start to decide whether the
    memory is relevant to the task before calling any tool.
    """
    if not storage.exists(INDEX_FILENAME):
        return {"description": "", "listing": ""}
    doc = OKFDocument.parse(storage.read_text(INDEX_FILENAME))
    desc = doc.frontmatter.get("description")
    return {
        "description": desc.strip() if isinstance(desc, str) else "",
        "listing": doc.body.strip(),
    }


def _overview_text(overview: dict | None) -> str:
    if not overview or not (overview["description"] or overview["listing"]):
        return (
            "\n## What this memory holds\n\nNo overview is available: the root `_index.md` is missing or unreadable "
            "(a new workspace is empty).\n"
        )
    lines = ["", "## What this memory holds", ""]
    if overview["description"]:
        lines += [overview["description"], ""]
    listing = overview["listing"]
    if listing:
        if len(listing) > OVERVIEW_CHARS:
            listing = listing[:OVERVIEW_CHARS].rstrip() + (
                "\n\n[... truncated; `mcp__okf__read_index` for the rest]"
            )
        # Demote the listing's headings below this section's.
        listing = re.sub(r"(?m)^(#{1,4}) ", lambda m: "#" * (len(m.group(1)) + 2) + " ", listing)
        lines += [listing, ""]
    return "\n".join(lines)


def build_context(workspace: str, recent: list[dict], overview: dict | None = None) -> str:
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
        .replace("{{overview}}", _overview_text(overview))
        .replace("{{recent}}", recent_text)
        .rstrip()
        + "\n"
    )


def session_start(
    workspace: str, *, recent: int = 5, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout
) -> int:
    if os.environ.get(CHILD_ENV):
        return 0
    try:
        event = _read_event(stdin)
        items: list[dict] = []
        overview: dict | None = None
        try:
            storage = episodes.workspace_storage(workspace)
        except Exception as exc:  # missing workspace etc.: still give guidance
            log(f"session-start: could not open workspace: {exc}")
        else:
            try:
                overview = root_overview(storage)
            except Exception as exc:
                log(f"session-start: could not read root _index.md: {exc}")
            try:
                items = episodes.recent_episodes(storage, project=event.get("cwd"), limit=recent)
            except Exception as exc:
                log(f"session-start: could not read episodes: {exc}")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": build_context(workspace, items, overview),
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
    # Resolve (and check) the workspace before paying for a summary.
    storage = episodes.workspace_storage(workspace)
    text = transcript.render(turns)
    summary = (summarize or (lambda t: episodes.summarize_with_claude(t, model=model)))(text)
    result = episodes.write_episode(
        storage,
        summary,
        session_id=session_id,
        project=cwd,
        started=transcript.started_at(turns),
        reason=reason,
    )
    log(f"episode {session_id}: {result['action']} {result['concept_id']} in {workspace}")
    return result


def episode(**kwargs) -> int:
    try:
        write_episode_from_transcript(**kwargs)
    except Exception as exc:
        log(f"episode {kwargs.get('session_id')} failed: {exc!r}")
        return 1
    return 0
