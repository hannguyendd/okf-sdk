from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path

from okf_core.constants import RESERVED_FILENAMES
from okf_core.document import OKFDocument, OKFDocumentError
from okf_core.links import _dir_key, _resolve_target_id
from okf_core.storage import Storage, is_uri, open_storage

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
    return extract_link_ids(body, _dir_key(doc_dir, bundle_root))


def extract_link_ids(body: str, doc_dir: str) -> list[str]:
    """Path-free core of :func:`extract_links`.

    ``doc_dir`` is the document's bundle-relative directory key (``""`` for the
    root); same resolution, skip, and dedupe rules.
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in _LINK_RE.finditer(body):
        rel = _resolve_target_id(m.group(1), doc_dir)
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
    """A loaded bundle. ``root`` is whatever it was loaded from (path or storage);
    ``storage`` is the resolved backend."""

    root: Path | str | Storage
    concepts: list[Concept] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_id: dict[str, Concept] = {c.id: c for c in self.concepts}
        self.storage: Storage = open_storage(self.root)

    @classmethod
    def load(cls, root: "Path | str | Storage") -> "Bundle":
        storage = open_storage(root)
        if not storage.is_dir(""):
            raise FileNotFoundError(f"Bundle directory not found: {storage.location}")
        concepts: list[Concept] = []
        for key in storage.iter_files(suffix=".md"):
            if posixpath.basename(key) in RESERVED_FILENAMES:
                continue
            try:
                doc = OKFDocument.parse(storage.read_text(key))
            except (OKFDocumentError, UnicodeDecodeError):
                continue
            links = extract_link_ids(doc.body or "", posixpath.dirname(key))
            concepts.append(Concept(id=key[:-3], document=doc, links_to=links))
        keep = Path(root) if isinstance(root, (str, Path)) and not is_uri(root) else storage
        return cls(root=keep, concepts=concepts)

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
