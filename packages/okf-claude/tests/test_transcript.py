from okf_claude import transcript
from okf_claude.transcript import Turn


def test_read_turns_keeps_only_conversation(transcript_file):
    turns = transcript.read_turns(transcript_file)
    assert [(t.role, t.text) for t in turns] == [
        ("user", "Add a delete tool to okf-mcp"),
        ("assistant", "I'll add delete_concept."),
        ("user", "Make it safe by default"),
        ("assistant", "Done: refuses when inbound links exist unless force."),
    ]
    assert transcript.user_prompt_count(turns) == 2
    assert transcript.started_at(turns).isoformat() == "2026-11-13T09:00:01+00:00"


def test_render_short_conversation_is_complete():
    turns = [Turn("user", "hi"), Turn("assistant", "hello")]
    assert transcript.render(turns) == "## USER\nhi\n\n## ASSISTANT\nhello"


def test_render_long_conversation_keeps_first_prompt_and_tail():
    turns = [Turn("user", "GOAL")] + [Turn("assistant", f"step {i} " + "x" * 100) for i in range(200)]
    out = transcript.render(turns, max_chars=2000)
    assert len(out) <= 2000
    assert out.startswith("## USER\nGOAL")
    assert "earlier conversation omitted" in out
    assert "step 199" in out and "step 0 " not in out
