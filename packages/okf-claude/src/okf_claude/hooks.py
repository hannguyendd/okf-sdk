"""Claude Code hook handlers.

Hooks receive the event as JSON on stdin. They must never break a session: every
handler catches its own errors, logs them to ``<OKF_HOME>/logs/okf-claude.log``,
and exits 0.

- ``session-start`` prints each workspace's root overview, OKF guidance, and recent
  episodes (from the episodes workspace) as additional context.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO

from okf_core import INDEX_FILENAME, OKFDocument, Storage


from okf_claude import episodes, transcript
from okf_claude.episodes import CHILD_ENV, Summary, log
from okf_claude.servers import SERVER_NAME, dedupe, server_names, tool_prefix

MIN_USER_PROMPTS = 2
BODY_PREVIEW_CHARS = 1500
OVERVIEW_CHARS = 3000
MIN_OVERVIEW_CHARS = 600


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


@dataclass
class WorkspaceView:
    """One workspace as the SessionStart context shows it."""

    workspace: str
    server: str
    overview: dict | None = None

    @property
    def prefix(self) -> str:
        return tool_prefix(self.server)


def _demote(listing: str) -> str:
    """Push the listing's headings two levels down, below this section's."""
    return re.sub(r"(?m)^(#{1,4}) ", lambda m: "#" * (len(m.group(1)) + 2) + " ", listing)


def _overview_text(view: WorkspaceView, *, heading: str, budget: int) -> str:
    lines = ["", heading, ""]
    overview = view.overview
    if not overview or not (overview["description"] or overview["listing"]):
        lines += [
            "No overview is available: the root `_index.md` is missing or unreadable "
            "(a new workspace is empty).",
            "",
        ]
        return "\n".join(lines)
    if overview["description"]:
        lines += [overview["description"], ""]
    listing = overview["listing"]
    if listing:
        if len(listing) > budget:
            listing = listing[:budget].rstrip() + (
                f"\n\n[... truncated; `{view.prefix}read_index` for the rest]"
            )
        lines += [_demote(listing), ""]
    return "\n".join(lines)


def _recent_text(recent: list[dict], *, workspace: str, prefix: str, multi: bool) -> str:
    if not recent:
        return ""
    where = f" in `{workspace}`" if multi else ""
    lines = ["", f"## Recent sessions{where} (newest first)", ""]
    for e in recent:
        when = e["timestamp"][:10]
        desc = f" — {e['description']}" if e["description"] else ""
        lines.append(f"- `{e['id']}` ({when}) **{e['title']}**{desc}")
    body = recent[0]["body"].strip()
    if body:
        if len(body) > BODY_PREVIEW_CHARS:
            body = body[:BODY_PREVIEW_CHARS].rstrip() + (
                f"\n\n[... truncated; `{prefix}get` for the rest]"
            )
        lines += ["", f"### Last session: {recent[0]['title']}", "", body]
    return "\n".join(lines)


def build_context(
    views: list[WorkspaceView], recent: list[dict], episodes_workspace: str | None = None
) -> str:
    """The SessionStart context: overviews, usage guidance, recent episodes."""
    multi = len(views) > 1
    by_ws = {v.workspace: v for v in views}
    ep_view = by_ws.get(episodes_workspace or "") or views[0]
    if multi:
        budget = max(OVERVIEW_CHARS // len(views), MIN_OVERVIEW_CHARS)
        listed = "\n".join(
            f"- `{v.workspace}`: server `{v.server}`, tools `{v.prefix}*`" for v in views
        )
        intro = (
            "This session has long-term memory in several OKF workspaces, one MCP "
            f"server each:\n\n{listed}\n"
        )
        overview = "".join(
            _overview_text(v, heading=f"## Workspace `{v.workspace}` (`{v.prefix}*`)",
                           budget=budget)
            for v in views
        )
        prefix = "mcp__<server>__"
        choose = (
            "\nEach workspace has its own tools; use the server of the workspace you\n"
            "mean (several if the task spans them). When saving, put the knowledge in\n"
            "the workspace it belongs to, and ask the user if that is unclear.\n"
        )
    else:
        v = views[0]
        intro = (
            f"This session has long-term memory in the OKF workspace `{v.workspace}`, "
            f"served by the `{v.server}` MCP server.\n"
        )
        overview = _overview_text(v, heading="## What this memory holds", budget=OVERVIEW_CHARS)
        prefix = v.prefix
        choose = ""
    text = episodes.prompt_text("session_start.md")
    return (
        text.replace("{{intro}}", intro)
        .replace("{{overview}}", overview)
        .replace("{{choose}}", choose)
        .replace("{{prefix}}", prefix)
        .replace("{{episodes}}", f"`{ep_view.workspace}`")
        .replace(
            "{{recent}}",
            _recent_text(recent, workspace=ep_view.workspace, prefix=ep_view.prefix, multi=multi),
        )
        .rstrip()
        + "\n"
    )


def _view(workspace: str, server: str) -> WorkspaceView:
    view = WorkspaceView(workspace, server)
    try:
        view.overview = root_overview(episodes.workspace_storage(workspace))
    except Exception as exc:  # missing workspace etc.: still give guidance
        log(f"session-start: could not read the overview of {workspace!r}: {exc}")
    return view


def session_start(
    workspaces: list[str] | str,
    *,
    episodes_workspace: str | None = None,
    recent: int = 5,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    if os.environ.get(CHILD_ENV):
        return 0
    stdout = stdout or sys.stdout
    try:
        event = _read_event(stdin or sys.stdin)
        names = dedupe([workspaces] if isinstance(workspaces, str) else list(workspaces))
        try:
            servers = server_names(names)
        except ValueError as exc:
            log(f"session-start: {exc}")
            servers = {ws: SERVER_NAME for ws in names[:1]}
        views = [_view(ws, server) for ws, server in servers.items()]
        ep_ws = episodes_workspace if episodes_workspace in servers else views[0].workspace
        items: list[dict] = []
        try:
            storage = episodes.workspace_storage(ep_ws)
            items = episodes.recent_episodes(storage, project=event.get("cwd"), limit=recent)
        except Exception as exc:
            log(f"session-start: could not read episodes: {exc}")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": build_context(views, items, ep_ws),
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
