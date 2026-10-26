"""Producer operations over an OKF bundle (framework-agnostic).

Every operation takes ``bundle_root`` as a ``Path``, location string, or
``okf_core.Storage`` and does all I/O through the storage interface; write
operations hold ``storage.lock()`` for their whole duration.
"""

from __future__ import annotations

import posixpath
from datetime import datetime, timezone
from pathlib import Path

from okf_core import (
    INDEX_FILENAME,
    LOG_FILENAME,
    RESERVED_STEMS,
    Bundle,
    OKFDocument,
    Storage,
    Workspace,
    extract_link_ids,
    open_storage,
    parse_concept_id,
    regenerate_indexes,
    rewrite_link_ids,
    strip_link_ids,
)

from okf_mcp.embeddings import EmbeddingConfig, embed_texts
from okf_mcp.vector_store import Embedder, VectorStore, workspace_db_path


def _concept_key(concept_id: str) -> str:
    parts = parse_concept_id(concept_id)
    if parts[-1] in RESERVED_STEMS:
        raise ValueError(
            f"concept_id {concept_id!r} collides with a reserved file name"
        )
    return "/".join(parts) + ".md"


def _id_of(key: str) -> str:
    return key.removesuffix(".md")


def _dir_of(key: str) -> str:
    return posixpath.dirname(key)


def _name_of(key: str) -> str:
    return posixpath.basename(key)


def _clean_dir(dir: str | None) -> str:
    """Normalize a bundle-relative directory arg to a key; reject escapes."""
    if not dir:
        return ""
    norm = posixpath.normpath(dir)
    if norm == ".":
        return ""
    if norm.startswith("/") or norm == ".." or norm.startswith("../"):
        raise ValueError(f"dir escapes the bundle root: {dir}")
    return norm


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now_iso() -> str:
    return _now_utc().isoformat().replace("+00:00", "Z")


def _utc_date(dt: datetime) -> str:
    return dt.date().isoformat()


def _utc_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S") + "Z"


def _append_log(storage: Storage, log_key: str, entry: str, today: str) -> None:
    """Append ``entry`` under a ``## <today>`` group in ``log_key`` (newest-first).

    Creates the file with a ``# Update Log`` title when absent; prepends the
    entry under an existing today group; otherwise inserts a new today group
    above older date groups.
    """
    heading = f"## {today}"
    if not storage.exists(log_key):
        storage.write_text(log_key, f"# Update Log\n\n{heading}\n{entry}\n")
        return
    lines = storage.read_text(log_key).splitlines()
    first_h2 = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), None)
    if first_h2 is not None and lines[first_h2].strip() == heading:
        new_lines = lines[: first_h2 + 1] + [entry] + lines[first_h2 + 1 :]
    elif first_h2 is not None:
        new_lines = lines[:first_h2] + [heading, entry, ""] + lines[first_h2:]
    else:
        new_lines = lines + ["", heading, entry]
    storage.write_text(log_key, "\n".join(new_lines).rstrip() + "\n")


def _log_key(directory_key: str) -> str:
    return posixpath.join(directory_key, LOG_FILENAME)


def _append_log_for(
    storage: Storage, concept_key: str, label: str, action: str, verb: str
) -> str:
    log_key = _log_key(_dir_of(concept_key))
    dt = _now_utc()
    entry = (
        f"* **{_utc_time(dt)}** **{action}**: {verb} [{label}]({_name_of(concept_key)})."
    )
    _append_log(storage, log_key, entry, _utc_date(dt))
    return log_key


def _summary(
    concept_id: str,
    key: str,
    action: str,
    log_key: str,
    indexes: list[str],
) -> dict:
    return {
        "concept_id": concept_id,
        "path": key,
        "action": action,
        "log": log_key,
        "indexes": list(indexes),
    }


