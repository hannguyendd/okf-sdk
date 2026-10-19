"""FastMCP producer server exposing okf_mcp.operations as MCP tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

from okf_core import Storage
from mcp.server.fastmcp import Context, FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict

from okf_mcp import operations


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OKF_", env_file=".env", extra="ignore"
    )

    # Locations: a local path, or a ``scheme://`` URI for a registered storage
    # backend (see ``okf_core.open_storage``). Kept as ``str`` so URIs survive.
    bundle_root: str | None = None
    store_root: str | None = None


settings = Settings()
mcp = FastMCP("okf-producer")


def _uri_to_path(uri: object) -> Path | None:
    """Convert a ``file://`` root URI to a local path; ``None`` if not a file URI."""
    parsed = urlparse(str(uri))
    if parsed.scheme != "file":
        return None
    path = url2pathname(parsed.path)
    return Path(path) if path else None


async def _project_root(ctx: Context) -> Path:
    """Discover the current project directory from the client's MCP roots.

    Returns the first ``file://`` root the client advertises; falls back to the
    process working directory when the client sends no usable roots or lacks the
    ``roots`` capability.
    """
    try:
        result = await ctx.session.list_roots()
        roots = result.roots or []
    except Exception:
        roots = []
    for root in roots:
        path = _uri_to_path(root.uri)
        if path is not None:
            return path
    return Path.cwd()


async def _root(bundle_root: str | None, ctx: Context) -> Path | Storage:
    """Resolve the effective bundle root for a tool call.

    Precedence: an explicit ``bundle_root`` arg wins; otherwise store mode
    (``OKF_STORE_ROOT``) partitions per project into ``<store_root>/<project-folder>``;
    otherwise the legacy single bundle (``OKF_BUNDLE_ROOT``). Setting both env
    roots (with no arg) is an error. Each is a local path or a ``scheme://``
    storage location; local paths resolve to ``Path`` and others to ``Storage``.
    """
    if bundle_root:
        return operations.resolve_bundle_root(bundle_root, None)
    if settings.store_root and settings.bundle_root:
        raise ValueError("set OKF_STORE_ROOT or OKF_BUNDLE_ROOT, not both")
    if settings.store_root:
        project = await _project_root(ctx)
        return operations.resolve_store_bundle_root(settings.store_root, project)
    return operations.resolve_bundle_root(None, settings.bundle_root)


@mcp.tool()
async def add(
    ctx: Context,
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
    appends a Creation entry to the directory's `_log.md`.
    """
    return operations.add_concept(
        await _root(bundle_root, ctx), concept_id, frontmatter, body
    )


@mcp.tool()
async def patch(
    ctx: Context,
    concept_id: str,
    frontmatter: dict[str, Any] | None = None,
    body: str | None = None,
    bundle_root: str | None = None,
) -> dict:
    """Update an existing OKF concept.

    Merges the given `frontmatter` keys (null values are ignored; keys are never
    deleted). Replaces the body only when `body` is provided. `timestamp` is
    refreshed unless you pass one. Fails if the concept does not exist.
    Regenerates indexes and appends an Update entry to `_log.md`.
    """
    return operations.patch_concept(
        await _root(bundle_root, ctx), concept_id, frontmatter, body
    )


@mcp.tool()
async def get(ctx: Context, concept_id: str, bundle_root: str | None = None) -> dict:
    """Read one concept: its frontmatter, body, and resolved outgoing links."""
    return operations.get_concept(await _root(bundle_root, ctx), concept_id)


@mcp.tool(name="list")
async def list_(
    ctx: Context,
    type: str | None = None,
    prefix: str | None = None,
    bundle_root: str | None = None,
) -> list[dict]:
    """List concepts, optionally filtered by exact `type` and/or id `prefix`."""
    return operations.list_concepts(await _root(bundle_root, ctx), type, prefix)


@mcp.tool()
async def read_index(
    ctx: Context,
    dir: str | None = None,
    depth: int = 1,
    bundle_root: str | None = None,
) -> list[dict]:
    """Read `_index.md` files for progressive disclosure.

    `dir` is a bundle-relative directory (root if omitted). `depth` (1-3) sets
    how many directory levels of indexes to return, breadth-first.
    """
    return operations.read_index(await _root(bundle_root, ctx), dir, depth)


@mcp.tool()
async def move(
    ctx: Context,
    from_concept_id: str,
    to_concept_id: str,
    bundle_root: str | None = None,
) -> dict:
    """Move (rename or relocate) an OKF concept to a new id.

    `from_concept_id`/`to_concept_id` are bundle-relative paths without `.md`
    (e.g. `tables/orders` -> `models/orders`). Fails if the source is missing,
    the destination already exists, or the two ids are equal. Rewrites markdown
    links so that inbound links from other concepts and the moved concept's own
    relative links stay valid, then regenerates indexes and appends a Move entry
    to `_log.md`.
    """
    return operations.move_concept(
        await _root(bundle_root, ctx), from_concept_id, to_concept_id
    )


@mcp.tool()
async def delete(
    ctx: Context,
    concept_id: str,
    force: bool = False,
    bundle_root: str | None = None,
) -> dict:
    """Delete an OKF concept document.

    Safe by default: if other concepts reference `concept_id`, deletes nothing
    and returns `action="blocked"` with `referenced_by` listing them. Pass
    `force=True` to delete anyway -- this unlinks every inbound reference
    (`[label](target.md)` becomes plain `label`), removes the file, regenerates
    indexes, and appends a Deletion entry to `_log.md`. Irreversible. Fails if
    the concept does not exist.
    """
    return operations.delete_concept(await _root(bundle_root, ctx), concept_id, force)


@mcp.tool()
async def reindex(ctx: Context, bundle_root: str | None = None) -> dict:
    """Regenerate every `_index.md` in the bundle from current content.

    Use this to repair indexes that have drifted -- for example after editing
    concept files directly instead of through `add`/`patch`/`move`. Rewrites all
    directory `_index.md` files; does not touch `_log.md`. Returns the
    regenerated index paths (bundle-relative) and their count.
    """
    return operations.reindex_bundle(await _root(bundle_root, ctx))


@mcp.tool()
async def describe(
    ctx: Context,
    dir: str,
    description: str,
    bundle_root: str | None = None,
) -> dict:
    """Set or clear a directory's authored description.

    Writes `description` into the directory's `_index.md` frontmatter, regenerates
    indexes so it appears in the parent's caption, and appends an Update entry to
    that directory's `_log.md`. Pass an empty string to clear it (reverting to the
    synthesized contents summary). `dir` is a bundle-relative directory that must
    already have an `_index.md`.
    """
    return operations.describe_directory(await _root(bundle_root, ctx), dir, description)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
