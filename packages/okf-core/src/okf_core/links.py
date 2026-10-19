"""Rewrite a document's markdown links when it moves within a bundle."""
from __future__ import annotations

import os
import posixpath
import re
from pathlib import Path

from okf_core.paths import parse_concept_id

# Mirrors bundle._LINK_RE but captures the target and anchor so they can be
# re-rendered. Keep the two patterns in sync.
_LINK_RE = re.compile(r"\]\((?P<target>[^)\s]+\.md)(?P<anchor>#[A-Za-z0-9_\-]*)?\)")


def _resolve_target_id(target: str, doc_dir: str) -> str | None:
    """Resolve a markdown link target to a bundle concept id, or ``None``.

    ``doc_dir`` is the document's bundle-relative directory key (``""`` for the
    root). Returns ``None`` for external (``scheme://``) links and targets that
    escape the bundle root, matching ``extract_links``' skip rules. Pure string
    logic (no filesystem access), so it works for any storage backend.
    """
    if "://" in target:
        return None
    if target.startswith("/"):
        joined = target.lstrip("/")
    else:
        joined = posixpath.join(doc_dir, target)
    rel = posixpath.normpath(joined)
    if rel == "." or rel == ".." or rel.startswith("../") or rel.startswith("/"):
        return None
    if rel.endswith(".md"):
        rel = rel[:-3]
    return rel or None


def _dir_key(directory: Path, bundle_root: Path) -> str:
    """Bundle-relative directory key for a (possibly symlinked) local ``directory``.

    Directories outside the bundle yield a ``..``-leading key, so every link
    resolved against them is treated as escaping the bundle.
    """
    rel = Path(os.path.relpath(directory.resolve(), bundle_root.resolve())).as_posix()
    return "" if rel == "." else rel


def rewrite_link_ids(
    body: str,
    doc_dir_old: str,
    doc_dir_new: str,
    id_map: dict[str, str],
) -> str:
    """Path-free core of :func:`rewrite_links`; directories are bundle-relative keys."""
    dir_changed = doc_dir_old != doc_dir_new

    def _sub(m: re.Match[str]) -> str:
        target = m.group("target")
        anchor = m.group("anchor") or ""
        old_id = _resolve_target_id(target, doc_dir_old)
        if old_id is None:
            return m.group(0)
        new_id = id_map.get(old_id, old_id)
        if new_id == old_id and not dir_changed:
            return m.group(0)  # nothing to change; preserve verbatim
        parse_concept_id(new_id)  # validate segments
        new_file = f"{new_id}.md"
        if target.startswith("/"):
            new_target = "/" + new_file
        else:
            new_target = posixpath.relpath(new_file, doc_dir_new or ".")
        if new_target == target:
            return m.group(0)
        return f"]({new_target}{anchor})"

    return _LINK_RE.sub(_sub, body)


def rewrite_links(
    body: str,
    doc_dir_old: Path,
    doc_dir_new: Path,
    bundle_root: Path,
    id_map: dict[str, str],
) -> str:
    """Recompute markdown links so they stay valid after a document moves.

    Resolves each ``](target.md)`` link in ``body`` (against ``doc_dir_old`` and
    ``bundle_root``, using the same rules as ``extract_links``), remaps the
    target concept id via ``id_map`` (old id -> new id), and re-renders the link
    relative to ``doc_dir_new`` -- preserving the ``#anchor`` and the absolute
    (``/...``) vs relative style. External and out-of-bundle links are left
    untouched, as are links whose rendered text would be unchanged.
    """
    return rewrite_link_ids(
        body,
        _dir_key(doc_dir_old, bundle_root),
        _dir_key(doc_dir_new, bundle_root),
        id_map,
    )


# Mirrors _LINK_RE but also captures the [label] so the whole link can be
# replaced by its label. Keep the target/anchor groups in sync with _LINK_RE.
_FULL_LINK_RE = re.compile(
    r"\[(?P<label>[^\]]*)\]\((?P<target>[^)\s]+\.md)(?P<anchor>#[A-Za-z0-9_\-]*)?\)"
)


def strip_link_ids(body: str, doc_dir: str, target_ids: set[str]) -> str:
    """Path-free core of :func:`strip_links`; ``doc_dir`` is a bundle-relative key."""

    def _sub(m: re.Match[str]) -> str:
        target_id = _resolve_target_id(m.group("target"), doc_dir)
        if target_id is None or target_id not in target_ids:
            return m.group(0)
        return m.group("label")

    return _FULL_LINK_RE.sub(_sub, body)


def strip_links(
    body: str,
    doc_dir: Path,
    bundle_root: Path,
    target_ids: set[str],
) -> str:
    """Remove markdown links pointing at any id in ``target_ids``, keeping text.

    Resolves each ``[label](target.md)`` link in ``body`` (against ``doc_dir``
    and ``bundle_root``, using the same rules as ``extract_links`` /
    ``rewrite_links``). When the resolved target concept id is in
    ``target_ids``, the entire link -- brackets, target, and any ``#anchor`` --
    is replaced by its bare ``label`` text. External (``scheme://``) and
    out-of-bundle links, and links whose target is not in ``target_ids``, are
    left untouched. Returns an equal body when nothing applies.
    """
    return strip_link_ids(body, _dir_key(doc_dir, bundle_root), target_ids)
