"""okf_core — read and index Open Knowledge Format (OKF) bundles."""
from __future__ import annotations

from okf_core.bundle import Bundle, Concept, extract_link_ids, extract_links
from okf_core.constants import (
    INDEX_FILENAME,
    INDEX_STEM,
    LOG_FILENAME,
    LOG_STEM,
    RESERVED_FILENAMES,
    RESERVED_STEMS,
)
from okf_core.document import (
    REQUIRED_FRONTMATTER_KEYS,
    OKFDocument,
    OKFDocumentError,
)
from okf_core.index import regenerate_indexes
from okf_core.links import rewrite_link_ids, rewrite_links, strip_link_ids, strip_links
from okf_core.paths import (
    concept_id_to_path,
    parse_concept_id,
    path_to_concept_id,
)
from okf_core.storage import (
    Entry,
    LocalStorage,
    MemoryStorage,
    Storage,
    open_storage,
    register_backend,
)
from okf_core.synthesizer import fallback_synthesizer

__version__ = "0.1.0"

__all__ = [
    "Bundle",
    "Concept",
    "extract_links",
    "extract_link_ids",
    "rewrite_links",
    "rewrite_link_ids",
    "strip_links",
    "strip_link_ids",
    "Storage",
    "Entry",
    "LocalStorage",
    "MemoryStorage",
    "open_storage",
    "register_backend",
    "OKFDocument",
    "OKFDocumentError",
    "REQUIRED_FRONTMATTER_KEYS",
    "concept_id_to_path",
    "parse_concept_id",
    "path_to_concept_id",
    "regenerate_indexes",
    "fallback_synthesizer",
    "INDEX_FILENAME",
    "INDEX_STEM",
    "LOG_FILENAME",
    "LOG_STEM",
    "RESERVED_FILENAMES",
    "RESERVED_STEMS",
    "Violation",
    "validate_bundle",
    "__version__",
]


def __getattr__(name: str):
    # Expose the validate API lazily so that `python -m okf_core.validate` does
    # not import the module both as a package attribute and as __main__ (which
    # triggers a runpy RuntimeWarning).
    if name in ("Violation", "validate_bundle"):
        from okf_core import validate

        return getattr(validate, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
