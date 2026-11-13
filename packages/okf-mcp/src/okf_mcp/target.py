"""Resolve which workspace and bundle an MCP tool call acts on.

Each level resolves independently: tool argument > ``X-OKF-*`` request header
(streamable-HTTP) > ``OKF_WORKSPACE``/``OKF_BUNDLE`` env > the pick remembered
for this MCP session > ask the user (MCP elicitation). A level with exactly one
candidate is used without asking. The default workspace and default bundle act
as a pair: the default bundle only applies inside the default workspace (or
when no default workspace is set); likewise for a remembered pick.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass

from mcp import types
from pydantic import Field, create_model

from okf_core import Workspace, WorkspaceRegistry

WORKSPACE_HEADER = "x-okf-workspace"
BUNDLE_HEADER = "x-okf-bundle"

# Picks made in an elicitation prompt, per MCP session; dropped with the session.
_picks: "weakref.WeakKeyDictionary[object, dict[str, str]]" = weakref.WeakKeyDictionary()


class TargetError(ValueError):
    """The workspace or bundle could not be resolved; the message lists choices."""


@dataclass(frozen=True)
class Target:
    workspace: Workspace
    bundle: str | None


def header(ctx, name: str) -> str | None:
    """A request header on the streamable-HTTP transport; ``None`` on stdio."""
    try:
        request = ctx.request_context.request
    except (AttributeError, ValueError, LookupError):
        return None
    headers = getattr(request, "headers", None)
    value = headers.get(name) if headers is not None else None
    return value or None


def _choices(names: list[str]) -> str:
    return ", ".join(names) or "(none)"


def _can_elicit(ctx) -> bool:
    try:
        return bool(
            ctx.session.check_client_capability(
                types.ClientCapabilities(elicitation=types.ElicitationCapability())
            )
        )
    except Exception:
        return False


async def _ask(ctx, kind: str, names: list[str], message: str) -> str:
    refusal = TargetError(f"no {kind} chosen; pass {kind}= one of: {_choices(names)}")
    if not _can_elicit(ctx):
        raise refusal
    schema = create_model(
        f"Pick{kind.capitalize()}",
        choice=(str, Field(description=f"The {kind} to use", json_schema_extra={"enum": names})),
    )
    result = await ctx.elicit(message, schema)
    if getattr(result, "action", None) != "accept" or result.data is None:
        raise refusal
    choice = result.data.choice
    if choice not in names:
        raise refusal
    return choice


def _session_picks(ctx) -> dict[str, str] | None:
    try:
        return _picks.setdefault(ctx.session, {})
    except TypeError:  # session not weak-referenceable: just don't remember
        return None


async def resolve_target(
    ctx,
    registry: WorkspaceRegistry,
    *,
    workspace: str | None,
    bundle: str | None,
    need_bundle: bool,
    env_workspace: str | None,
    env_bundle: str | None,
) -> Target:
    """Resolve the target of a tool call (see module docstring).

    With ``need_bundle`` false the bundle is only taken from the argument or a
    default, never asked for, and may be ``None``.
    """
    picks = _session_picks(ctx)
    remembered = picks or {}

    default_ws = header(ctx, WORKSPACE_HEADER) or env_workspace
    names = [w.name for w in registry.list()]
    ws_name = workspace or default_ws or remembered.get("workspace")
    if ws_name is not None:
        if ws_name not in names:
            raise TargetError(f"no workspace {ws_name!r}; workspaces: {_choices(names)}")
    elif not names:
        raise TargetError(
            "no workspaces exist; create one first (workspaces are created by a person, "
            "not over MCP)"
        )
    elif len(names) == 1:
        ws_name = names[0]
    else:
        ws_name = await _ask(ctx, "workspace", names, "Which OKF workspace should I use?")
        if picks is not None:
            if picks.get("workspace") != ws_name:
                picks.pop("bundle", None)
            picks["workspace"] = ws_name
    ws = registry.get(ws_name)

    bundles = ws.indexes()
    default_bundle = header(ctx, BUNDLE_HEADER) or env_bundle
    if default_ws is not None and ws_name != default_ws:
        default_bundle = None
    remembered_bundle = (
        remembered.get("bundle") if remembered.get("workspace") == ws_name else None
    )
    b_name = bundle or default_bundle
    if b_name is None and need_bundle:
        b_name = remembered_bundle
    if b_name is not None:
        if b_name not in bundles:
            raise TargetError(
                f"no bundle {b_name!r} in workspace {ws_name!r}; bundles: {_choices(bundles)}"
            )
        return Target(ws, b_name)
    if not need_bundle:
        return Target(ws, None)
    if not bundles:
        raise TargetError(
            f"workspace {ws_name!r} has no bundles; call create_bundle to make one"
        )
    if len(bundles) == 1:
        return Target(ws, bundles[0])
    lines = [
        f"- {i['name']} — {i['description']}" if i["description"] else f"- {i['name']}"
        for i in ws.bundles_info()
    ]
    message = f"Which bundle in workspace {ws_name!r} should I use?\n" + "\n".join(lines)
    b_name = await _ask(ctx, "bundle", bundles, message)
    if picks is not None:
        picks["workspace"], picks["bundle"] = ws_name, b_name
    return Target(ws, b_name)
