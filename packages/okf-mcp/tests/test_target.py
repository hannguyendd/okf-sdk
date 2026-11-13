import asyncio
from types import SimpleNamespace

import pytest

from okf_core import WorkspaceRegistry

from okf_mcp.target import TargetError, header, resolve_target


class _Session:
    """Weak-referenceable stand-in for the MCP ServerSession."""

    def __init__(self, elicitation: bool = True):
        self.elicitation = elicitation

    def check_client_capability(self, capability) -> bool:
        return self.elicitation


class _Ctx:
    """Fake FastMCP Context: a session, optional HTTP headers, scripted elicit answers."""

    def __init__(self, session=None, headers=None, answers=()):
        self.session = session or _Session()
        request = SimpleNamespace(headers=headers) if headers is not None else None
        self.request_context = SimpleNamespace(request=request)
        self.answers = list(answers)
        self.prompts: list[tuple[str, type]] = []

    async def elicit(self, message, schema):
        self.prompts.append((message, schema))
        action, choice = self.answers.pop(0)
        data = schema(choice=choice) if action == "accept" else None
        return SimpleNamespace(action=action, data=data)


def _registry(tmp_path, layout):
    """``layout``: {workspace: {bundle: description}}."""
    reg = WorkspaceRegistry(tmp_path)
    for ws_name, bundles in layout.items():
        ws = reg.create(ws_name)
        for b, d in bundles.items():
            ws.create_index(b, d)
    return reg


def _resolve(ctx, reg, *, workspace=None, bundle=None, need_bundle=True, env_ws=None, env_b=None):
    return asyncio.run(
        resolve_target(
            ctx, reg, workspace=workspace, bundle=bundle, need_bundle=need_bundle,
            env_workspace=env_ws, env_bundle=env_b,
        )
    )


def _names(t):
    return (t.workspace.name, t.bundle)


def test_arg_beats_header_beats_env(tmp_path):
    reg = _registry(tmp_path, {"A": {"x": None, "y": None}, "B": {"x": None, "y": None}, "C": {"x": None}})
    hdr = {"x-okf-workspace": "B", "x-okf-bundle": "y"}
    assert _names(_resolve(_Ctx(headers=hdr), reg, workspace="C", bundle="x", env_ws="A", env_b="x")) == ("C", "x")
    assert _names(_resolve(_Ctx(headers=hdr), reg, env_ws="A", env_b="x")) == ("B", "y")
    assert _names(_resolve(_Ctx(), reg, env_ws="A", env_b="y")) == ("A", "y")


def test_single_workspace_and_single_bundle_auto_picked_without_prompt(tmp_path):
    reg = _registry(tmp_path, {"only": {"one": None}})
    ctx = _Ctx()
    assert _names(_resolve(ctx, reg)) == ("only", "one")
    reg.create("second").create_index("z")
    ctx.answers = [("accept", "second")]
    assert _names(_resolve(ctx, reg)) == ("second", "z")  # nothing remembered: asked now
    assert len(ctx.prompts) == 1


def test_elicits_workspace_then_bundle_and_remembers(tmp_path):
    reg = _registry(tmp_path, {"A": {"x": "X data", "y": "Y data"}, "B": {"z": None}})
    ctx = _Ctx(answers=[("accept", "A"), ("accept", "y")])
    assert _names(_resolve(ctx, reg)) == ("A", "y")
    assert len(ctx.prompts) == 2
    bundle_message, bundle_schema = ctx.prompts[1]
    assert "x — X data" in bundle_message and "y — Y data" in bundle_message
    assert bundle_schema.model_json_schema()["properties"]["choice"]["enum"] == ["x", "y"]
    assert _names(_resolve(ctx, reg)) == ("A", "y")
    assert len(ctx.prompts) == 2  # remembered: no new prompt


def test_picks_are_per_session(tmp_path):
    reg = _registry(tmp_path, {"A": {"x": None}, "B": {"z": None}})
    first = _Ctx(answers=[("accept", "A")])
    _resolve(first, reg)
    other = _Ctx(answers=[("accept", "B")])
    assert _names(_resolve(other, reg)) == ("B", "z")
    assert len(other.prompts) == 1


