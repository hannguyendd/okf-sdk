"""CLI entry point: ``okf-web`` serves the API and built frontend on localhost."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from okf_core import WorkspaceRegistry
from okf_mcp import operations
from okf_mcp.embeddings import EmbeddingConfig
from okf_mcp.server import Settings

from okf_web.app import create_app

STATIC_DIR = Path(__file__).parent / "static"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="okf-web", description=__doc__)
    p.add_argument("--bundle-root", help="bundle path or scheme:// location (else OKF_BUNDLE_ROOT)")
    p.add_argument("--project", help="project path for store mode (OKF_STORE_ROOT); default: cwd")
    p.add_argument(
        "--workspaces",
        action="store_true",
        help="serve workspaces under $OKF_HOME (default ~/.okf) instead of one bundle; "
        "implied when no bundle root is configured",
    )
    p.add_argument("--read-only", action="store_true", help="disable all write endpoints")
    p.add_argument("--host", default="127.0.0.1", help="bind address (no auth: keep it local)")
    p.add_argument("--port", type=int, default=8765)
    return p.parse_args(argv)


def build_app(args: argparse.Namespace):
    settings = Settings()
    root = None
    registry = None
    configured = args.bundle_root or settings.store_root or settings.bundle_root
    if args.workspaces or not configured:
        registry = WorkspaceRegistry()
    else:
        try:
            if args.bundle_root:
                root = operations.resolve_bundle_root(args.bundle_root, None)
            elif settings.store_root and settings.bundle_root:
                raise ValueError("set OKF_STORE_ROOT or OKF_BUNDLE_ROOT, not both")
            elif settings.store_root:
                root = operations.resolve_store_bundle_root(
                    settings.store_root, args.project or Path.cwd()
                )
            else:
                root = operations.resolve_bundle_root(None, settings.bundle_root)
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
        root,
        registry=registry,
        read_only=args.read_only,
        search_config=config,
        search_max_chars=settings.embedding_max_chars,
        vector_db=settings.vector_db,
        static_dir=STATIC_DIR if (STATIC_DIR / "index.html").is_file() else None,
    )


def main() -> None:
    import uvicorn

    args = parse_args()
    app = build_app(args)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
