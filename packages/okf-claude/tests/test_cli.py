import json

import pytest

from okf_claude import cli, installer


def test_setup_end_to_end_without_mcp(tmp_path, okf_home, monkeypatch, capsys):
    monkeypatch.setattr(installer, "_bin", lambda name: f"/venv/bin/{name}")
    project = tmp_path / "proj"
    cli.main(["setup", "-w", "team", "-b", "notes", "--project", str(project), "--no-mcp"])
    out = capsys.readouterr().out
    assert "created workspace 'team'" in out and "installed hooks" in out
    settings = json.loads((project / ".claude" / "settings.local.json").read_text())
    assert "session-start" in settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]


def test_setup_no_create_fails_cleanly(tmp_path, okf_home, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["setup", "-w", "team", "-b", "notes", "--project", str(tmp_path), "--no-create", "--no-mcp"])
    assert exc.value.code == 1
    assert "no workspace 'team'" in capsys.readouterr().err


def test_setup_rejects_bad_server_env(tmp_path, okf_home):
    with pytest.raises(SystemExit):
        cli.main(["setup", "-w", "t", "-b", "n", "--project", str(tmp_path), "--server-env", "NOEQUALS"])
