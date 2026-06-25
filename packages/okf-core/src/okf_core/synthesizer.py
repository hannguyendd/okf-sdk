from __future__ import annotations


def fallback_synthesizer(rel_path: str, children: list[tuple[str, str]]) -> str:
    """Deterministic one-line directory summary used by ``regenerate_indexes``.

    ``children`` is a list of ``(title, description)`` pairs. Returns
    ``"Contains N entries: <comma-joined titles>."`` (or ``"no titled entries"``
    when none of the children have a title), and ``""`` when there are no
    children.

    To generate richer (e.g. LLM-backed) summaries, pass any callable with this
    same ``(rel_path, children) -> str`` signature as
    ``regenerate_indexes(..., synthesize=...)``.
    """
    if not children:
        return ""
    titles = ", ".join(t for t, _ in children if t) or "no titled entries"
    return f"Contains {len(children)} entries: {titles}."
