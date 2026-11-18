"""Starlette HTTP API over ``okf_backend.operations`` for the workspaces of a registry."""

from __future__ import annotations

import asyncio
import posixpath
from pathlib import Path
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from okf_core import (
    Bundle,
    INDEX_FILENAME,
    RESERVED_STEMS,
    OKFDocument,
    Storage,
    WorkspaceRegistry,
)
from okf_core.paths import is_hidden

from okf_backend import operations


class _Forbidden(Exception):
    pass


class _UnsupportedMediaType(Exception):
    pass


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _hostname(host: str) -> str:
    """``Host`` header value without its port (``[::1]:8765`` -> ``::1``)."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


class _LocalOnly:
    """Refuse ``/api`` requests that a web page in the user's browser could forge.

    The API has no auth, so any site the user visits could otherwise write to it:
    - ``Host`` must be an allowed name (blocks DNS rebinding); skipped when
      ``allowed_hosts`` is ``None``.
    - Writes must not be cross-site: ``Sec-Fetch-Site: cross-site`` or an
      ``Origin`` that differs from ``Host`` is refused. Clients that send no
      ``Origin`` (curl, scripts) are allowed.
    """

    def __init__(self, app, allowed_hosts: frozenset[str] | None) -> None:
        self.app = app
        self.allowed_hosts = allowed_hosts

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/api/"):
            reason = self._refusal(Headers(scope=scope), scope["method"])
            if reason:
                await JSONResponse({"error": reason}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)

    def _refusal(self, headers: Headers, method: str) -> str | None:
        host = headers.get("host", "")
        if self.allowed_hosts is not None and _hostname(host) not in self.allowed_hosts:
            return f"host not allowed: {host or '(none)'}"
        if method in _SAFE_METHODS:
            return None
        if headers.get("sec-fetch-site") == "cross-site":
            return "cross-site request refused"
        origin = headers.get("origin")
        if origin is not None and (origin == "null" or urlsplit(origin).netloc.lower() != host.lower()):
            return f"cross-origin request refused: {origin}"
        return None


def _tree(storage: Storage, dir: str | None) -> dict:
    """One directory level: authored description, child directories, concepts."""
    key = operations._clean_dir(dir)
    if is_hidden(key) or not storage.is_dir(key):
        raise ValueError(f"directory not found: {key or '/'}")

    def description(d: str) -> str | None:
        idx = posixpath.join(d, INDEX_FILENAME)
        if not storage.exists(idx):
            return None
        return OKFDocument.parse(storage.read_text(idx)).frontmatter.get("description") or None

    directories, concepts = [], []
    for e in sorted(storage.list_dir(key), key=lambda e: e.name):
        if is_hidden(e.name):
            continue
        child = posixpath.join(key, e.name)
        if e.is_dir:
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


def _overview(storage: Storage, recent: int = 5) -> dict:
    """At-a-glance stats for the workspace: concept/directory counts, types, latest concepts."""
    bundle = Bundle.load(storage)
    concepts = list(bundle)
    types: dict[str, int] = {}
    for c in concepts:
        types[c.type or "?"] = types.get(c.type or "?", 0) + 1

    def stamp(c) -> str:
        ts = c.document.frontmatter.get("timestamp")
        return ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")

    latest = sorted(concepts, key=stamp, reverse=True)[:recent]
    return {
        "concepts": len(concepts),
        "directories": len(_all_dirs(storage)),
        "types": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "recent": [
            {"id": c.id, "title": c.title or None, "type": c.type or None, "timestamp": stamp(c) or None}
            for c in latest
        ],
    }


def _concept_with_backlinks(storage: Storage, concept_id: str) -> dict:
    """``get_concept`` plus ``linked_from``: the concepts whose bodies link here."""
    result = operations.get_concept(storage, concept_id)
    result["linked_from"] = sorted(set(Bundle.load(storage).backlinks(concept_id)))
    return result


def _all_dirs(storage: Storage, key: str = "") -> list[str]:
    out: list[str] = []
    for e in storage.list_dir(key):
        if e.is_dir and not is_hidden(e.name):
            child = posixpath.join(key, e.name)
            out.append(child)
            out.extend(_all_dirs(storage, child))
    return out


def create_app(
    registry: WorkspaceRegistry,
    *,
    read_only: bool = False,
    search_config=None,
    search_max_chars: int = 6000,
    static_dir: Path | str | None = None,
    allowed_hosts: frozenset[str] | None = None,
) -> Starlette:
    """Serve a workspace registry: each workspace is addressed under
    ``/api/workspaces/{workspace}``; search uses the workspace's ``.okf/vectors.db``.

    Cross-site writes are always refused; ``allowed_hosts`` (e.g.
    ``LOOPBACK_HOSTS``) also restricts the ``Host`` header, which ``okf-backend``
    always sets. Write bodies must be ``application/json``."""

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
                        media = request.headers.get("content-type", "").split(";")[0].strip().lower()
                        if media != "application/json":
                            raise _UnsupportedMediaType("request body must be application/json")
                        body = await request.json()
                result = await asyncio.to_thread(fn, request, body)
                return JSONResponse(result, status_code=status)
            except _Forbidden as e:
                return JSONResponse({"error": str(e)}, status_code=403)
            except _UnsupportedMediaType as e:
                return JSONResponse({"error": str(e)}, status_code=415)
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
            "mode": "workspace",
            "location": registry.storage.location,
            "read_only": read_only,
            "search_enabled": search_config is not None,
        }

    def workspace_routes() -> list[Route]:
        """The per-workspace API; every route targets ``registry.get(ws).storage``."""
        prefix = "/api/workspaces/{workspace}"

        def resolve(request) -> Storage:
            return registry.get(request.path_params["workspace"]).storage

        def search(request, body):
            return operations.search_workspace(
                registry.get(request.path_params["workspace"]),
                q(request, "q", ""),
                int(q(request, "top_k", 5)),
                request.query_params.getlist("paths") or None,
                config=search_config,
                max_chars=search_max_chars,
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
            r("/concepts/{concept_id:path}", lambda rq, b: _concept_with_backlinks(resolve(rq), cid(rq)), ["GET"]),
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
            r("/dirs", lambda rq, b: {"dirs": sorted(_all_dirs(resolve(rq)))}, ["GET"]),
            r(
                "/dirs",
                lambda rq, b: operations.create_directory(resolve(rq), b["dir"], b.get("description") or ""),
                ["POST"],
                write=True,
                status=201,
            ),
            r("/reindex", lambda rq, b: operations.reindex_bundle(resolve(rq)), ["POST"], write=True),
            r("/search", search, ["GET"]),
            r("/overview", lambda rq, b: _overview(resolve(rq)), ["GET"]),
        ]

    def list_workspaces(request, body):
        # One unusable (v1 / corrupt) workspace must not hide the others: it is
        # listed with its error so the portal can say what to run.
        rows = []
        for w in registry.list():
            try:
                rows.append({"name": w.name, "color": w.color()})
            except ValueError as exc:
                rows.append({"name": w.name, "color": None, "error": str(exc)})
        return rows

    def create_workspace(request, body):
        registry.create(body["name"])
        return {"name": body["name"], "color": None}

    def set_workspace_color(request, body):
        ws = registry.get(request.path_params["workspace"])
        return {"name": ws.name, "color": ws.set_color(body.get("color"))}

    routes = [
        Route("/api/info", handler(info)),
        Route("/api/workspaces", handler(list_workspaces), methods=["GET"]),
        Route("/api/workspaces", handler(create_workspace, write=True, status=201), methods=["POST"]),
        Route(
            "/api/workspaces/{workspace}/color",
            handler(set_workspace_color, write=True),
            methods=["POST"],
        ),
    ]
    routes += workspace_routes()

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

    return Starlette(
        routes=routes, middleware=[Middleware(_LocalOnly, allowed_hosts=allowed_hosts)]
    )