def add_concept(
    bundle_root: "Path | str | Storage", concept_id: str, frontmatter: dict, body: str
) -> dict:
    """Create a new concept document, then reindex and log the creation."""
    storage = open_storage(bundle_root)
    key = _concept_key(concept_id)
    fm = dict(frontmatter or {})
    type_val = fm.get("type")
    with storage.lock():
        if storage.exists(key):
            raise ValueError(f"concept already exists: {concept_id}")
        if not isinstance(type_val, str) or not type_val.strip():
            raise ValueError("frontmatter must include a non-empty string 'type'")
        if not fm.get("timestamp"):
            fm["timestamp"] = _now_iso()
        storage.write_text(key, OKFDocument(frontmatter=fm, body=body or "").serialize())
        label = str(fm.get("title") or _id_of(_name_of(key)))
        log_key = _append_log_for(storage, key, label, "Creation", "Added")
        indexes = regenerate_indexes(storage)
    return _summary(concept_id, key, "created", log_key, indexes)


def patch_concept(
    bundle_root: "Path | str | Storage",
    concept_id: str,
    frontmatter: dict | None = None,
    body: str | None = None,
) -> dict:
    """Update an existing concept (merge frontmatter, optional body), reindex, log."""
    storage = open_storage(bundle_root)
    key = _concept_key(concept_id)
    with storage.lock():
        if not storage.exists(key):
            raise ValueError(f"concept not found: {concept_id}")
        doc = OKFDocument.parse(storage.read_text(key))
        fm = dict(doc.frontmatter)
        caller_ts = False
        for k, value in (frontmatter or {}).items():
            if value is not None:
                fm[k] = value
                if k == "timestamp":
                    caller_ts = True
        new_body = doc.body if body is None else body
        if not caller_ts:
            fm["timestamp"] = _now_iso()
        storage.write_text(key, OKFDocument(frontmatter=fm, body=new_body).serialize())
        label = str(fm.get("title") or _id_of(_name_of(key)))
        log_key = _append_log_for(storage, key, label, "Update", "Updated")
        indexes = regenerate_indexes(storage)
    return _summary(concept_id, key, "updated", log_key, indexes)


def reindex_bundle(bundle_root: "Path | str | Storage") -> dict:
    """Regenerate every ``_index.md`` in the bundle from current content.

    Repairs indexes that have drifted (e.g. files edited outside the producer
    tools). This is index maintenance, not a concept change, so it does not
    touch ``_log.md``. Returns the regenerated index paths and their count.
    """
    storage = open_storage(bundle_root)
    with storage.lock():
        indexes = regenerate_indexes(storage)
    return {"action": "reindexed", "indexes": list(indexes), "count": len(indexes)}


def get_concept(bundle_root: "Path | str | Storage", concept_id: str) -> dict:
    """Read one concept: frontmatter, body, and resolved outgoing links."""
    storage = open_storage(bundle_root)
    key = _concept_key(concept_id)
    if not storage.exists(key):
        raise ValueError(f"concept not found: {concept_id}")
    doc = OKFDocument.parse(storage.read_text(key))
    links = extract_link_ids(doc.body or "", _dir_of(key))
    return {
        "id": concept_id,
        "frontmatter": doc.frontmatter,
        "body": doc.body,
        "links_to": links,
    }


def list_concepts(
    bundle_root: "Path | str | Storage",
    type: str | None = None,
    prefix: str | None = None,
) -> list[dict]:
    """List concepts, optionally filtered by exact ``type`` and/or id ``prefix``."""
    bundle = Bundle.load(bundle_root)
    out: list[dict] = []
    for c in bundle.concepts:
        if type is not None and c.type != type:
            continue
        if prefix is not None and not c.id.startswith(prefix):
            continue
        out.append(
            {
                "id": c.id,
                "type": c.type,
                "title": c.title,
                "description": c.description,
                "tags": c.tags,
            }
        )
    return out


