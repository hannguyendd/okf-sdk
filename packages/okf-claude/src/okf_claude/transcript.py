"""Read a Claude Code session transcript (JSONL) into plain conversation turns.

Only what a person would call the conversation is kept: user prompts and the
assistant's text replies. Tool calls, tool results, meta entries, sidechains
(subagents), and command/system-reminder wrappers are dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_NOISE_PREFIXES = (
    "<command-name>",
    "<command-message>",
    "<command-args>",
    "<local-command-stdout>",
    "<local-command-stderr>",
    "<system-reminder>",
    "Caveat: The messages below were generated",
)


@dataclass(frozen=True)
class Turn:
    role: str  # "user" | "assistant"
    text: str
    timestamp: datetime | None = None


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)
    return ""


def _is_noise(text: str) -> bool:
    stripped = text.lstrip()
    return not stripped or stripped.startswith(_NOISE_PREFIXES)


def read_turns(path: Path | str) -> list[Turn]:
    """Parse a transcript file; unreadable lines are skipped."""
    turns: list[Turn] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            role = entry.get("type")
            if role not in ("user", "assistant"):
                continue
            if entry.get("isMeta") or entry.get("isSidechain"):
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            text = _text_of(message.get("content")).strip()
            if _is_noise(text):
                continue
            turns.append(Turn(role, text, _parse_ts(entry.get("timestamp"))))
    return turns


def user_prompt_count(turns: list[Turn]) -> int:
    return sum(1 for t in turns if t.role == "user")


def started_at(turns: list[Turn]) -> datetime | None:
    return next((t.timestamp for t in turns if t.timestamp), None)


def render(turns: list[Turn], max_chars: int = 60_000) -> str:
    """Render turns as text, keeping the first prompt and the most recent tail.

    When the conversation is longer than ``max_chars``, the opening user prompt
    (what the session set out to do) is kept and the rest is cut from the front,
    so the end of the session (where it landed) survives.
    """
    blocks = [f"## {t.role.upper()}\n{t.text}" for t in turns]
    full = "\n\n".join(blocks)
    if len(full) <= max_chars or not blocks:
        return full
    head = blocks[0][: max_chars // 4]
    marker = "\n\n[... earlier conversation omitted ...]\n\n"
    budget = max_chars - len(head) - len(marker)
    tail: list[str] = []
    used = 0
    for block in reversed(blocks[1:]):
        if used + len(block) + 2 > budget:
            if not tail:
                tail.append(block[-budget:])
            break
        tail.append(block)
        used += len(block) + 2
    return head + marker + "\n\n".join(reversed(tail))
