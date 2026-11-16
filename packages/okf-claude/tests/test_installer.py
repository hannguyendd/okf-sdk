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
    return InstallConfig(project=tmp_path / "proj", workspace="team", bundle="notes", home=tmp_path / "home")


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
    cfg.workspace = "my ws"
    cmd = installer.hook_command(cfg, "SessionStart", "/v/okf-claude")
    assert cmd == "/v/okf-claude hook session-start --workspace 'my ws' --bundle notes --recent 5"
    assert installer.hook_command(cfg, "SessionEnd", "/v/okf-claude").endswith("--model haiku")


def test_ensure_target_creates_or_refuses(okf_home):
    with pytest.raises(FileNotFoundError):
        installer.ensure_target("team", "notes", create=False)
    assert installer.ensure_target("team", "notes", create=True) == [
        "created workspace 'team'", "created bundle 'notes' in workspace 'team'"]
    assert installer.ensure_target("team", "notes", create=False) == []
    assert WorkspaceRegistry().get("team").indexes() == ["notes"]


def test_install_and_uninstall_roundtrip(cfg):
    run = FakeRun()
    cfg.server_env = {"OKF_EMBEDDING_URL": "http://localhost:1234/v1"}
    done = installer.install(cfg, run=run)
    assert any("registered MCP server" in d for d in done)

    add = run.calls[1]
    assert add[:6] == ["claude", "mcp", "add", "--scope", "local", "okf"]
    assert add[6:] == ["-e", "OKF_WORKSPACE=team", "-e", "OKF_BUNDLE=notes",
                       "-e", "OKF_EMBEDDING_URL=http://localhost:1234/v1", "--", "/venv/bin/okf-mcp"]

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