def read_index(
    bundle_root: "Path | str | Storage", dir: str | None = None, depth: int = 1
) -> list[dict]:
    """Return ``_index.md`` files for progressive disclosure, breadth-first.

    Starts at ``dir`` (bundle root if omitted) and descends ``depth`` levels
    (1..3). Missing ``_index.md`` files are skipped; read-only.
    """
    if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= 3:
        raise ValueError("depth must be an integer in 1..3")
    storage = open_storage(bundle_root)
    start = _clean_dir(dir)
    results: list[dict] = []
    level = [start]
    for _ in range(depth):
        nxt: list[str] = []
        for d in level:
            index_key = posixpath.join(d, INDEX_FILENAME)
            if storage.exists(index_key) and not storage.is_dir(index_key):
                results.append(
                    {
                        "dir": d,
                        "path": index_key,
                        "content": storage.read_text(index_key),
                    }
                )
            if storage.is_dir(d):
                nxt.extend(
                    posixpath.join(d, e.name)
                    for e in storage.list_dir(d)
                    if e.is_dir
                )
        level = nxt
        if not level:
            break
    return results


def _log_move(
    storage: Storage,
    from_key: str,
    to_key: str,
    frontmatter: dict,
    from_id: str,
    to_id: str,
) -> list[str]:
    """Append Move entries: an arrival in the dest dir log, and (when the source
    directory differs) a departure in the source dir log. Returns the logs."""
    label = str(frontmatter.get("title") or _id_of(_name_of(to_key)))
    dt = _now_utc()
    date_group, time = _utc_date(dt), _utc_time(dt)
    dest_log = _log_key(_dir_of(to_key))
    _append_log(
        storage,
        dest_log,
        f"* **{time}** **Move**: Moved [{label}]({_name_of(to_key)}) from `{from_id}`.",
        date_group,
    )
    logs = [dest_log]
    if _dir_of(from_key) != _dir_of(to_key):
        src_log = _log_key(_dir_of(from_key))
        _append_log(
            storage,
            src_log,
            f"* **{time}** **Move**: Moved [{label}]({_name_of(from_key)}) to `{to_id}`.",
            date_group,
        )
        logs.append(src_log)
    return logs


def _rewrite_inbound_links(
    storage: Storage, moved_id: str, id_map: dict[str, str]
) -> list[str]:
    """Rewrite links to the moved concept in every other concept document.

    Returns the ids of concepts whose body changed (sorted). The moved concept
    itself (now at ``moved_id``) is skipped -- its body was rewritten on write.
    """
    relinked: list[str] = []
    for c in Bundle.load(storage).concepts:
        if c.id == moved_id:
            continue
        d = posixpath.dirname(c.id)
        new_body = rewrite_link_ids(c.body, d, d, id_map)
        if new_body != c.body:
            storage.write_text(
                f"{c.id}.md",
                OKFDocument(frontmatter=c.document.frontmatter, body=new_body).serialize(),
            )
            relinked.append(c.id)
    return sorted(relinked)


def move_concept(
    bundle_root: "Path | str | Storage", from_concept_id: str, to_concept_id: str
) -> dict:
    """Relocate a concept to a new id: rewrite links, reindex, and log.

    Moves the file from ``from_concept_id`` to ``to_concept_id``, rewriting the
    moved document's own relative links for its new directory. Inbound links from
    other concepts are rewritten separately (see ``_rewrite_inbound_links``).
    Preserves frontmatter (including ``timestamp``). Fails if the source is
    missing, the destination exists, or the two ids are equal.
    """
    storage = open_storage(bundle_root)
    from_key = _concept_key(from_concept_id)
    to_key = _concept_key(to_concept_id)
    if from_key == to_key:
        raise ValueError("source and destination are the same concept")
    from_id = "/".join(parse_concept_id(from_concept_id))
    to_id = "/".join(parse_concept_id(to_concept_id))
    id_map = {from_id: to_id}

    with storage.lock():
        if not storage.exists(from_key):
            raise ValueError(f"concept not found: {from_concept_id}")
        if storage.exists(to_key):
            raise ValueError(f"destination already exists: {to_concept_id}")

        doc = OKFDocument.parse(storage.read_text(from_key))
        new_body = rewrite_link_ids(
            doc.body or "", _dir_of(from_key), _dir_of(to_key), id_map
        )
        storage.write_text(
            to_key, OKFDocument(frontmatter=doc.frontmatter, body=new_body).serialize()
        )
        storage.delete(from_key)

        relinked = _rewrite_inbound_links(storage, to_id, id_map)

        logs = _log_move(storage, from_key, to_key, doc.frontmatter, from_id, to_id)
        indexes = regenerate_indexes(storage)
    return {
        "from": from_id,
        "to": to_id,
        "action": "moved",
        "relinked": relinked,
        "logs": list(logs),
        "indexes": list(indexes),
    }


