"""okf_core — read and index Open Knowledge Format (OKF) bundles."""
from __future__ import annotations

from okf_core.bundle import Bundle, Concept, extract_links
from okf_core.document import (
    REQUIRED_FRONTMATTER_KEYS,
    OKFDocument,
    OKFDocumentError,
)
from okf_core.index import regenerate_indexes
from okf_core.links import rewrite_links
from okf_core.paths import (
    concept_id_to_path,
    parse_concept_id,
    path_to_concept_id,
)
from okf_core.synthesizer import fallback_synthesizer

__version__ = "0.1.0"

__all__ = [
    "Bundle",
    "Concept",
    "extract_links",
    "rewrite_links",
    "OKFDocument",
    "OKFDocumentError",
    "REQUIRED_FRONTMATTER_KEYS",
    "concept_id_to_path",
    "parse_concept_id",
    "path_to_concept_id",
    "regenerate_indexes",
    "fallback_synthesizer",
    "__version__",
]
