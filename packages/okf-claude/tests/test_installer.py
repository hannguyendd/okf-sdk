import json
import subprocess

import pytest
from okf_core import WorkspaceRegistry

from okf_claude import installer
from okf_claude.installer import InstallConfig


class FakeRun:
    def __init__(self, add_rc=0):
        self.calls = []
        self.add_rc = add_rc

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        rc = self.add_rc if cmd[2] == "add" else 0
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="boom" if rc else "")


@pytest.fixture
def cfg(tmp_path, okf_home, monkeypatch):
    monkeypatch.setattr(installer, "_bin", lambda name: f"/venv/bin/{name}")
    return InstallConfig(project=tmp_path / "proj", workspaces=["team"], home=tmp_path / "home")


def test_settings_paths_per_scope(cfg, tmp_path):
    assert cfg.settings_path == cfg.project / ".claude" / "settings.local.json"
    cfg.scope = "project"
    assert cfg.settings_path == cfg.project / ".claude" / "settings.json"
    cfg.scope = "user"
    assert cfg.settings_path == tmp_path / "home" / ".claude" / "settings.json"
    assert cfg.commands_dir == tmp_path / "home" / ".claude" / "commands"


def test_bad_scope_rejected(tmp_path):
    with pytest.raises(ValueError):
        InstallConfig(project=tmp_path, scope="global")


def test_merge_hooks_keeps_foreign_and_is_idempotent():
    settings = {"model": "x", "hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "other-tool"},
                   {"type": "command", "command": "/old/okf-claude hook session-start -w a"}]}]}}
    cmds = {"SessionStart": "/v/okf-claude hook session-start", "SessionEnd": "/v/okf-claude hook session-end"}
    once = installer.merge_hooks(json.loads(json.dumps(settings)), cmds)
    twice = installer.merge_hooks(json.loads(json.dumps(once)), cmds)
    assert once == twice
    starts = once["hooks"]["SessionStart"]
    assert starts[0]["hooks"] == [{"type": "command", "command": "other-tool"}]
    assert starts[1]["hooks"][0]["command"] == "/v/okf-claude hook session-start"
    assert once["model"] == "x"


def test_remove_hooks_drops_empty_events():
    settings = {"hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": "x/okf-claude hook session-end"}]}]}}
    assert installer.remove_hooks(settings) == {}


def test_hook_command_quotes_args(cfg):
    cfg.workspaces = ["my ws"]
    cmd = installer.hook_command(cfg, "SessionStart", "/v/okf-claude")
    assert cmd == "/v/okf-claude hook session-start --workspace 'my ws' --recent 5"
    assert installer.hook_command(cfg, "SessionEnd", "/v/okf-claude").endswith("--model haiku")


def test_ensure_target_creates_or_refuses(okf_home):
    with pytest.raises(FileNotFoundError):
        installer.ensure_target("team", create=False)
    assert installer.ensure_target("team", create=True) == ["created workspace 'team'"]
    assert installer.ensure_target("team", create=False) == []
    assert WorkspaceRegistry().exists("team")


def test_mcp_add_pins_workspace_by_parameter(cfg):
    run = FakeRun()
    installer.register_servers(cfg, run)
    argv = run.calls[1]
    assert argv[-3:] == ["/venv/bin/okf-mcp", "--workspace", "team"]
    assert not any("OKF_BUNDLE" in a or "OKF_WORKSPACE" in a for a in argv)


def test_install_and_uninstall_roundtrip(cfg):
    run = FakeRun()
    cfg.server_env = {"OKF_EMBEDDING_URL": "http://localhost:1234/v1"}
    done = installer.install(cfg, run=run)
    assert any("registered MCP server" in d for d in done)

    add = run.calls[1]
    assert add[:6] == ["claude", "mcp", "add", "--scope", "local", "okf"]
    assert add[6:] == ["-e", "OKF_EMBEDDING_URL=http://localhost:1234/v1", "--", "/venv/bin/okf-mcp",
                       "--workspace", "team"]

    settings = json.loads(cfg.settings_path.read_text())
    assert set(settings["hooks"]) == {"SessionStart", "SessionEnd"}
    assert (cfg.commands_dir / "okf-remember.md").read_text().startswith("---\ndescription:")
    assert (cfg.commands_dir / "okf-recall.md").exists()

    installer.install(cfg, run=run)  # idempotent
    settings = json.loads(cfg.settings_path.read_text())
    assert len(settings["hooks"]["SessionStart"]) == 1

    installer.uninstall(cfg, run=run)
    assert json.loads(cfg.settings_path.read_text()) == {}
    assert not (cfg.commands_dir / "okf-remember.md").exists()
    assert run.calls[-1][:3] == ["claude", "mcp", "remove"]


