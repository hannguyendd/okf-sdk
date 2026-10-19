from __future__ import annotations

import posixpath
from collections import defaultdict
from pathlib import Path
from typing import Callable, overload

from okf_core.constants import INDEX_FILENAME, RESERVED_FILENAMES
from okf_core.document import OKFDocument
from okf_core.storage import Storage, open_storage
from okf_core.synthesizer import fallback_synthesizer

Synthesizer = Callable[[str, list[tuple[str, str]]], str]


def _load_doc(storage: Storage, key: str) -> OKFDocument | None:
    try:
        return OKFDocument.parse(storage.read_text(key))
    except Exception:
        return None


def _build_index_text(entries: list[tuple[str, str, str, str, list[str]]]) -> str:
    # entries: (type, title, relative_link, description, tags)
    grouped: dict[str, list[tuple[str, str, str, list[str]]]] = defaultdict(list)
    for typ, title, link, desc, tags in entries:
        grouped[typ or "Other"].append((title, link, desc, tags))

    sections: list[str] = []
    for typ in sorted(grouped):
        lines = [f"# {typ}", ""]
        for title, link, desc, tags in sorted(grouped[typ], key=lambda e: e[0].lower()):
            suffix = f" - {desc}" if desc else ""
            if tags:
                suffix += f" _(tags: {', '.join(tags)})_"
            lines.append(f"* [{title}]({link}){suffix}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


def _doc_tags(frontmatter: dict) -> list[str]:
    """Normalize a document's ``tags`` frontmatter to a list of strings.

    Mirrors ``Concept.tags``: a missing/empty value yields ``[]`` and a scalar
    is coerced to a single-element list.
    """
    raw = frontmatter.get("tags") or []
    if not isinstance(raw, list):
        raw = [raw]
    return [str(t) for t in raw]


def _read_index_frontmatter(storage: Storage, index_key: str) -> dict:
    """Return an existing ``_index.md``'s frontmatter, or ``{}`` if none/unparseable."""
    doc = _load_doc(storage, index_key)
    return (doc.frontmatter if doc else None) or {}


def _directories_to_index(storage: Storage) -> list[str]:
    """Directory keys (``""`` = root) that contain a ``.md`` file at any depth."""
    dirs: set[str] = set()
    for key in storage.iter_files(suffix=".md"):
        cur = posixpath.dirname(key)
        while True:
            dirs.add(cur)
            if not cur:
                break
            cur = posixpath.dirname(cur)
    return sorted(dirs)


def _depth(key: str) -> int:
    return len(key.split("/")) if key else 0


@overload
def regenerate_indexes(
    bundle_root: Storage, *, synthesize: Synthesizer = ...
) -> list[str]: ...
@overload
def regenerate_indexes(
    bundle_root: Path | str, *, synthesize: Synthesizer = ...
) -> list[Path]: ...


def regenerate_indexes(
    bundle_root: Path | str | Storage,
    *,
    synthesize: Synthesizer = fallback_synthesizer,
) -> list[Path] | list[str]:
    """Regenerate every ``_index.md`` under the bundle and return the ones written.

    For a ``Storage`` argument the result is bundle-relative key strings; for a
    ``Path``/``str`` root it is absolute ``Path`` s (the original behaviour).
    """
    storage = open_storage(bundle_root)
    keys = _regenerate(storage, synthesize)
    if isinstance(bundle_root, Storage):
        return keys
    root = getattr(storage, "root", None)
    if root is None:  # a URI scheme that is not a path: keep keys
        return keys
    return [root / k for k in keys]


def _regenerate(storage: Storage, synthesize: Synthesizer) -> list[str]:
    written: list[str] = []
    if not storage.is_dir(""):
        return written

    directories = sorted(
        _directories_to_index(storage), key=lambda d: (-_depth(d), d)
    )

    dir_descriptions: dict[str, str] = {}

    for directory in directories:
        index_key = posixpath.join(directory, INDEX_FILENAME)
        existing_fm = _read_index_frontmatter(storage, index_key)
        authored = str(existing_fm.get("description") or "").strip()

        entries: list[tuple[str, str, str, str, list[str]]] = []

        for child in storage.list_dir(directory):
            if child.name in RESERVED_FILENAMES:
                continue
            child_key = posixpath.join(directory, child.name)
            if not child.is_dir and child.name.endswith(".md"):
                doc = _load_doc(storage, child_key)
                if doc is None:
                    continue
                fm = doc.frontmatter
                stem = child.name[:-3]
                title = str(fm.get("title") or stem)
                desc = str(fm.get("description") or "")
                typ = str(fm.get("type") or "")
                entries.append((typ, title, child.name, desc, _doc_tags(fm)))
            elif child.is_dir:
                desc = dir_descriptions.get(child_key, "")
                entries.append(
                    (
                        "Subdirectories",
                        child.name,
                        f"{child.name}/{INDEX_FILENAME}",
                        desc,
                        [],
                    )
                )

        if not entries:
            continue

        # Preserve only allowlisted frontmatter: description (any level) and
        # okf_version (bundle root only). Anything else is dropped (self-healing).
        kept_fm: dict = {}
        if not directory and existing_fm.get("okf_version"):
            kept_fm["okf_version"] = existing_fm["okf_version"]
        if authored:
            kept_fm["description"] = authored

        body = _build_index_text(entries)
        text = (
            OKFDocument(frontmatter=kept_fm, body=body).serialize() if kept_fm else body
        )
        storage.write_text(index_key, text)
        written.append(index_key)

        if not directory:
            continue

        # Caption shown in the parent's listing: authored description wins,
        # else a synthesized contents summary.
        if authored:
            dir_descriptions[directory] = authored
        else:
            pairs = [(title, desc) for _, title, _, desc, _ in entries]
            dir_descriptions[directory] = synthesize(directory, pairs)

    return written
