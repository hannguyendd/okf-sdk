"""FastMCP producer server exposing okf_backend.operations as MCP tools.

One server acts on one workspace (``~/.okf/workspaces/<name>``, home overridable
by ``OKF_HOME``). On stdio the workspace is fixed at startup with
``--workspace NAME``; on streamable-HTTP each request names it with the
``X-OKF-Workspace`` header. Tools take no workspace argument, and every result
echoes the ``workspace`` used.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from okf_backend import operations
from okf_backend.settings import BackendSettings
from okf_core import Workspace, WorkspaceRegistry

WORKSPACE_HEADER = "x-okf-workspace"

mcp = FastMCP("okf-producer")

# Set by ``main`` for stdio; takes precedence over the request header.
_fixed_workspace: str | None = None


def registry() -> WorkspaceRegistry:
    """Workspaces under ``OKF_HOME`` (built per call so the env is honoured)."""
    return WorkspaceRegistry()


def header(ctx, name: str) -> str | None:
    """A request header on the streamable-HTTP transport; ``None`` on stdio."""
    try:
        request = ctx.request_context.request
    except (AttributeError, ValueError, LookupError):
        return None
    headers = getattr(request, "headers", None)
    value = headers.get(name) if headers is not None else None
    return value or None


def _names() -> str:
    return ", ".join(w.name for w in registry().list()) or "(none)"


def workspace(ctx) -> Workspace:
    """The workspace this call acts on: ``--workspace``, else the header."""
    name = _fixed_workspace or header(ctx, WORKSPACE_HEADER)
    if not name:
        raise ValueError(
            "no workspace: start okf-mcp with --workspace <name> (stdio) or send "
            f"the X-OKF-Workspace header (http); workspaces: {_names()}"
        )
    try:
        return registry().get(name)
    except (ValueError, FileNotFoundError):
        raise ValueError(f"unknown workspace '{name}'; workspaces: {_names()}") from None


def _echo(ws: Workspace, result: Any) -> dict:
    if isinstance(result, dict):
        return {**result, "workspace": ws.name}
    return {"workspace": ws.name, "items": result}


@mcp.tool()
async def add(
    ctx: Context,
    concept_id: str,
    frontmatter: dict[str, Any],
    body: str,
) -> dict:
    """Create a new OKF concept document.

    `concept_id` is the workspace-relative path without `.md` (e.g. `tables/orders`).
    `frontmatter` must include a non-empty `type`; recommended keys: `title`,
    `description`, `resource`, `tags`. `timestamp` is set automatically when
    omitted. Fails if the concept already exists. Regenerates indexes and
    appends a Creation entry to the directory's `_log.md`.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.add_concept(ws.storage, concept_id, frontmatter, body))


@mcp.tool()
async def patch(
    ctx: Context,
    concept_id: str,
    frontmatter: dict[str, Any] | None = None,
    body: str | None = None,
) -> dict:
    """Update an existing OKF concept.

    Merges the given `frontmatter` keys (null values are ignored; keys are never
    deleted). Replaces the body only when `body` is provided. `timestamp` is
    refreshed unless you pass one. Fails if the concept does not exist.
    Regenerates indexes and appends an Update entry to `_log.md`.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.patch_concept(ws.storage, concept_id, frontmatter, body))


@mcp.tool()
async def get(
    ctx: Context, concept_id: str
) -> dict:
    """Read one concept: its frontmatter, body, and resolved outgoing links."""
    ws = workspace(ctx)
    return _echo(ws, operations.get_concept(ws.storage, concept_id))


@mcp.tool(name="list")
async def list_(
    ctx: Context,
    type: str | None = None,
    prefix: str | None = None,
) -> dict:
    """List concepts, optionally filtered by exact `type` and/or id `prefix`.

    Returns `{workspace, items: [...]}`.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.list_concepts(ws.storage, type, prefix))


@mcp.tool()
async def read_index(
    ctx: Context,
    dir: str | None = None,
    depth: int = 1,
) -> dict:
    """Read `_index.md` files for progressive disclosure.

    `dir` is a workspace-relative directory (the workspace root if omitted). `depth` (1-3) sets
    how many directory levels of indexes to return, breadth-first. Returns
    `{workspace, items: [...]}`.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.read_index(ws.storage, dir, depth))


@mcp.tool()
async def move(
    ctx: Context,
    from_concept_id: str,
    to_concept_id: str,
) -> dict:
    """Move (rename or relocate) an OKF concept to a new id.

    `from_concept_id`/`to_concept_id` are workspace-relative paths without `.md`
    (e.g. `tables/orders` -> `models/orders`). Fails if the source is missing,
    the destination already exists, or the two ids are equal. Rewrites markdown
    links so that inbound links from other concepts and the moved concept's own
    relative links stay valid, then regenerates indexes and appends a Move entry
    to `_log.md`.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.move_concept(ws.storage, from_concept_id, to_concept_id))


