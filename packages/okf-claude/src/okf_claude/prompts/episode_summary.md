You are writing the episodic memory for a finished Claude Code session. A future
session will read your summary to pick up where this one left off, so write
what that future session needs, not a play-by-play.

Read the transcript below and answer with ONE JSON object and nothing else:

{
  "title": "short title of what the session was about (max 80 chars)",
  "description": "one sentence: what was done and where it landed",
  "tags": ["2-6 lowercase topic tags"],
  "body": "markdown, see below"
}

The `body` uses these sections; drop a section that would be empty:

## Goal
What the user wanted and why, in 1-3 sentences.

## Outcome
What was actually done or decided. Name files, commands, branches, PRs.

## Decisions
Choices made and their reasons, including options rejected.

## Open threads
Unfinished work, known bugs, next steps, questions left for the user.

Rules:
- Be specific and factual; only state what the transcript shows.
- Never include secrets, tokens, passwords, or personal data.
- Keep the body under 400 words.

<transcript>
{{transcript}}
</transcript>
