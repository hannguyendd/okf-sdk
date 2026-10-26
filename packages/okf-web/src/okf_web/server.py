"""CLI entry point: ``okf-web`` serves the API and built frontend on localhost."""

from __future__ import annotations

import argparse
from pathlib import Path

from okf_core import WorkspaceRegistry
from okf_mcp.embeddings import EmbeddingConfig
from okf_mcp.server import Settings

from okf_web.app import create_app

STATIC_DIR = Path(__file__).parent / "static"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="okf-web", description=__doc__)
    p.add_argument("--read-only", action="store_true", help="disable all write endpoints")
    p.add_argument("--host", default="127.0.0.1", help="bind address (no auth: keep it local)")
    p.add_argument("--port", type=int, default=8765)
    return p.parse_args(argv)


def build_app(args: argparse.Namespace):
    """Serve the workspaces under ``$OKF_HOME`` (default ``~/.okf``)."""
    settings = Settings()
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
        WorkspaceRegistry(),
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
