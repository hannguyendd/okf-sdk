from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from okf_core.document import OKFDocument, OKFDocumentError

_INDEX_NAME = "index.md"
_LINK_RE = re.compile(r"\]\(([^)\s]+\.md)(?:#[A-Za-z0-9_\-]*)?\)")


def extract_links(body: str, doc_dir: Path, bundle_root: Path) -> list[str]:
    """Resolve the markdown links in ``body`` to concept ids.

    Relative links resolve against the document's directory; absolute links
    beginning with ``/`` resolve against ``bundle_root`` (the OKF-recommended
    form). External ``scheme://`` links are skipped. Results are normalized to
    concept ids (``.md`` removed) and deduped, preserving first-seen order.

    Examples (``doc_dir=root/topics``, ``bundle_root=root``)::

        "[intro](./basics.md)"           -> ["topics/basics"]
        "[home](/index-page.md)"         -> ["index-page"]      # absolute
        "[sec](other.md#part-2)"         -> ["topics/other"]    # anchor stripped
        "[site](https://x.com/page.md)"  -> []                  # external skipped
        "[up](../outside.md)"            -> []                  # escapes root
        "[a](a.md) [b](b.md) [a](a.md)"  -> ["topics/a",        # deduped, ordered
                                            "topics/b"]
    """
    out: list[str] = []
    seen: set[str] = set()
    bundle_root_resolved = bundle_root.resolve()
    for m in _LINK_RE.finditer(body):
        target = m.group(1)
        if "://" in target:
            continue
        if target.startswith("/"):
            base = bundle_root_resolved
            rel_target = target.lstrip("/")
        else:
            base = doc_dir
            rel_target = target
        try:
            resolved = (base / rel_target).resolve().relative_to(bundle_root_resolved)
        except ValueError:
            continue
        rel = resolved.as_posix()
        if rel.endswith(".md"):
            rel = rel[:-3]
        if rel and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


@dataclass
class Concept:
    id: str
    document: OKFDocument
    links_to: list[str] = field(default_factory=list)

    @property
    def type(self) -> str:
        return str(self.document.frontmatter.get("type") or "Unknown")

    @property
    def title(self) -> str:
        return str(self.document.frontmatter.get("title") or self.id)

    @property
    def description(self) -> str:
        return str(self.document.frontmatter.get("description") or "")

    @property
    def resource(self) -> str:
        return str(self.document.frontmatter.get("resource") or "")

    @property
    def tags(self) -> list[str]:
        raw = self.document.frontmatter.get("tags") or []
        if not isinstance(raw, list):
            raw = [raw]
        return [str(t) for t in raw]

    @property
    def body(self) -> str:
        return self.document.body


@dataclass
class Bundle:
    root: Path
    concepts: list[Concept] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_id: dict[str, Concept] = {c.id: c for c in self.concepts}

    @classmethod
    def load(cls, root: Path | str) -> "Bundle":
        root = Path(root)
        if not root.is_dir():
            raise FileNotFoundError(f"Bundle directory not found: {root}")
        concepts: list[Concept] = []
        for md_path in sorted(root.rglob("*.md")):
            if md_path.name == _INDEX_NAME:
                continue
            rel = md_path.relative_to(root).with_suffix("")
            concept_id = "/".join(rel.parts)
            try:
                doc = OKFDocument.parse(md_path.read_text(encoding="utf-8"))
            except OKFDocumentError:
                continue
            links = extract_links(doc.body or "", md_path.parent, root)
            concepts.append(Concept(id=concept_id, document=doc, links_to=links))
        return cls(root=root, concepts=concepts)

    def get(self, concept_id: str) -> Concept | None:
        return self._by_id.get(concept_id)

    def __contains__(self, concept_id: object) -> bool:
        return concept_id in self._by_id

    def __iter__(self):
        return iter(self.concepts)

    def __len__(self) -> int:
        return len(self.concepts)

    def edges(self) -> list[tuple[str, str]]:
        ids = set(self._by_id)
        out: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for c in self.concepts:
            for target in c.links_to:
                if target == c.id or target not in ids:
                    continue
                key = (c.id, target)
                if key in seen:
                    continue
                seen.add(key)
                out.append(key)
        return out

    def backlinks(self, concept_id: str) -> list[str]:
        return [src for src, tgt in self.edges() if tgt == concept_id]

    def types(self) -> list[str]:
        return sorted({c.type for c in self.concepts})
