from __future__ import annotations


def test_public_api_is_importable_from_top_level():
    import okf_core

    expected = {
        "OKFDocument",
        "OKFDocumentError",
        "REQUIRED_FRONTMATTER_KEYS",
        "Concept",
        "Bundle",
        "extract_links",
        "concept_id_to_path",
        "path_to_concept_id",
        "parse_concept_id",
        "regenerate_indexes",
        "fallback_synthesizer",
        "Violation",
        "validate_bundle",
    }
    assert expected <= set(okf_core.__all__)
    for name in expected:
        assert hasattr(okf_core, name), f"okf_core.{name} is not exported"
    assert okf_core.__version__ == "0.1.0"
