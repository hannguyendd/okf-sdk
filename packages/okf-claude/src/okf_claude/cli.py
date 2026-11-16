"""``okf-claude`` command line: setup/uninstall, and the hook entry points."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from okf_claude import hooks, installer


def _target_args(p: argparse.ArgumentParser, required: bool) -> None:
    p.add_argument("--workspace", "-w", default=os.environ.get("OKF_WORKSPACE"),
                   required=required and not os.environ.get("OKF_WORKSPACE"),
                   help="OKF workspace (default: $OKF_WORKSPACE)")
    p.add_argument("--bundle", "-b", default=os.environ.get("OKF_BUNDLE"),
                   required=required and not os.environ.get("OKF_BUNDLE"),
                   help="bundle inside the workspace (default: $OKF_BUNDLE)")


def _env_pairs(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in values:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise SystemExit(f"--server-env expects KEY=VALUE, got {item!r}")
        out[key] = value
    return out


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="okf-claude", description="Claude Code integration for OKF")
    sub = p.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="install MCP server, hooks, and slash commands")
    _target_args(setup, required=True)
    setup.add_argument("--project", type=Path, default=Path.cwd(),
                       help="project directory (default: current directory)")
    setup.add_argument("--scope", choices=installer.SCOPES, default="local",
                       help="local (default): this project, just you; project: committed "
                            "project files; user: every project")
    setup.add_argument("--model", default="haiku", help="model that writes episode summaries")
    setup.add_argument("--recent", type=int, default=5,
                       help="recent episodes loaded at session start (0 disables)")
    setup.add_argument("--server-env", action="append", default=[], metavar="KEY=VALUE",
                       help="extra env for the MCP server, e.g. OKF_EMBEDDING_URL=... (repeatable)")
    setup.add_argument("--no-create", action="store_true",
                       help="fail instead of creating a missing workspace/bundle")
    setup.add_argument("--no-mcp", action="store_true", help="skip registering the MCP server")

    rm = sub.add_parser("uninstall", help="remove what setup installed")
    rm.add_argument("--project", type=Path, default=Path.cwd())
    rm.add_argument("--scope", choices=installer.SCOPES, default="local")
    rm.add_argument("--no-mcp", action="store_true", help="leave the MCP server registered")

    hook = sub.add_parser("hook", help="Claude Code hook entry points (reads the event on stdin)")
    hook_sub = hook.add_subparsers(dest="event", required=True)
    start = hook_sub.add_parser("session-start")
    _target_args(start, required=True)
    start.add_argument("--recent", type=int, default=5)
    end = hook_sub.add_parser("session-end")
    _target_args(end, required=True)
    end.add_argument("--model", default="haiku")

    ep = sub.add_parser("episode", help="summarize a transcript into an episode (used by session-end)")
    _target_args(ep, required=True)
    ep.add_argument("--transcript", required=True)
    ep.add_argument("--session-id", required=True)
    ep.add_argument("--cwd")
    ep.add_argument("--reason")
    ep.add_argument("--model", default="haiku")
    return p


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)

    if args.command == "setup":
        cfg = installer.InstallConfig(
            project=args.project, workspace=args.workspace, bundle=args.bundle,
            scope=args.scope, model=args.model, recent=args.recent,
            server_env=_env_pairs(args.server_env),
        )
        try:
            done = installer.install(cfg, create=not args.no_create, mcp=not args.no_mcp)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            print(f"okf-claude setup: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        for line in done:
            print(f"✓ {line}")
        print("Restart Claude Code (or start a new session) to load the hooks.")
        return

    if args.command == "uninstall":
        cfg = installer.InstallConfig(project=args.project, scope=args.scope)
        for line in installer.uninstall(cfg, mcp=not args.no_mcp):
            print(f"✓ {line}")
        return

    if args.command == "hook":
        if args.event == "session-start":
            raise SystemExit(hooks.session_start(args.workspace, args.bundle, recent=args.recent))
        raise SystemExit(hooks.session_end(args.workspace, args.bundle, model=args.model))

    if args.command == "episode":
        raise SystemExit(hooks.episode(
            workspace=args.workspace, bundle=args.bundle, transcript_path=args.transcript,
            session_id=args.session_id, cwd=args.cwd, reason=args.reason, model=args.model,
        ))