def test_install_reports_mcp_failure(cfg):
    with pytest.raises(RuntimeError, match="boom"):
        installer.install(cfg, run=FakeRun(add_rc=1))


def test_install_without_mcp(cfg):
    run = FakeRun()
    installer.install(cfg, mcp=False, run=run)
    assert run.calls == []


def test_server_names_single_vs_several():
    from okf_claude.servers import server_names

    assert server_names(["team"]) == {"team": "okf"}
    assert server_names(["team", "team"]) == {"team": "okf"}
    assert server_names(["backend", "my.notes"]) == {"backend": "okf-backend", "my.notes": "okf-my-notes"}
    with pytest.raises(ValueError, match="share MCP server name"):
        server_names(["a.b", "a-b"])


def test_episodes_must_be_a_listed_workspace(tmp_path):
    with pytest.raises(ValueError, match="--episodes"):
        InstallConfig(project=tmp_path, workspaces=["a", "b"], episodes="c")
    cfg = InstallConfig(project=tmp_path, workspaces=["a", "b"], episodes="b")
    assert cfg.episodes_workspace == "b"
    assert InstallConfig(project=tmp_path, workspaces=["a", "b"]).episodes_workspace == "a"


def test_hook_commands_for_several_workspaces(cfg):
    cfg.workspaces = ["backend", "team"]
    cfg.episodes = "team"
    start = installer.hook_command(cfg, "SessionStart", "/v/okf-claude")
    assert start == ("/v/okf-claude hook session-start --workspace backend --workspace team "
                     "--episodes team --recent 5")
    end = installer.hook_command(cfg, "SessionEnd", "/v/okf-claude")
    assert end == "/v/okf-claude hook session-end --workspace team --model haiku"


def test_install_several_workspaces_registers_one_server_each(cfg):
    run = FakeRun()
    cfg.workspaces = ["backend", "team"]
    done = installer.install(cfg, run=run)
    adds = [c for c in run.calls if c[2] == "add"]
    assert [a[5] for a in adds] == ["okf-backend", "okf-team"]
    assert [a[-1] for a in adds] == ["backend", "team"]
    assert "created workspace 'backend'" in done and WorkspaceRegistry().exists("backend")
    assert installer.hooked_workspaces(json.loads(cfg.settings_path.read_text())) == ["backend", "team"]


def test_reinstall_removes_servers_no_longer_listed(cfg):
    run = FakeRun()
    cfg.workspaces = ["backend", "team"]
    installer.install(cfg, run=run)
    run.calls.clear()
    cfg.workspaces = ["backend"]
    installer.install(cfg, run=run)
    removed = {c[5] for c in run.calls if c[2] == "remove"}
    assert removed == {"okf-backend", "okf-team", "okf"}
    assert [c[5] for c in run.calls if c[2] == "add"] == ["okf"]


def test_uninstall_removes_every_server_from_hooks(cfg):
    run = FakeRun()
    cfg.workspaces = ["backend", "team"]
    installer.install(cfg, run=run)
    run.calls.clear()
    installer.uninstall(InstallConfig(project=cfg.project, home=cfg.home), run=run)
    assert sorted(c[5] for c in run.calls) == ["okf-backend", "okf-team"]
    assert json.loads(cfg.settings_path.read_text()) == {}


def test_uninstall_without_hooks_falls_back_to_okf(cfg):
    run = FakeRun()
    installer.uninstall(cfg, run=run)
    assert [c[5] for c in run.calls] == ["okf"]


def test_install_name_clash_fails_before_changes(cfg):
    run = FakeRun()
    cfg.workspaces = ["a.b", "a-b"]
    with pytest.raises(ValueError):
        installer.install(cfg, run=run)
    assert run.calls == [] and not cfg.settings_path.exists()
