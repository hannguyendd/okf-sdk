from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable

from okf_core.constants import INDEX_FILENAME, RESERVED_FILENAMES
from okf_core.document import OKFDocument
from okf_core.synthesizer import fallback_synthesizer

Synthesizer = Callable[[str, list[tuple[str, str]]], str]


def _load_doc(path: Path) -> OKFDocument | None:
    try:
        return OKFDocument.parse(path.read_text(encoding="utf-8"))
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


def _read_index_frontmatter(index_path: Path) -> dict:
    """Return an existing ``_index.md``'s frontmatter, or ``{}`` if none/unparseable."""
    if not index_path.is_file():
        return {}
    try:
        return (
            OKFDocument.parse(index_path.read_text(encoding="utf-8")).frontmatter or {}
        )
    except Exception:
        return {}


def _directories_to_index(bundle_root: Path) -> list[Path]:
    dirs: set[Path] = set()
    for md in bundle_root.rglob("*.md"):
        cur = md.parent
        while cur != bundle_root.parent:
            dirs.add(cur)
            if cur == bundle_root:
                break
            cur = cur.parent
    return sorted(dirs)


def regenerate_indexes(
    bundle_root: Path | str,
    *,
    synthesize: Synthesizer = fallback_synthesizer,
) -> list[Path]:
    bundle_root = Path(bundle_root)
    written: list[Path] = []
    if not bundle_root.exists():
        return written

    directories = sorted(
        _directories_to_index(bundle_root),
        key=lambda p: (-len(p.relative_to(bundle_root).parts), str(p)),
    )

    dir_descriptions: dict[Path, str] = {}

    for directory in directories:
        index_path = directory / INDEX_FILENAME
        existing_fm = _read_index_frontmatter(index_path)
        authored = str(existing_fm.get("description") or "").strip()

        entries: list[tuple[str, str, str, str, list[str]]] = []

        for child in sorted(directory.iterdir()):
            if child.name in RESERVED_FILENAMES:
                continue
            if child.is_file() and child.suffix == ".md":
                doc = _load_doc(child)
                if doc is None:
                    continue
                fm = doc.frontmatter
                title = str(fm.get("title") or child.stem)
                desc = str(fm.get("description") or "")
                typ = str(fm.get("type") or "")
                entries.append((typ, title, child.name, desc, _doc_tags(fm)))
            elif child.is_dir():
                desc = dir_descriptions.get(child, "")
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
        if directory == bundle_root and existing_fm.get("okf_version"):
            kept_fm["okf_version"] = existing_fm["okf_version"]
        if authored:
            kept_fm["description"] = authored

        body = _build_index_text(entries)
        text = (
            OKFDocument(frontmatter=kept_fm, body=body).serialize() if kept_fm else body
        )
        index_path.write_text(text, encoding="utf-8")
        written.append(index_path)

        if directory == bundle_root:
            continue

        # Caption shown in the parent's listing: authored description wins,
        # else a synthesized contents summary.
        if authored:
            dir_descriptions[directory] = authored
        else:
            rel = str(directory.relative_to(bundle_root))
            pairs = [(title, desc) for _, title, _, desc, _ in entries]
            dir_descriptions[directory] = synthesize(rel, pairs)

    return written
