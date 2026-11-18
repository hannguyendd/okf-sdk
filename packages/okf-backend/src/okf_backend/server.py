"""CLI entry point: ``okf-backend`` serves the REST API (and an optional built frontend) on localhost."""

from __future__ import annotations

import argparse
from pathlib import Path

from okf_core import WorkspaceRegistry

from okf_backend.api import create_app
from okf_backend.settings import BackendSettings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="okf-backend", description=__doc__)
    p.add_argument("--read-only", action="store_true", help="disable all write endpoints")
    p.add_argument("--host", default="127.0.0.1", help="bind address (no auth: keep it local)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument(
        "--static",
        type=Path,
        metavar="DIR",
        help="serve this built frontend (e.g. packages/okf-web/dist); omit to serve the API only",
    )
    return p.parse_args(argv)


def _static_dir(override: Path | None) -> Path | None:
    if override is not None:
        if not (override / "index.html").is_file():
            raise SystemExit(f"okf-backend: --static {override}: no index.html (build the frontend first)")
        return override
    return None


def build_app(args: argparse.Namespace):
    """Serve the workspaces under ``$OKF_HOME`` (default ``~/.okf``)."""
    settings = BackendSettings()
    return create_app(
        WorkspaceRegistry(),
        read_only=args.read_only,
        search_config=settings.embedding_config(),
        search_max_chars=settings.embedding_max_chars,
        static_dir=_static_dir(args.static),
    )


def main() -> None:
    import uvicorn

    args = parse_args()
    app = build_app(args)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
