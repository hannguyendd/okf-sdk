"""Reserved filenames defined by the OKF format.

Every ``.md`` file in a bundle is either a concept document or one of these
reserved files. The reserved files are special at *any* level of the tree and
must never be used as concepts (see ``CONFORMANCE.md`` rules RSV-01 / RSV-02).
This module is the single source of truth for their names.
"""
from __future__ import annotations

#: Directory listing for progressive disclosure (at most one per directory).
INDEX_FILENAME = "_index.md"
#: Chronological update history for the scope (level) it sits in.
LOG_FILENAME = "_log.md"

#: All reserved filenames; a ``.md`` file with one of these names is never a concept.
RESERVED_FILENAMES = (INDEX_FILENAME, LOG_FILENAME)

#: Reserved concept-id stems — the reserved filenames with the ``.md`` suffix
#: removed. A concept id whose final segment is one of these collides with a
#: reserved file and is rejected by producer tooling.
INDEX_STEM = INDEX_FILENAME.removesuffix(".md")
LOG_STEM = LOG_FILENAME.removesuffix(".md")
RESERVED_STEMS = (INDEX_STEM, LOG_STEM)
