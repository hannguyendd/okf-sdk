from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from okf_core.bundle import Bundle


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip(), encoding="utf-8")


def _make_bundle(root: Path) -> None:
    _write(
        root / "datasets" / "my_dataset.md",
        """
        ---
        type: BigQuery Dataset
        title: My dataset
        description: A test dataset.
        resource: https://example.com/dataset
        tags: [test]
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Parent dataset for [users](../tables/users.md).
        """,
    )
    _write(
        root / "tables" / "users.md",
        """
        ---
        type: BigQuery Table
        title: Users
        description: User profiles.
        resource: https://example.com/users
        tags: [users]
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Joinable with [events](events.md) and see [DAU](../references/metrics/dau.md).
        """,
    )
    _write(
        root / "tables" / "events.md",
        """
        ---
        type: BigQuery Table
        title: Events
        description: User events.
        resource: https://example.com/events
        tags: [events]
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        See [users](users.md).
        """,
    )
    _write(
        root / "references" / "metrics" / "dau.md",
        """
        ---
        type: Reference
        title: Daily active users
        description: DAU metric.
        resource: https://example.com/dau
        tags: [metric]
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        COUNT(DISTINCT user_id) per day.
        """,
    )
    # An index.md must NOT be loaded as a concept.
    _write(root / "index.md", "# My Bundle\n- tables/users\n- tables/events\n")


def test_load_collects_concepts_excluding_index(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    assert len(b) == 4
    ids = {c.id for c in b}
    assert "index" not in ids
    assert ids == {
        "datasets/my_dataset",
        "tables/users",
        "tables/events",
        "references/metrics/dau",
    }


def test_edges_capture_relative_cross_links(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    pairs = set(b.edges())
    assert ("datasets/my_dataset", "tables/users") in pairs
    assert ("tables/users", "tables/events") in pairs
    assert ("tables/users", "references/metrics/dau") in pairs
    assert ("tables/events", "tables/users") in pairs


def test_backlinks_reverse_the_graph(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    assert set(b.backlinks("tables/users")) == {
        "datasets/my_dataset",
        "tables/events",
    }
    assert b.backlinks("datasets/my_dataset") == []


def test_types_are_sorted_unique(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    assert b.types() == ["BigQuery Dataset", "BigQuery Table", "Reference"]


def test_concept_accessors_and_full_frontmatter_preserved(tmp_path: Path):
    root = tmp_path / "bundle"
    _make_bundle(root)
    b = Bundle.load(root)
    c = b.get("tables/users")
    assert c is not None
    assert c.type == "BigQuery Table"
    assert c.title == "Users"
    assert c.description == "User profiles."
    assert c.resource == "https://example.com/users"
    assert c.tags == ["users"]
    assert "tables/users" in b
    # Arbitrary frontmatter is preserved on the underlying document.
    assert c.document.frontmatter["timestamp"] == "2026-05-28T00:00:00+00:00"


def test_missing_link_targets_are_skipped(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "tables" / "lonely.md",
        """
        ---
        type: BigQuery Table
        title: Lonely
        description: Has a dangling link.
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Links to [missing](missing.md).
        """,
    )
    b = Bundle.load(root)
    assert len(b) == 1
    assert b.edges() == []


def test_absolute_bundle_root_links_resolve(tmp_path: Path):
    root = tmp_path / "bundle"
    _write(
        root / "datasets" / "sales.md",
        """
        ---
        type: BigQuery Dataset
        title: Sales
        description: Sales dataset.
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Contains [orders](/tables/orders.md).
        """,
    )
    _write(
        root / "tables" / "orders.md",
        """
        ---
        type: BigQuery Table
        title: Orders
        description: Orders table.
        timestamp: '2026-05-28T00:00:00+00:00'
        ---
        Part of [sales](/datasets/sales.md).
        """,
    )
    b = Bundle.load(root)
    pairs = set(b.edges())
    assert ("datasets/sales", "tables/orders") in pairs
    assert ("tables/orders", "datasets/sales") in pairs


def test_load_raises_when_bundle_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Bundle.load(tmp_path / "nope")
