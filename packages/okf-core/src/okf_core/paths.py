from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from okf_core.storage import Storage, normalize_key

_SEGMENT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*")


def _validate_segment(seg: str) -> None:
    if not _SEGMENT_RE.fullmatch(seg):
        raise ValueError(f"Invalid concept id segment: {seg!r}")


def concept_id_to_path(bundle_root: Path, concept_id: tuple[str, ...]) -> Path:
    if not concept_id:
        raise ValueError("concept_id must have at least one segment")
    for seg in concept_id:
        _validate_segment(seg)
    *dirs, name = concept_id
    return bundle_root.joinpath(*dirs, f"{name}.md")


def path_to_concept_id(bundle_root: Path, path: Path) -> tuple[str, ...]:
    rel = path.relative_to(bundle_root).with_suffix("")
    return tuple(rel.parts)


def parse_concept_id(s: str) -> tuple[str, ...]:
    parts = tuple(p for p in s.split("/") if p)
    if not parts:
        raise ValueError(f"Empty concept id: {s!r}")
    for p in parts:
        _validate_segment(p)
    return parts


def is_hidden(key: str) -> bool:
    """True if any segment of the bundle-relative ``key`` starts with ``.``.

    Hidden entries (``.okf/``, ``.git/``, ``notes/.cache/``, ``.x.md``) are
    never bundle content: they are not loaded, indexed, listed, validated, or
    searched. ``_``-prefixed reserved files (``_index.md``, ``_log.md``) have
    their own rules and are *not* hidden.
    """
    return any(seg.startswith(".") for seg in key.split("/") if seg)


def iter_visible_files(storage: Storage, prefix: str = "", suffix: str = "") -> Iterator[str]:
    """Like ``Storage.iter_files`` but skips hidden entries without descending into them."""
    prefix = normalize_key(prefix)
    if is_hidden(prefix):
        return
    try:
        entries = storage.list_dir(prefix)
    except FileNotFoundError:
        return
    for e in entries:
        if is_hidden(e.name):
            continue
        key = f"{prefix}/{e.name}" if prefix else e.name
        if e.is_dir:
            yield from iter_visible_files(storage, key, suffix)
        elif e.name.endswith(suffix):
            yield key
