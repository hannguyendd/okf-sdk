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
                    ("Subdirectories", child.name, f"{child.name}/{INDEX_FILENAME}", desc, [])
                )

        if not entries:
            continue

        index_path = directory / INDEX_FILENAME
        index_path.write_text(_build_index_text(entries), encoding="utf-8")
        written.append(index_path)

        if directory == bundle_root:
            continue

        pairs = [(title, desc) for _, title, _, desc, _ in entries]
        if len(pairs) == 1 and pairs[0][1]:
            dir_descriptions[directory] = pairs[0][1]
        else:
            rel = str(directory.relative_to(bundle_root))
            dir_descriptions[directory] = synthesize(rel, pairs)

    return written
