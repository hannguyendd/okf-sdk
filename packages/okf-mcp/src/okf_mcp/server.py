"""FastMCP producer server exposing okf_mcp.operations as MCP tools.

Every tool acts on a bundle inside a workspace (``~/.okf/workspaces/<ws>/<bundle>``,
home overridable by ``OKF_HOME``). ``workspace``/``bundle`` are optional on every
tool: they default from the ``X-OKF-Workspace``/``X-OKF-Bundle`` request headers
(streamable-HTTP), then ``OKF_WORKSPACE``/``OKF_BUNDLE``, then the pick remembered
for this session, and otherwise the user is asked (see ``okf_mcp.target``).
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict

from okf_core import Storage, WorkspaceRegistry

from okf_mcp import operations
from okf_mcp.embeddings import EmbeddingConfig
from okf_mcp.target import Target, resolve_target


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OKF_", env_file=".env", extra="ignore"
    )

    # Default target (overridden per call by tool args or request headers).
    workspace: str | None = None
    bundle: str | None = None

    # Semantic search (``search`` tool). Only the tool needs these; leave unset to
    # keep it disabled. ``embedding_url`` is an OpenAI-compatible base URL
    # including any ``/v1`` prefix. Vectors live in ``<workspace>/.okf/vectors.db``.
    embedding_url: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_max_chars: int = 6000


settings = Settings()
mcp = FastMCP("okf-producer")

_TARGET_DOC = """

    `workspace`/`bundle` are optional: when omitted they come from the client's
    defaults, or the user is asked. The result names the `workspace` and `bundle`
    used; pass them explicitly on later calls."""


def registry() -> WorkspaceRegistry:
    """Workspaces under ``OKF_HOME`` (built per call so the env is honoured)."""
    return WorkspaceRegistry()


async def _target(
    ctx: Context, workspace: str | None, bundle: str | None, *, need_bundle: bool = True
) -> Target:
    return await resolve_target(
        ctx,
        registry(),
        workspace=workspace,
        bundle=bundle,
        need_bundle=need_bundle,
        env_workspace=settings.workspace,
        env_bundle=settings.bundle,
    )


async def _bundle(
    ctx: Context, workspace: str | None, bundle: str | None
) -> tuple[Target, Storage]:
    target = await _target(ctx, workspace, bundle)
    return target, target.workspace.bundle_storage(target.bundle)


def _echo(target: Target, result: Any) -> dict:
    where = {"workspace": target.workspace.name, "bundle": target.bundle}
    if isinstance(result, dict):
        return {**result, **where}
    return {**where, "items": result}


def _with_target_doc(fn):
    fn.__doc__ = (fn.__doc__ or "").rstrip() + _TARGET_DOC
    return fn


@mcp.tool()
@_with_target_doc
async def add(
    ctx: Context,
    concept_id: str,
    frontmatter: dict[str, Any],
    body: str,
    workspace: str | None = None,
    bundle: str | None = None,
) -> dict:
    """Create a new OKF concept document.

    `concept_id` is the bundle-relative path without `.md` (e.g. `tables/orders`).
    `frontmatter` must include a non-empty `type`; recommended keys: `title`,
    `description`, `resource`, `tags`. `timestamp` is set automatically when
    omitted. Fails if the concept already exists. Regenerates indexes and
    appends a Creation entry to the directory's `_log.md`.
    """
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.add_concept(storage, concept_id, frontmatter, body))


@mcp.tool()
@_with_target_doc
async def patch(
    ctx: Context,
    concept_id: str,
    frontmatter: dict[str, Any] | None = None,
    body: str | None = None,
    workspace: str | None = None,
    bundle: str | None = None,
) -> dict:
    """Update an existing OKF concept.

    Merges the given `frontmatter` keys (null values are ignored; keys are never
    deleted). Replaces the body only when `body` is provided. `timestamp` is
    refreshed unless you pass one. Fails if the concept does not exist.
    Regenerates indexes and appends an Update entry to `_log.md`.
    """
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.patch_concept(storage, concept_id, frontmatter, body))


@mcp.tool()
@_with_target_doc
async def get(
    ctx: Context, concept_id: str, workspace: str | None = None, bundle: str | None = None
) -> dict:
    """Read one concept: its frontmatter, body, and resolved outgoing links."""
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.get_concept(storage, concept_id))


@mcp.tool(name="list")
@_with_target_doc
async def list_(
    ctx: Context,
    type: str | None = None,
    prefix: str | None = None,
    workspace: str | None = None,
    bundle: str | None = None,
) -> dict:
    """List concepts, optionally filtered by exact `type` and/or id `prefix`.

    Returns `{workspace, bundle, items: [...]}`.
    """
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.list_concepts(storage, type, prefix))


@mcp.tool()
@_with_target_doc
async def read_index(
    ctx: Context,
    dir: str | None = None,
    depth: int = 1,
    workspace: str | None = None,
    bundle: str | None = None,
) -> dict:
    """Read `_index.md` files for progressive disclosure.

    `dir` is a bundle-relative directory (root if omitted). `depth` (1-3) sets
    how many directory levels of indexes to return, breadth-first. Returns
    `{workspace, bundle, items: [...]}`.
    """
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.read_index(storage, dir, depth))


@mcp.tool()
@_with_target_doc
async def move(
    ctx: Context,
    from_concept_id: str,
    to_concept_id: str,
    workspace: str | None = None,
    bundle: str | None = None,
) -> dict:
    """Move (rename or relocate) an OKF concept to a new id.

    `from_concept_id`/`to_concept_id` are bundle-relative paths without `.md`
    (e.g. `tables/orders` -> `models/orders`). Fails if the source is missing,
    the destination already exists, or the two ids are equal. Rewrites markdown
    links so that inbound links from other concepts and the moved concept's own
    relative links stay valid, then regenerates indexes and appends a Move entry
    to `_log.md`.
    """
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.move_concept(storage, from_concept_id, to_concept_id))


@mcp.tool()
@_with_target_doc
async def delete(
    ctx: Context,
    concept_id: str,
    force: bool = False,
    workspace: str | None = None,
    bundle: str | None = None,
) -> dict:
    """Delete an OKF concept document.

    Safe by default: if other concepts reference `concept_id`, deletes nothing
    and returns `action="blocked"` with `referenced_by` listing them. Pass
    `force=True` to delete anyway -- this unlinks every inbound reference
    (`[label](target.md)` becomes plain `label`), removes the file, regenerates
    indexes, and appends a Deletion entry to `_log.md`. Irreversible. Fails if
    the concept does not exist.
    """
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.delete_concept(storage, concept_id, force))


@mcp.tool()
@_with_target_doc
async def reindex(
    ctx: Context, workspace: str | None = None, bundle: str | None = None
) -> dict:
    """Regenerate every `_index.md` in the bundle from current content.

    Use this to repair indexes that have drifted -- for example after editing
    concept files directly instead of through `add`/`patch`/`move`. Rewrites all
    directory `_index.md` files; does not touch `_log.md`. Returns the
    regenerated index paths (bundle-relative) and their count.
    """
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.reindex_bundle(storage))


@mcp.tool()
@_with_target_doc
async def describe(
    ctx: Context,
    dir: str,
    description: str,
    workspace: str | None = None,
    bundle: str | None = None,
) -> dict:
    """Set or clear a directory's authored description.

    Writes `description` into the directory's `_index.md` frontmatter, regenerates
    indexes so it appears in the parent's caption, and appends an Update entry to
    that directory's `_log.md`. Pass an empty string to clear it (reverting to the
    synthesized contents summary). `dir` is a bundle-relative directory that must
    already have an `_index.md`.
    """
    t, storage = await _bundle(ctx, workspace, bundle)
    return _echo(t, operations.describe_directory(storage, dir, description))


@mcp.tool()
async def search(
    ctx: Context,
    query: str,
    top_k: int = 5,
    bundles: list[str] | None = None,
    dir: str | None = None,
    workspace: str | None = None,
) -> dict:
    """Find what is closest in meaning to a natural-language `query` across a workspace.

    Semantic search over every bundle's directory indexes (`_index.md`) and over
    the bundles' own descriptions, to locate the right bundle and area when you
    do not know where something lives. Searches every bundle of the workspace
    unless `bundles` lists some (or a default bundle is configured). Returns
    `{workspace, bundles, hits}`; hits are `{bundle, kind, dir, path, score,
    excerpt}`, best first, up to `top_k` (1-20) in total. `kind` is `index` for
    an `_index.md` hit and `bundle` for a bundle-description hit (`path` null).
    `dir` narrows to a subdirectory and needs exactly one bundle. Then go deeper:
    `read_index` / `list` / `get` with that hit's `bundle` and `dir`. Concept
    bodies are not searched. Needs OKF_EMBEDDING_URL and OKF_EMBEDDING_MODEL; the
    first search after changes embeds what changed, so it can be slower.
    `workspace` is optional (defaults, else the user is asked).
    """
    config = (
        EmbeddingConfig(
            url=settings.embedding_url,
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
        )
        if settings.embedding_url and settings.embedding_model
        else None
    )
    target = await _target(ctx, workspace, None, need_bundle=False)
    ws = target.workspace
    scope = bundles if bundles is not None else (
        [target.bundle] if target.bundle else ws.indexes()
    )
    hits = await asyncio.to_thread(
        operations.search_workspace,
        ws,
        query,
        top_k,
        scope,
        dir,
        config=config,
        max_chars=settings.embedding_max_chars,
    )
    return {"workspace": ws.name, "bundles": scope, "hits": hits}


@mcp.tool()
async def list_workspaces() -> list[dict]:
    """List the OKF workspaces as `[{name, bundles}]` (`bundles` = how many).

    Workspaces are created by a person, not over MCP. Use `list_bundles` to see
    what each bundle in a workspace is for.
    """
    return [{"name": w.name, "bundles": len(w.indexes())} for w in registry().list()]


@mcp.tool()
async def list_bundles(ctx: Context, workspace: str | None = None) -> dict:
    """List a workspace's bundles with what each is for.

    Returns `{workspace, bundles: [{name, description}]}`; `description` is null
    when none was set (see `describe_bundle`). Pick the bundle whose description
    fits, then pass it as `bundle` to other tools. `workspace` is optional
    (defaults, else the user is asked).
    """
    target = await _target(ctx, workspace, None, need_bundle=False)
    return {"workspace": target.workspace.name, "bundles": target.workspace.bundles_info()}


@mcp.tool()
async def create_bundle(
    ctx: Context, name: str, description: str | None = None, workspace: str | None = None
) -> dict:
    """Create a new, empty bundle `name` in a workspace, with an optional description.

    The `description` (max 1000 chars) says what the bundle is for, so agents
    can choose it later. Fails if the bundle exists. Names start with a letter
    or digit and use only letters, digits, `.`, `_`, `-`. Returns `{workspace,
    bundle, description}`. `workspace` is optional (defaults, else the user is
    asked). Workspaces themselves cannot be created here.
    """
    target = await _target(ctx, workspace, None, need_bundle=False)
    result = operations.create_bundle(target.workspace, name, description)
    return {"workspace": target.workspace.name, **result}


@mcp.tool()
@_with_target_doc
async def describe_bundle(
    ctx: Context,
    description: str | None,
    bundle: str | None = None,
    workspace: str | None = None,
) -> dict:
    """Set or clear what a bundle is for (its description, max 1000 chars).

    Pass null or an empty string to clear it. Returns `{workspace, bundle,
    description}`. This is the bundle-level description shown by `list_bundles`
    and matched by `search`; for a directory inside a bundle use `describe`.
    """
    target = await _target(ctx, workspace, bundle)
    stored = target.workspace.set_description(target.bundle, description)
    return {"workspace": target.workspace.name, "bundle": target.bundle, "description": stored}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="okf-mcp", description="OKF producer MCP server")
    p.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    p.add_argument("--host", default="127.0.0.1", help="HTTP bind address (no auth: keep it local)")
    p.add_argument("--port", type=int, default=8000, help="HTTP port")
    args = p.parse_args(argv)
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
