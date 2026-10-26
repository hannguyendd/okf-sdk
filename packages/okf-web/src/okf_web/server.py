"""CLI entry point: ``okf-web`` serves the API and built frontend on localhost."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from okf_core import Workspace, WorkspaceRegistry
from okf_mcp.embeddings import EmbeddingConfig
from okf_mcp.server import Settings

from okf_web.app import create_app

STATIC_DIR = Path(__file__).parent / "static"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="okf-web", description=__doc__)
    p.add_argument("--workspace", help="workspace under OKF_HOME (else OKF_WORKSPACE, else the only one)")
    p.add_argument("--bundle", help="bundle in the workspace (else OKF_BUNDLE, else the only one)")
    p.add_argument("--read-only", action="store_true", help="disable all write endpoints")
    p.add_argument("--host", default="127.0.0.1", help="bind address (no auth: keep it local)")
    p.add_argument("--port", type=int, default=8765)
    return p.parse_args(argv)


def _pick(kind: str, name: str | None, names: list[str], where: str) -> str:
    choices = ", ".join(names) or "(none)"
    if name is not None:
        if name not in names:
            raise ValueError(f"no {kind} {name!r}{where}; {kind}s: {choices}")
        return name
    if len(names) == 1:
        return names[0]
    if not names:
        raise ValueError(f"no {kind}s{where} yet; create one first")
    raise ValueError(f"choose a {kind} with --{kind}{where}: one of {choices}")


def resolve_target(
    registry: WorkspaceRegistry,
    workspace: str | None,
    bundle: str | None,
    env_workspace: str | None,
    env_bundle: str | None,
) -> tuple[Workspace, str]:
    """Flag > env > the only candidate. The env bundle only applies inside the
    env workspace (or when none is set). Raises ``ValueError`` listing choices."""
    ws_name = _pick("workspace", workspace or env_workspace, [w.name for w in registry.list()], "")
    if env_workspace is not None and ws_name != env_workspace:
        env_bundle = None
    ws = registry.get(ws_name)
    return ws, _pick("bundle", bundle or env_bundle, ws.indexes(), f" in workspace {ws_name!r}")


def build_app(args: argparse.Namespace):
    settings = Settings()
    try:
        workspace, bundle = resolve_target(
            WorkspaceRegistry(), args.workspace, args.bundle, settings.workspace, settings.bundle
        )
    except ValueError as e:
        sys.exit(f"okf-web: {e}")
    config = (
        EmbeddingConfig(
            url=settings.embedding_url,
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
        )
        if settings.embedding_url and settings.embedding_model
        else None
    )
    return create_app(
        workspace,
        bundle,
        read_only=args.read_only,
        search_config=config,
        search_max_chars=settings.embedding_max_chars,
        static_dir=STATIC_DIR if (STATIC_DIR / "index.html").is_file() else None,
    )


def main() -> None:
    import uvicorn

    args = parse_args()
    app = build_app(args)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