def _append_log_deletion(storage: Storage, concept_key: str, label: str) -> str:
    """Append a Deletion entry to the directory's log.

    The label is backticked (not a markdown link) because the file is gone --
    a link entry would itself be a dangling link.
    """
    log_key = _log_key(_dir_of(concept_key))
    dt = _now_utc()
    _append_log(
        storage,
        log_key,
        f"* **{_utc_time(dt)}** **Deletion**: Removed `{label}`.",
        _utc_date(dt),
    )
    return log_key


def delete_concept(
    bundle_root: "Path | str | Storage", concept_id: str, force: bool = False
) -> dict:
    """Delete a concept; safe by default, ``force`` unlinks inbound references.

    Collects every other concept whose body links to ``concept_id``. When such
    referrers exist and ``force`` is false, deletes nothing and returns the
    referrers (``action="blocked"``). Otherwise unlinks each inbound reference
    (``[label](target.md)`` -> ``label``), removes the file, appends a Deletion
    entry to the directory ``_log.md``, regenerates indexes, and returns a
    summary (``action="deleted"``). Fails if the concept does not exist or the
    id collides with a reserved file name.
    """
    storage = open_storage(bundle_root)
    key = _concept_key(concept_id)
    deleted_id = "/".join(parse_concept_id(concept_id))
    with storage.lock():
        if not storage.exists(key):
            raise ValueError(f"concept not found: {concept_id}")
        doc = OKFDocument.parse(storage.read_text(key))
        label = str(doc.frontmatter.get("title") or _id_of(_name_of(key)))

        # One pass: find every other concept whose body links to the deleted id.
        referrers: list[tuple[str, dict, str]] = []  # (id, fm, new_body)
        for c in Bundle.load(storage).concepts:
            if c.id == deleted_id:
                continue
            new_body = strip_link_ids(
                c.body, posixpath.dirname(c.id), {deleted_id}
            )
            if new_body != c.body:
                referrers.append((c.id, c.document.frontmatter, new_body))

        if referrers and not force:
            return {
                "concept_id": deleted_id,
                "action": "blocked",
                "referenced_by": sorted(rid for rid, _, _ in referrers),
            }

        unlinked: list[str] = []
        for rid, fm, new_body in referrers:
            storage.write_text(
                f"{rid}.md", OKFDocument(frontmatter=fm, body=new_body).serialize()
            )
            unlinked.append(rid)

        storage.delete(key)
        log_key = _append_log_deletion(storage, key, label)
        indexes = regenerate_indexes(storage)
    return {
        "concept_id": deleted_id,
        "path": key,
        "action": "deleted",
        "unlinked": sorted(unlinked),
        "log": log_key,
        "indexes": list(indexes),
    }


def _log_describe(storage: Storage, dir_key: str, cleared: bool) -> str:
    """Append an Update entry recording a directory-description change."""
    log_key = _log_key(dir_key)
    dt = _now_utc()
    what = "Cleared" if cleared else "Set"
    _append_log(
        storage,
        log_key,
        f"* **{_utc_time(dt)}** **Update**: {what} description for this directory.",
        _utc_date(dt),
    )
    return log_key


