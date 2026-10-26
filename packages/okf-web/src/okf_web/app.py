"""Starlette HTTP API over ``okf_mcp.operations`` for one fixed bundle root."""

from __future__ import annotations

import asyncio
import posixpath
from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from okf_core import INDEX_FILENAME, RESERVED_STEMS, OKFDocument, Storage, open_storage
from okf_mcp import operations


class _Forbidden(Exception):
    pass


def _tree(storage: Storage, dir: str | None) -> dict:
    """One directory level: authored description, child directories, concepts."""
    key = operations._clean_dir(dir)
    if not storage.is_dir(key):
        raise ValueError(f"directory not found: {key or '/'}")

    def description(d: str) -> str | None:
        idx = posixpath.join(d, INDEX_FILENAME)
        if not storage.exists(idx):
            return None
        return OKFDocument.parse(storage.read_text(idx)).frontmatter.get("description") or None

    directories, concepts = [], []
    for e in sorted(storage.list_dir(key), key=lambda e: e.name):
        child = posixpath.join(key, e.name)
        if e.is_dir:
            if not e.name.startswith("."):
                directories.append({"name": e.name, "dir": child, "description": description(child)})
        elif e.name.endswith(".md") and e.name.removesuffix(".md") not in RESERVED_STEMS:
            fm = OKFDocument.parse(storage.read_text(child)).frontmatter
            concepts.append(
                {
                    "id": child.removesuffix(".md"),
                    "type": fm.get("type"),
                    "title": fm.get("title"),
                    "description": fm.get("description"),
                    "tags": fm.get("tags") or [],
                }
            )
    return {"dir": key, "description": description(key), "directories": directories, "concepts": concepts}


def create_app(
    bundle_root,
    *,
    read_only: bool = False,
    search_config=None,
    search_max_chars: int = 6000,
    vector_db: str | None = None,
    static_dir: Path | str | None = None,
) -> Starlette:
    storage = open_storage(bundle_root)

    def guard() -> None:
        if read_only:
            raise _Forbidden("server is read-only")

    def handler(fn, *, write: bool = False, status: int = 200):
        async def endpoint(request: Request):
            try:
                if write:
                    guard()
                body = {}
                if request.method in ("POST", "PATCH"):
                    raw = await request.body()
                    if raw:
                        body = await request.json()
                result = await asyncio.to_thread(fn, request, body)
                return JSONResponse(result, status_code=status)
            except _Forbidden as e:
                return JSONResponse({"error": str(e)}, status_code=403)
            except (ValueError, KeyError, TypeError) as e:
                msg = str(e).strip("'") if isinstance(e, KeyError) else str(e)
                if isinstance(e, KeyError):
                    msg = f"missing field: {msg}"
                code = 404 if "not found" in msg else 400
                return JSONResponse({"error": msg}, status_code=code)

        return endpoint

    def q(request: Request, name: str, default=None):
        return request.query_params.get(name, default)

    def info(request, body):
        return {
            "location": storage.location,
            "read_only": read_only,
            "search_enabled": search_config is not None,
        }

    def search(request, body):
        return operations.search_indexes(
            storage,
            q(request, "q", ""),
            int(q(request, "top_k", 5)),
            q(request, "dir"),
            config=search_config,
            max_chars=search_max_chars,
            db_path=vector_db,
        )

    routes = [
        Route("/api/info", handler(info)),
        Route("/api/tree", handler(lambda r, b: _tree(storage, q(r, "dir")))),
        Route(
            "/api/index",
            handler(lambda r, b: operations.read_index(storage, q(r, "dir"), int(q(r, "depth", 1)))),
        ),
        Route(
            "/api/concepts",
            handler(lambda r, b: operations.list_concepts(storage, q(r, "type"), q(r, "prefix"))),
            methods=["GET"],
        ),
        Route(
            "/api/concepts",
            handler(
                lambda r, b: operations.add_concept(
                    storage, b["concept_id"], b.get("frontmatter") or {}, b.get("body") or ""
                ),
                write=True,
                status=201,
            ),
            methods=["POST"],
        ),
        Route(
            "/api/concepts/{concept_id:path}",
            handler(lambda r, b: operations.get_concept(storage, r.path_params["concept_id"])),
            methods=["GET"],
        ),
        Route(
            "/api/concepts/{concept_id:path}",
            handler(
                lambda r, b: operations.patch_concept(
                    storage, r.path_params["concept_id"], b.get("frontmatter"), b.get("body")
                ),
                write=True,
            ),
            methods=["PATCH"],
        ),
        Route(
            "/api/concepts/{concept_id:path}",
            handler(
                lambda r, b: operations.delete_concept(
                    storage, r.path_params["concept_id"], q(r, "force", "") in ("1", "true")
                ),
                write=True,
            ),
            methods=["DELETE"],
        ),
        Route(
            "/api/move",
            handler(
                lambda r, b: operations.move_concept(
                    storage, b["from_concept_id"], b["to_concept_id"]
                ),
                write=True,
            ),
            methods=["POST"],
        ),
        Route(
            "/api/describe",
            handler(
                lambda r, b: operations.describe_directory(
                    storage, b["dir"], b.get("description", "")
                ),
                write=True,
            ),
            methods=["POST"],
        ),
        Route(
            "/api/reindex",
            handler(lambda r, b: operations.reindex_bundle(storage), write=True),
            methods=["POST"],
        ),
        Route("/api/search", handler(search)),
    ]

    if static_dir is not None:
        root = Path(static_dir).resolve()

        async def spa(request: Request):
            rel = request.path_params.get("path", "")
            target = (root / rel).resolve()
            if rel and target.is_file() and root in target.parents:
                return FileResponse(target)
            if rel.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(root / "index.html")

        routes.append(Route("/{path:path}", spa))

    return Starlette(routes=routes)
