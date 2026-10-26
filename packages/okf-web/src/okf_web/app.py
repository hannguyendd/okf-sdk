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

from okf_core import (
    INDEX_FILENAME,
    RESERVED_STEMS,
    OKFDocument,
    Storage,
    WorkspaceRegistry,
    open_storage,
)
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
    bundle_root=None,
    *,
    registry: WorkspaceRegistry | None = None,
    read_only: bool = False,
    search_config=None,
    search_max_chars: int = 6000,
    vector_db: str | None = None,
    static_dir: Path | str | None = None,
) -> Starlette:
    """Serve one fixed bundle (``bundle_root``) or a workspace registry.

    In workspace mode each index is addressed under
    ``/api/workspaces/{workspace}/indexes/{index}`` with the same bundle routes;
    ``vector_db`` applies only to the fixed bundle (indexes use the default
    sibling file so they never share a vector store).
    """
    if bundle_root is None and registry is None:
        raise ValueError("create_app needs a bundle_root or a registry")
    fixed = open_storage(bundle_root) if bundle_root is not None else None

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
            except FileNotFoundError as e:
                return JSONResponse({"error": f"not found: {e}"}, status_code=404)
            except FileExistsError as e:
                return JSONResponse({"error": str(e)}, status_code=400)
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
            "mode": "workspace" if fixed is None else "bundle",
            "location": str(registry.root) if fixed is None else fixed.location,
            "read_only": read_only,
            "search_enabled": search_config is not None,
        }

    def bundle_routes(prefix: str, resolve) -> list[Route]:
        """The per-bundle API; ``resolve(request)`` yields that request's Storage."""

        def search(request, body):
            return operations.search_indexes(
                resolve(request),
                q(request, "q", ""),
                int(q(request, "top_k", 5)),
                q(request, "dir"),
                config=search_config,
                max_chars=search_max_chars,
                db_path=vector_db if fixed is not None else None,
            )

        def r(path, fn, methods, **kw):
            return Route(prefix + path, handler(fn, **kw), methods=methods)

        cid = lambda req: req.path_params["concept_id"]  # noqa: E731
        return [
            r("/tree", lambda rq, b: _tree(resolve(rq), q(rq, "dir")), ["GET"]),
            r(
                "/index",
                lambda rq, b: operations.read_index(resolve(rq), q(rq, "dir"), int(q(rq, "depth", 1))),
                ["GET"],
            ),
            r(
                "/concepts",
                lambda rq, b: operations.list_concepts(resolve(rq), q(rq, "type"), q(rq, "prefix")),
                ["GET"],
            ),
            r(
                "/concepts",
                lambda rq, b: operations.add_concept(
                    resolve(rq), b["concept_id"], b.get("frontmatter") or {}, b.get("body") or ""
                ),
                ["POST"],
                write=True,
                status=201,
            ),
            r("/concepts/{concept_id:path}", lambda rq, b: operations.get_concept(resolve(rq), cid(rq)), ["GET"]),
            r(
                "/concepts/{concept_id:path}",
                lambda rq, b: operations.patch_concept(resolve(rq), cid(rq), b.get("frontmatter"), b.get("body")),
                ["PATCH"],
                write=True,
            ),
            r(
                "/concepts/{concept_id:path}",
                lambda rq, b: operations.delete_concept(
                    resolve(rq), cid(rq), q(rq, "force", "") in ("1", "true")
                ),
                ["DELETE"],
                write=True,
            ),
            r(
                "/move",
                lambda rq, b: operations.move_concept(resolve(rq), b["from_concept_id"], b["to_concept_id"]),
                ["POST"],
                write=True,
            ),
            r(
                "/describe",
                lambda rq, b: operations.describe_directory(resolve(rq), b["dir"], b.get("description", "")),
                ["POST"],
                write=True,
            ),
            r("/reindex", lambda rq, b: operations.reindex_bundle(resolve(rq)), ["POST"], write=True),
            r("/search", search, ["GET"]),
        ]

    routes = [Route("/api/info", handler(info))]

    if fixed is not None:
        routes += bundle_routes("/api", lambda request: fixed)
    else:

        def index_storage(request: Request) -> Storage:
            ws = registry.get(request.path_params["workspace"])
            return open_storage(ws.index_root(request.path_params["index"]))

        def list_workspaces(request, body):
            return [{"name": w.name, "indexes": w.indexes()} for w in registry.list()]

        def create_workspace(request, body):
            registry.create(body["name"])
            return {"name": body["name"], "indexes": []}

        def create_index(request, body):
            registry.get(request.path_params["workspace"]).create_index(body["name"])
            return {"name": body["name"]}

        routes += [
            Route("/api/workspaces", handler(list_workspaces), methods=["GET"]),
            Route("/api/workspaces", handler(create_workspace, write=True, status=201), methods=["POST"]),
            Route(
                "/api/workspaces/{workspace}/indexes",
                handler(create_index, write=True, status=201),
                methods=["POST"],
            ),
        ]
        routes += bundle_routes("/api/workspaces/{workspace}/indexes/{index}", index_storage)

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
