from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from okf_core.validate import Violation, validate_bundle, main


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip(), encoding="utf-8")


def _rules_for(violations: list[Violation], path: str) -> set[str]:
    return {v.rule for v in violations if v.path == path}


def _make_conformant_bundle(root: Path) -> None:
    _write(
        root / "_index.md",
        """
        ---
        okf_version: "0.1"
        ---

        # Subdirectories

        * [tables/](tables/) - Warehouse tables.
        """,
    )
    _write(
        root / "_log.md",
        """
        # Update Log

        ## 2026-05-28
        * **Creation**: Added the orders table.
        """,
    )
    _write(
        root / "tables" / "_index.md",
        """
        # Tables

        * [Orders](orders.md) - One row per order.
        """,
    )
    _write(
        root / "tables" / "orders.md",
        """
        ---
        type: BigQuery Table
        title: Orders
        description: One row per completed customer order.
        ---

        # Schema

        Part of the sales domain.
        """,
    )


def test_conformant_bundle_has_no_violations(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_conformant_bundle(root)
    assert validate_bundle(root) == []


def test_missing_frontmatter_block_flags_doc_02(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(root / "metrics.md", "# Monthly Active Users\n\nNo frontmatter here.\n")
    assert "DOC-02" in _rules_for(validate_bundle(root), "metrics.md")


def test_unterminated_frontmatter_flags_doc_02(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "metrics.md",
        """
        ---
        type: Metric
        title: MAU

        # Body never closes the block
        """,
    )
    assert "DOC-02" in _rules_for(validate_bundle(root), "metrics.md")


def test_non_mapping_frontmatter_flags_doc_03(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "customers.md",
        """
        ---
        - BigQuery Table
        - Customers
        ---

        One row per customer.
        """,
    )
    assert "DOC-03" in _rules_for(validate_bundle(root), "customers.md")


def test_missing_type_flags_fm_01(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "orders.md",
        """
        ---
        title: Orders
        description: One row per order.
        ---

        Body.
        """,
    )
    assert "FM-01" in _rules_for(validate_bundle(root), "orders.md")


def test_empty_type_flags_fm_01(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "orders.md",
        """
        ---
        type: "   "
        title: Orders
        ---

        Body.
        """,
    )
    assert "FM-01" in _rules_for(validate_bundle(root), "orders.md")


def test_invalid_utf8_flags_doc_01(tmp_path: Path):
    root = tmp_path / "bundle"
    root.mkdir(parents=True)
    (root / "bad.md").write_bytes(b"---\ntype: X\n---\n\xff\xfe not utf-8\n")
    assert "DOC-01" in _rules_for(validate_bundle(root), "bad.md")


def test_non_root_index_with_frontmatter_flags_idx_01(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "tables" / "_index.md",
        """
        ---
        type: Index
        title: Tables
        ---

        # Tables

        * [Orders](orders.md) - Orders.
        """,
    )
    assert "IDX-01" in _rules_for(validate_bundle(root), "tables/_index.md")


def test_root_index_with_only_okf_version_is_allowed(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "_index.md",
        """
        ---
        okf_version: "0.1"
        ---

        # Contents

        * [tables/](tables/) - Tables.
        """,
    )
    assert "IDX-01" not in _rules_for(validate_bundle(root), "_index.md")


def test_root_index_with_extra_frontmatter_key_flags_idx_01(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "_index.md",
        """
        ---
        okf_version: "0.1"
        title: My Bundle
        ---

        # Contents

        * [tables/](tables/) - Tables.
        """,
    )
    assert "IDX-01" in _rules_for(validate_bundle(root), "_index.md")


def test_idx01_allows_description_in_subdir_index(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "tables" / "_index.md",
        """
        ---
        description: Sales tables.
        ---

        # Tables

        * [Orders](orders.md) - Orders.
        """,
    )
    assert "IDX-01" not in _rules_for(validate_bundle(root), "tables/_index.md")


def test_idx01_allows_description_and_okf_version_at_root(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "_index.md",
        """
        ---
        okf_version: "0.1"
        description: The bundle.
        ---

        # Contents

        * [tables/](tables/) - Tables.
        """,
    )
    assert "IDX-01" not in _rules_for(validate_bundle(root), "_index.md")


def test_idx01_rejects_okf_version_in_subdir(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "tables" / "_index.md",
        """
        ---
        okf_version: "0.1"
        ---

        # Tables

        * [Orders](orders.md) - Orders.
        """,
    )
    assert "IDX-01" in _rules_for(validate_bundle(root), "tables/_index.md")


def test_index_without_heading_flags_idx_02(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "tables" / "_index.md",
        "* [Orders](orders.md) - Orders.\n* [Customers](customers.md) - Customers.\n",
    )
    assert "IDX-02" in _rules_for(validate_bundle(root), "tables/_index.md")


def test_log_non_iso_date_heading_flags_log_01(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "_log.md",
        """
        # Update Log

        ## May 28, 2026
        * **Creation**: Added the orders table.
        """,
    )
    assert "LOG-01" in _rules_for(validate_bundle(root), "_log.md")


def test_log_with_frontmatter_flags_rsv_01(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "_log.md",
        """
        ---
        type: Log
        ---

        # Update Log

        ## 2026-05-28
        * **Creation**: Added the orders table.
        """,
    )
    assert "RSV-01" in _rules_for(validate_bundle(root), "_log.md")


def test_violation_has_rule_path_and_message(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(root / "metrics.md", "no frontmatter\n")
    v = validate_bundle(root)[0]
    assert v.rule and v.path and v.message


def test_missing_root_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_bundle(tmp_path / "nope")


def test_main_returns_zero_for_conformant_bundle(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_conformant_bundle(root)
    assert main([str(root)]) == 0


def test_main_returns_one_for_non_conformant_bundle(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(root / "metrics.md", "no frontmatter\n")
    assert main([str(root)]) == 1


def test_main_returns_two_for_missing_root(tmp_path: Path):
    assert main([str(tmp_path / "nope")]) == 2
