"""Install / uninstall the OKF integration into Claude Code.

Three pieces, each idempotent (re-running replaces our own entries only):

- one MCP server per workspace, registered with ``claude mcp add`` and pinned
  via ``okf-mcp --workspace`` (named ``okf`` for a single workspace,
  ``okf-<ws>`` for several; see ``okf_claude.servers``);
- SessionStart / SessionEnd hooks in a Claude Code settings file;
- the ``/okf-remember`` and ``/okf-recall`` slash commands.

Scopes follow Claude Code's: ``local`` (this project, just you — the default,
since hook commands are absolute paths on this machine), ``project`` (this
project, committed: ``.claude/settings.json`` and ``.mcp.json``), and ``user``
(every project).
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Callable

from okf_core import WorkspaceRegistry

from okf_claude.servers import SERVER_NAME, dedupe, server_names

COMMANDS = ("okf-remember.md", "okf-recall.md")
HOOK_EVENTS = {"SessionStart": "session-start", "SessionEnd": "session-end"}
SCOPES = ("local", "project", "user")

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class InstallConfig:
    project: Path
    workspaces: list[str] = field(default_factory=list)
    episodes: str | None = None
    scope: str = "local"
    model: str = "haiku"
    recent: int = 5
    server_env: dict[str, str] = field(default_factory=dict)
    claude_bin: str = "claude"
    home: Path = field(default_factory=Path.home)

    def __post_init__(self) -> None:
        if self.scope not in SCOPES:
            raise ValueError(f"scope must be one of {', '.join(SCOPES)}")
        self.project = Path(self.project).resolve()
        self.workspaces = dedupe(list(self.workspaces))
        if self.episodes and self.workspaces and self.episodes not in self.workspaces:
            raise ValueError(f"--episodes {self.episodes!r} must be one of the --workspace values")

    @property
    def episodes_workspace(self) -> str:
        """Where SessionEnd writes episodes: ``episodes`` or the first workspace."""
        return self.episodes or (self.workspaces[0] if self.workspaces else "")

    @property
    def settings_path(self) -> Path:
        if self.scope == "user":
            return self.home / ".claude" / "settings.json"
        name = "settings.local.json" if self.scope == "local" else "settings.json"
        return self.project / ".claude" / name

    @property
    def commands_dir(self) -> Path:
        base = self.home if self.scope == "user" else self.project
        return base / ".claude" / "commands"


def _bin(name: str) -> str:
    """Absolute path of a console script from this environment."""
    candidate = Path(sys.executable).parent / name
    if candidate.exists():
        return str(candidate)
    found = shutil.which(name)
    if found:
        return str(Path(found).resolve())
    raise FileNotFoundError(f"{name} not found; run `uv sync` in the okf-sdk checkout")


def hook_command(cfg: InstallConfig, event: str, okf_claude: str | None = None) -> str:
    args = [okf_claude or _bin("okf-claude"), "hook", HOOK_EVENTS[event]]
    if event == "SessionStart":
        for ws in cfg.workspaces:
            args += ["--workspace", ws]
        if len(cfg.workspaces) > 1:
            args += ["--episodes", cfg.episodes_workspace]
        args += ["--recent", str(cfg.recent)]
    else:
        args += ["--workspace", cfg.episodes_workspace, "--model", cfg.model]
    return shlex.join(args)


def hooked_workspaces(settings: dict) -> list[str]:
    """Workspaces named by our hook commands in ``settings`` (from an earlier setup)."""
    found: list[str] = []
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return found
    for groups in hooks.values():
        for group in groups if isinstance(groups, list) else []:
            inner = group.get("hooks") if isinstance(group, dict) else None
            for hook in inner if isinstance(inner, list) else []:
                if not _is_ours(hook):
                    continue
                try:
                    argv = shlex.split(hook.get("command", ""))
                except ValueError:
                    continue
                for flag, value in zip(argv, argv[1:]):
                    if flag in ("--workspace", "-w"):
                        found.append(value)
    return dedupe(found)


def _previous_servers(cfg: InstallConfig) -> set[str]:
    try:
        old = hooked_workspaces(_load_json(cfg.settings_path))
        return set(server_names(old).values()) if old else set()
    except ValueError:
        return set()


def _is_ours(hook: object) -> bool:
    cmd = hook.get("command", "") if isinstance(hook, dict) else ""
    return "okf-claude" in cmd and " hook " in cmd


def remove_hooks(settings: dict) -> dict:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return settings
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept = []
        for group in groups:
            if isinstance(group, dict) and isinstance(group.get("hooks"), list):
                inner = [h for h in group["hooks"] if not _is_ours(h)]
                if inner:
                    kept.append({**group, "hooks": inner})
            else:
                kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks:
        del settings["hooks"]
    return settings


def merge_hooks(settings: dict, commands: dict[str, str]) -> dict:
    """Replace our hook entries in ``settings`` with ``{event: command}``."""
    settings = remove_hooks(settings)
    hooks = settings.setdefault("hooks", {})
    for event, command in commands.items():
        timeout = 30 if event == "SessionStart" else 15
        hooks.setdefault(event, []).append(
            {"hooks": [{"type": "command", "command": command, "timeout": timeout}]}
        )
    return settings


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def ensure_target(workspace: str, *, create: bool) -> list[str]:
    """Check the workspace exists and is usable; create it when ``create``.

    A v1 (bundle-era) workspace raises ``ValueError`` pointing to
    ``okf-migrate-v2`` before anything is installed.
    """
    registry = WorkspaceRegistry()
    done: list[str] = []
    if not registry.exists(workspace):
        if not create:
            raise FileNotFoundError(f"no workspace {workspace!r} (drop --no-create to create it)")
        registry.create(workspace)
        done.append(f"created workspace {workspace!r}")
    else:
        registry.get(workspace)  # raises for a v1 workspace
    return done


def _remove_server(cfg: InstallConfig, name: str, run: Runner) -> bool:
    proc = run(
        [cfg.claude_bin, "mcp", "remove", "--scope", cfg.scope, name],
        cwd=cfg.project, capture_output=True, text=True,
    )
    return proc.returncode == 0


def register_servers(cfg: InstallConfig, run: Runner = subprocess.run) -> list[str]:
    """Register one server per workspace, first removing ours from an earlier setup."""
    names = server_names(cfg.workspaces)
    for stale in sorted(_previous_servers(cfg) | set(names.values())):
        _remove_server(cfg, stale, run)
    done = []
    for ws, name in names.items():
        # Name before the variadic `-e` so it cannot be swallowed as an env value.
        cmd = [cfg.claude_bin, "mcp", "add", "--scope", cfg.scope, name]
        for key, value in cfg.server_env.items():
            cmd += ["-e", f"{key}={value}"]
        cmd += ["--", _bin("okf-mcp"), "--workspace", ws]
        proc = run(cmd, cwd=cfg.project, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"`claude mcp add {name}` failed: {(proc.stderr or proc.stdout).strip()}"
            )
        done.append(f"registered MCP server {name!r} for workspace {ws!r} ({cfg.scope} scope)")
    return done


def unregister_servers(cfg: InstallConfig, run: Runner = subprocess.run) -> list[str]:
    """Remove the servers our hooks point at (``okf`` if there are no hooks)."""
    names = _previous_servers(cfg) or {SERVER_NAME}
    done = []
    for name in sorted(names):
        if _remove_server(cfg, name, run):
            done.append(f"removed MCP server {name!r} ({cfg.scope} scope)")
        else:
            done.append(f"MCP server {name!r} was not registered ({cfg.scope} scope)")
    return done


def install_hooks(cfg: InstallConfig, okf_claude: str | None = None) -> str:
    settings = _load_json(cfg.settings_path)
    commands = {e: hook_command(cfg, e, okf_claude) for e in HOOK_EVENTS}
    _save_json(cfg.settings_path, merge_hooks(settings, commands))
    return f"installed hooks in {cfg.settings_path}"


def uninstall_hooks(cfg: InstallConfig) -> str:
    if not cfg.settings_path.exists():
        return f"no hooks to remove ({cfg.settings_path} does not exist)"
    _save_json(cfg.settings_path, remove_hooks(_load_json(cfg.settings_path)))
    return f"removed hooks from {cfg.settings_path}"


def install_commands(cfg: InstallConfig) -> str:
    cfg.commands_dir.mkdir(parents=True, exist_ok=True)
    source = files("okf_claude.prompts").joinpath("commands")
    for name in COMMANDS:
        (cfg.commands_dir / name).write_text(
            source.joinpath(name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    names = ", ".join("/" + n.removesuffix(".md") for n in COMMANDS)
    return f"installed {names} in {cfg.commands_dir}"


def uninstall_commands(cfg: InstallConfig) -> str:
    removed = 0
    for name in COMMANDS:
        path = cfg.commands_dir / name
        if path.exists():
            path.unlink()
            removed += 1
    return f"removed {removed} slash command(s) from {cfg.commands_dir}"


def install(
    cfg: InstallConfig, *, create: bool = True, mcp: bool = True, run: Runner = subprocess.run
) -> list[str]:
    if not cfg.workspaces:
        raise ValueError("at least one --workspace is required")
    server_names(cfg.workspaces)  # fail on a name clash before touching anything
    done: list[str] = []
    for ws in cfg.workspaces:
        done += ensure_target(ws, create=create)
    if mcp:
        done += register_servers(cfg, run)
    done.append(install_hooks(cfg))
    done.append(install_commands(cfg))
    return done


def uninstall(cfg: InstallConfig, *, mcp: bool = True, run: Runner = subprocess.run) -> list[str]:
    done: list[str] = []
    if mcp:
        done += unregister_servers(cfg, run)
    done.append(uninstall_hooks(cfg))
    done.append(uninstall_commands(cfg))
    return done
