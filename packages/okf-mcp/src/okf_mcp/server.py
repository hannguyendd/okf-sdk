"""FastMCP producer server exposing okf_mcp.operations as MCP tools."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict

from okf_mcp import operations


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OKF_")

    bundle_root: Path | None = None


settings = Settings()
mcp = FastMCP("okf-producer")


def _root(bundle_root: str | None) -> Path:
    return operations.resolve_bundle_root(bundle_root, settings.bundle_root)


@mcp.tool()
def add(
    concept_id: str,
    frontmatter: dict[str, Any],
    body: str,
    bundle_root: str | None = None,
) -> dict:
    """Create a new OKF concept document.

    `concept_id` is the bundle-relative path without `.md` (e.g. `tables/orders`).
    `frontmatter` must include a non-empty `type`; recommended keys: `title`,
    `description`, `resource`, `tags`. `timestamp` is set automatically when
    omitted. Fails if the concept already exists. Regenerates indexes and
    appends a Creation entry to the directory's `log.md`.
    """
    return operations.add_concept(_root(bundle_root), concept_id, frontmatter, body)


@mcp.tool()
def patch(
    concept_id: str,
    frontmatter: dict[str, Any] | None = None,
    body: str | None = None,
    bundle_root: str | None = None,
) -> dict:
    """Update an existing OKF concept.

    Merges the given `frontmatter` keys (null values are ignored; keys are never
    deleted). Replaces the body only when `body` is provided. `timestamp` is
    refreshed unless you pass one. Fails if the concept does not exist.
    Regenerates indexes and appends an Update entry to `log.md`.
    """
    return operations.patch_concept(_root(bundle_root), concept_id, frontmatter, body)


@mcp.tool()
def get(concept_id: str, bundle_root: str | None = None) -> dict:
    """Read one concept: its frontmatter, body, and resolved outgoing links."""
    return operations.get_concept(_root(bundle_root), concept_id)


@mcp.tool(name="list")
def list_(
    type: str | None = None,
    prefix: str | None = None,
    bundle_root: str | None = None,
) -> list[dict]:
    """List concepts, optionally filtered by exact `type` and/or id `prefix`."""
    return operations.list_concepts(_root(bundle_root), type, prefix)


@mcp.tool()
def read_index(
    dir: str | None = None,
    depth: int = 1,
    bundle_root: str | None = None,
) -> list[dict]:
    """Read `index.md` files for progressive disclosure.

    `dir` is a bundle-relative directory (root if omitted). `depth` (1-3) sets
    how many directory levels of indexes to return, breadth-first.
    """
    return operations.read_index(_root(bundle_root), dir, depth)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
