"""Episodes: one OKF concept per Claude Code session, under ``episodes/``.

An episode is written by the SessionEnd hook from a model-written summary of the
session transcript, and read back by the SessionStart hook so a new session
starts with recent history. Writes go through ``okf_mcp.operations`` so they
reindex and log like any other producer write.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

from okf_core import OKFDocument, Storage, WorkspaceRegistry, okf_home

from okf_mcp import operations

EPISODE_DIR = "episodes"
EPISODE_TYPE = "episode"
EPISODE_DIR_DESCRIPTION = (
    "Summaries of past Claude Code sessions, written automatically when a session ends."
)
# Set in the environment of the summarizer's own `claude -p` run so our hooks
# do nothing there (no recursive episodes).
CHILD_ENV = "OKF_CLAUDE_CHILD"


class SummaryError(RuntimeError):
    pass


@dataclass
class Summary:
    title: str
    description: str
    body: str
    tags: list[str] = field(default_factory=list)


def bundle_storage(workspace: str, bundle: str) -> Storage:
    return WorkspaceRegistry().get(workspace).bundle_storage(bundle)


def episode_id(session_id: str, started: datetime | None) -> str:
    day = (started or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    short = re.sub(r"[^A-Za-z0-9]", "", session_id)[:8] or "session"
    return f"{EPISODE_DIR}/{day.isoformat()}-{short}"


def prompt_text(name: str) -> str:
    return files("okf_claude.prompts").joinpath(name).read_text(encoding="utf-8")


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_summary(text: str) -> Summary:
    """Parse the model's JSON answer (tolerating code fences and stray prose)."""
    cleaned = _FENCE_RE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise SummaryError(f"no JSON object in summary output: {text[:200]!r}")
    try:
        data = json.loads(cleaned[start : end + 1])
    except ValueError as exc:
        raise SummaryError(f"invalid JSON in summary output: {exc}") from exc
    title = str(data.get("title") or "").strip()
    body = str(data.get("body") or "").strip()
    if not title or not body:
        raise SummaryError("summary needs a non-empty 'title' and 'body'")
    tags = data.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return Summary(
        title=title[:200],
        description=str(data.get("description") or "").strip()[:500],
        body=body,
        tags=[str(t).strip() for t in tags if str(t).strip()][:8],
    )


def summarize_with_claude(
    transcript_text: str,
    *,
    model: str = "haiku",
    claude_bin: str = "claude",
    timeout: int = 300,
) -> Summary:
    """Ask a headless, tool-less ``claude -p`` run to summarize a transcript."""
    prompt = prompt_text("episode_summary.md").replace("{{transcript}}", transcript_text)
    workdir = okf_home()
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        claude_bin,
        "-p",
        "--model", model,
        "--tools", "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format", "text",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
            env={**os.environ, CHILD_ENV: "1"},
        )
    except FileNotFoundError as exc:
        raise SummaryError(f"{claude_bin!r} not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise SummaryError(f"summarizer timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise SummaryError(f"summarizer exited {proc.returncode}: {proc.stderr.strip()[:500]}")
    return parse_summary(proc.stdout)


def write_episode(
    storage: Storage,
    summary: Summary,
    *,
    session_id: str,
    project: str | None,
    started: datetime | None,
    reason: str | None = None,
) -> dict:
    """Create the session's episode, or update it if the session was resumed."""
    concept_id = episode_id(session_id, started)
    frontmatter = {
        "type": EPISODE_TYPE,
        "title": summary.title,
        "description": summary.description or summary.title,
        "tags": summary.tags,
        "session_id": session_id,
    }
    if project:
        frontmatter["project"] = project
    if started:
        frontmatter["started"] = started.astimezone(timezone.utc).isoformat()
    if reason:
        frontmatter["end_reason"] = reason
    if storage.exists(f"{concept_id}.md"):
        return operations.patch_concept(storage, concept_id, frontmatter, summary.body)
    first = not storage.is_dir(EPISODE_DIR)
    result = operations.add_concept(storage, concept_id, frontmatter, summary.body)
    if first:
        try:
            operations.describe_directory(storage, EPISODE_DIR, EPISODE_DIR_DESCRIPTION)
        except ValueError:
            pass  # cosmetic; the synthesized description is an acceptable fallback
    return result


def recent_episodes(
    storage: Storage, *, project: str | None = None, limit: int = 5
) -> list[dict]:
    """Newest episodes first: ``[{id, title, description, timestamp, body}]``.

    When ``project`` is given, episodes from that project are returned; episodes
    from other projects are only used if the project has none.
    """
    if limit <= 0 or not storage.is_dir(EPISODE_DIR):
        return []
    items: list[dict] = []
    for entry in storage.list_dir(EPISODE_DIR):
        if entry.is_dir or not entry.name.endswith(".md") or entry.name.startswith("_"):
            continue
        key = f"{EPISODE_DIR}/{entry.name}"
        try:
            doc = OKFDocument.parse(storage.read_text(key))
        except Exception:
            continue
        fm = doc.frontmatter or {}
        if fm.get("type") != EPISODE_TYPE:
            continue
        items.append(
            {
                "id": key.removesuffix(".md"),
                "title": str(fm.get("title") or entry.name),
                "description": str(fm.get("description") or ""),
                "timestamp": str(fm.get("timestamp") or ""),
                "project": fm.get("project"),
                "body": doc.body or "",
            }
        )
    if project:
        mine = [e for e in items if e["project"] == project]
        items = mine or items
    items.sort(key=lambda e: e["timestamp"], reverse=True)
    return items[:limit]


def log_path() -> Path:
    return okf_home() / "logs" / "okf-claude.log"


def log(message: str) -> None:
    """Append to the hook log; never raises (hooks must not break a session)."""
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {message}\n")
    except Exception:
        pass