def describe_directory(
    bundle_root: "Path | str | Storage", dir: str, description: str
) -> dict:
    """Set or clear a directory's authored description in its ``_index.md`` frontmatter.

    An empty/whitespace ``description`` clears the key (reverting to the
    synthesized contents summary). Reindexes so the value reaches the parent's
    caption, and appends an Update entry to the directory's ``_log.md``. Fails if
    ``dir`` escapes the bundle root, is not a directory, or has no ``_index.md``
    (directories only exist once populated, so there is always an index to edit).
    """
    storage = open_storage(bundle_root)
    target = _clean_dir(dir)
    with storage.lock():
        if not storage.is_dir(target):
            raise ValueError(f"directory not found: {dir}")
        index_key = posixpath.join(target, INDEX_FILENAME)
        if not storage.exists(index_key) or storage.is_dir(index_key):
            raise ValueError(f"directory has no {INDEX_FILENAME}: {dir}")

        doc = OKFDocument.parse(storage.read_text(index_key))
        fm = dict(doc.frontmatter)
        desc = description.strip()
        cleared = not desc
        if cleared:
            fm.pop("description", None)
        else:
            fm["description"] = desc

        if fm:
            storage.write_text(
                index_key, OKFDocument(frontmatter=fm, body=doc.body).serialize()
            )
        else:
            body = doc.body if doc.body.endswith("\n") else doc.body + "\n"
            storage.write_text(index_key, body)

        log_key = _log_describe(storage, target, cleared)
        indexes = regenerate_indexes(storage)
    return {
        "dir": target,
        "action": "cleared" if cleared else "described",
        "description": None if cleared else desc,
        "log": log_key,
        "indexes": list(indexes),
    }


_MAX_TOP_K = 20


def search_workspace(
    workspace: Workspace,
    query: str,
    top_k: int = 5,
    bundles: list[str] | None = None,
    dir: str | None = None,
    *,
    config: EmbeddingConfig | None,
    max_chars: int = 6000,
    embed: Embedder | None = None,
    db_path: Path | str | None = None,
) -> list[dict]:
    """Semantic search over the ``_index.md`` files and descriptions of a
    workspace's bundles (all of them unless ``bundles`` narrows the scope).

    Syncs the workspace vector store first (embedding only what changed, and
    dropping bundles no longer on disk), then returns up to ``top_k`` hits
    ``{bundle, kind, dir, path, score, excerpt}``, ranked together, best first.
    ``dir`` needs exactly one bundle in scope. Raises if the embedding server
    fails; never answers from a store it could not bring up to date.
    ``db_path`` overrides the workspace's ``.okf/vectors.db`` (tests).
    """
    if not query or not query.strip():
        raise ValueError("query must not be blank")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= _MAX_TOP_K:
        raise ValueError(f"top_k must be an integer in 1..{_MAX_TOP_K}")
    present = workspace.indexes()
    scope = present if bundles is None else list(dict.fromkeys(bundles))
    missing = [b for b in scope if b not in present]
    if missing:
        raise FileNotFoundError(
            f"no bundle {missing[0]!r} in workspace {workspace.name!r}; "
            f"bundles: {', '.join(present) or '(none)'}"
        )
    start = _clean_dir(dir)
    if start and len(scope) != 1:
        raise ValueError("dir requires exactly one bundle")
    if config is None:
        raise ValueError(
            "embedding is not configured: set OKF_EMBEDDING_URL and OKF_EMBEDDING_MODEL"
        )
    embedder = embed or (lambda texts: embed_texts(texts, config))
    store = VectorStore(db_path or workspace_db_path(workspace))
    try:
        store.prune_bundles(set(present))
        def sync_scope() -> bool:
            rebuilt = False
            for name in scope:
                rebuilt |= store.sync(
                    workspace.bundle_storage(name),
                    embedder,
                    bundle=name,
                    description=workspace.description(name),
                    model=config.model,
                    max_chars=max_chars,
                )
            return rebuilt

        if sync_scope():  # a rebuild emptied bundles synced earlier in the loop
            sync_scope()
        if not scope:
            return []
        return store.query(embedder([query])[0], top_k, bundles=scope, dir=start)
    finally:
        store.close()


def create_bundle(workspace: Workspace, name: str, description: str | None = None) -> dict:
    """Create an empty bundle ``name`` in ``workspace`` with an optional
    description. ``FileExistsError`` if it exists. Its first ``_index.md`` appears
    with its first concept (indexes only cover directories holding documents)."""
    workspace.create_index(name, description)
    return {"bundle": name, "description": workspace.description(name)}