@mcp.tool()
async def delete(
    ctx: Context,
    concept_id: str,
    force: bool = False,
) -> dict:
    """Delete an OKF concept document.

    Safe by default: if other concepts reference `concept_id`, deletes nothing
    and returns `action="blocked"` with `referenced_by` listing them. Pass
    `force=True` to delete anyway -- this unlinks every inbound reference
    (`[label](target.md)` becomes plain `label`), removes the file, regenerates
    indexes, and appends a Deletion entry to `_log.md`. Irreversible. Fails if
    the concept does not exist.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.delete_concept(ws.storage, concept_id, force))


@mcp.tool()
async def reindex(ctx: Context) -> dict:
    """Regenerate every `_index.md` in the workspace from current content.

    Use this to repair indexes that have drifted -- for example after editing
    concept files directly instead of through `add`/`patch`/`move`. Rewrites all
    directory `_index.md` files; does not touch `_log.md`. Returns the
    regenerated index paths (workspace-relative) and their count.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.reindex_bundle(ws.storage))


@mcp.tool()
async def describe(
    ctx: Context,
    dir: str,
    description: str,
) -> dict:
    """Set or clear a directory's authored description.

    Writes `description` into the directory's `_index.md` frontmatter, regenerates
    indexes so it appears in the parent's caption, and appends an Update entry to
    that directory's `_log.md`. Pass an empty string to clear it (reverting to the
    synthesized contents summary). `dir` is a workspace-relative directory that must
    already have an `_index.md`.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.describe_directory(ws.storage, dir, description))


@mcp.tool()
async def mkdir(ctx: Context, dir: str, description: str | None = None) -> dict:
    """Create an empty directory `dir` (workspace-relative) with an optional description.

    Writes the directory's `_index.md` (carrying `description`, which says what
    the directory is for) and appends a Creation entry to its `_log.md`. Fails
    if the directory already exists. Concepts added under a new path create
    their directories automatically; use this to make one ahead of time.
    """
    ws = workspace(ctx)
    return _echo(ws, operations.create_directory(ws.storage, dir, description or ""))


@mcp.tool()
async def search(
    ctx: Context, query: str, top_k: int = 5, paths: list[str] | None = None
) -> dict:
    """Find what is closest in meaning to a natural-language `query` in the workspace.

    Semantic search over the workspace's directory indexes (`_index.md`), to
    locate the right area when you do not know where something lives. `paths`
    optionally limits the search to those workspace-relative directories. Returns
    `{workspace, hits}`; hits are `{kind, dir, path, score, excerpt}`, best
    first, up to `top_k` (1-20). Then go deeper with `read_index` / `list` /
    `get` on a hit's `dir`. Concept bodies are not searched. Needs
    OKF_EMBEDDING_URL and OKF_EMBEDDING_MODEL; the first search after changes
    embeds what changed, so it can be slower.
    """
    backend = BackendSettings()  # read per call so the env is honoured
    ws = workspace(ctx)
    hits = await asyncio.to_thread(
        operations.search_workspace,
        ws,
        query,
        top_k,
        paths,
        config=backend.embedding_config(),
        max_chars=backend.embedding_max_chars,
    )
    return {"workspace": ws.name, "hits": hits}


def main(argv: list[str] | None = None) -> None:
    global _fixed_workspace
    p = argparse.ArgumentParser(prog="okf-mcp", description="OKF producer MCP server")
    p.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    p.add_argument("--workspace", metavar="NAME", help="workspace to serve (stdio only)")
    p.add_argument("--host", default="127.0.0.1", help="HTTP bind address (no auth: keep it local)")
    p.add_argument("--port", type=int, default=8000, help="HTTP port")
    args = p.parse_args(argv)
    if args.transport == "streamable-http":
        if args.workspace:
            raise SystemExit(
                "okf-mcp: --workspace is not used with streamable-http; "
                "send the X-OKF-Workspace header"
            )
        _fixed_workspace = None
    else:
        if not args.workspace:
            raise SystemExit(f"okf-mcp: --workspace is required for stdio; workspaces: {_names()}")
        try:
            registry().get(args.workspace)
        except (ValueError, FileNotFoundError):
            raise SystemExit(
                f"okf-mcp: unknown workspace '{args.workspace}'; workspaces: {_names()}"
            ) from None
        _fixed_workspace = args.workspace
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