def test_remembered_bundle_belongs_to_its_workspace(tmp_path):
    reg = _registry(tmp_path, {"A": {"x": None, "y": None}, "B": {"x": None, "z": None}})
    ctx = _Ctx(answers=[("accept", "A"), ("accept", "x"), ("accept", "z")])
    _resolve(ctx, reg)
    assert _names(_resolve(ctx, reg, workspace="B")) == ("B", "z")  # A's "x" not reused in B
    assert len(ctx.prompts) == 3


def test_default_bundle_ignored_for_other_workspace(tmp_path):
    reg = _registry(tmp_path, {"A": {"notes": None}, "B": {"notes": None, "other": None}})
    ctx = _Ctx(answers=[("accept", "other")])
    assert _names(_resolve(ctx, reg, workspace="B", env_ws="A", env_b="notes")) == ("B", "other")
    assert len(ctx.prompts) == 1


def test_default_bundle_applies_when_no_default_workspace(tmp_path):
    reg = _registry(tmp_path, {"A": {"notes": None, "x": None}, "B": {"y": None}})
    assert _names(_resolve(_Ctx(), reg, workspace="A", env_b="notes")) == ("A", "notes")


def test_named_missing_workspace_or_bundle_errors_without_prompt(tmp_path):
    reg = _registry(tmp_path, {"A": {"x": None, "y": None}, "B": {"z": None}})
    ctx = _Ctx()
    with pytest.raises(TargetError, match="A, B"):
        _resolve(ctx, reg, workspace="nope")
    with pytest.raises(TargetError, match="x, y"):
        _resolve(ctx, reg, workspace="A", bundle="nope")
    with pytest.raises(TargetError):
        _resolve(ctx, reg, workspace="A", env_b="nope")
    assert ctx.prompts == []


@pytest.mark.parametrize("action", ["decline", "cancel"])
def test_decline_or_cancel_raises_with_choices(tmp_path, action):
    reg = _registry(tmp_path, {"A": {"x": None}, "B": {"z": None}})
    with pytest.raises(TargetError, match="workspace=.*A, B"):
        _resolve(_Ctx(answers=[(action, None)]), reg)


def test_no_elicitation_capability_raises_with_choices(tmp_path):
    reg = _registry(tmp_path, {"A": {"x": None, "y": None}})
    ctx = _Ctx(session=_Session(elicitation=False))
    with pytest.raises(TargetError, match="bundle=.*x, y"):
        _resolve(ctx, reg)
    assert ctx.prompts == []


def test_answer_not_in_choices_rejected(tmp_path):
    reg = _registry(tmp_path, {"A": {"x": None}, "B": {"z": None}})
    with pytest.raises(TargetError, match="A, B"):
        _resolve(_Ctx(answers=[("accept", "../etc")]), reg)


def test_no_workspaces_error_mentions_creation(tmp_path):
    with pytest.raises(TargetError, match="no workspaces"):
        _resolve(_Ctx(), WorkspaceRegistry(tmp_path / "none"))


def test_no_bundles_error_mentions_create_bundle(tmp_path):
    reg = _registry(tmp_path, {"A": {}})
    with pytest.raises(TargetError, match="create_bundle"):
        _resolve(_Ctx(), reg)


def test_need_bundle_false_never_prompts_for_bundle(tmp_path):
    reg = _registry(tmp_path, {"A": {"x": None, "y": None}})
    ctx = _Ctx()
    assert _names(_resolve(ctx, reg, need_bundle=False)) == ("A", None)
    assert _names(_resolve(ctx, reg, need_bundle=False, env_b="y")) == ("A", "y")
    assert ctx.prompts == []


def test_header_reads_request_headers_and_none_on_stdio():
    assert header(_Ctx(headers={"x-okf-workspace": "w"}), "x-okf-workspace") == "w"
    assert header(_Ctx(), "x-okf-workspace") is None
    assert header(SimpleNamespace(), "x-okf-workspace") is None
