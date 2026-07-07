"""Producer operations over an OKF bundle (framework-agnostic)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from okf_core import (
    INDEX_FILENAME,
    LOG_FILENAME,
    RESERVED_STEMS,
    Bundle,
    OKFDocument,
    concept_id_to_path,
    extract_links,
    parse_concept_id,
    regenerate_indexes,
    rewrite_links,
    strip_links,
)


def resolve_bundle_root(arg: str | None, env_default: Path | None) -> Path:
    """Resolve the bundle root from a call arg, falling back to the env default.

    Raises ``ValueError`` when neither is set or the path is not a directory.
    """
    chosen = arg or env_default
    if not chosen:
        raise ValueError("no bundle root: pass bundle_root or set OKF_BUNDLE_ROOT")
    root = Path(chosen).resolve()
    if not root.is_dir():
        raise ValueError(f"bundle root is not a directory: {root}")
    return root


def _concept_path(bundle_root: Path, concept_id: str) -> Path:
    parts = parse_concept_id(concept_id)
    if parts[-1] in RESERVED_STEMS:
        raise ValueError(
            f"concept_id {concept_id!r} collides with a reserved file name"
        )
    return concept_id_to_path(bundle_root, parts)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now_iso() -> str:
    return _now_utc().isoformat().replace("+00:00", "Z")


def _utc_date(dt: datetime) -> str:
    return dt.date().isoformat()


def _utc_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S") + "Z"


def _append_log(log_path: Path, entry: str, today: str) -> None:
    """Append ``entry`` under a ``## <today>`` group in ``log_path`` (newest-first).

    Creates the file with a ``# Update Log`` title when absent; prepends the
    entry under an existing today group; otherwise inserts a new today group
    above older date groups.
    """
    heading = f"## {today}"
    if not log_path.exists():
        log_path.write_text(f"# Update Log\n\n{heading}\n{entry}\n", encoding="utf-8")
        return
    lines = log_path.read_text(encoding="utf-8").splitlines()
    first_h2 = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), None)
    if first_h2 is not None and lines[first_h2].strip() == heading:
        new_lines = lines[: first_h2 + 1] + [entry] + lines[first_h2 + 1 :]
    elif first_h2 is not None:
        new_lines = lines[:first_h2] + [heading, entry, ""] + lines[first_h2:]
    else:
        new_lines = lines + ["", heading, entry]
    log_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def _append_log_for(concept_path: Path, label: str, action: str, verb: str) -> Path:
    log_path = concept_path.parent / LOG_FILENAME
    dt = _now_utc()
    entry = (
        f"* **{_utc_time(dt)}** **{action}**: {verb} [{label}]({concept_path.name})."
    )
    _append_log(log_path, entry, _utc_date(dt))
    return log_path


def _summary(
    bundle_root: Path,
    concept_id: str,
    path: Path,
    action: str,
    log_path: Path,
    indexes: list[Path],
) -> dict:
    return {
        "concept_id": concept_id,
        "path": path.relative_to(bundle_root).as_posix(),
        "action": action,
        "log": log_path.relative_to(bundle_root).as_posix(),
        "indexes": [Path(p).relative_to(bundle_root).as_posix() for p in indexes],
    }


def add_concept(
    bundle_root: Path, concept_id: str, frontmatter: dict, body: str
) -> dict:
    """Create a new concept document, then reindex and log the creation."""
    path = _concept_path(bundle_root, concept_id)
    if path.exists():
        raise ValueError(f"concept already exists: {concept_id}")
    fm = dict(frontmatter or {})
    type_val = fm.get("type")
    if not isinstance(type_val, str) or not type_val.strip():
        raise ValueError("frontmatter must include a non-empty string 'type'")
    if not fm.get("timestamp"):
        fm["timestamp"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        OKFDocument(frontmatter=fm, body=body or "").serialize(), encoding="utf-8"
    )
    label = str(fm.get("title") or path.stem)
    log_path = _append_log_for(path, label, "Creation", "Added")
    indexes = regenerate_indexes(bundle_root)
    return _summary(bundle_root, concept_id, path, "created", log_path, indexes)


def patch_concept(
    bundle_root: Path,
    concept_id: str,
    frontmatter: dict | None = None,
    body: str | None = None,
) -> dict:
    """Update an existing concept (merge frontmatter, optional body), reindex, log."""
    path = _concept_path(bundle_root, concept_id)
    if not path.exists():
        raise ValueError(f"concept not found: {concept_id}")
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    fm = dict(doc.frontmatter)
    caller_ts = False
    for key, value in (frontmatter or {}).items():
        if value is not None:
            fm[key] = value
            if key == "timestamp":
                caller_ts = True
    new_body = doc.body if body is None else body
    if not caller_ts:
        fm["timestamp"] = _now_iso()
    path.write_text(
        OKFDocument(frontmatter=fm, body=new_body).serialize(), encoding="utf-8"
    )
    label = str(fm.get("title") or path.stem)
    log_path = _append_log_for(path, label, "Update", "Updated")
    indexes = regenerate_indexes(bundle_root)
    return _summary(bundle_root, concept_id, path, "updated", log_path, indexes)


def reindex_bundle(bundle_root: Path) -> dict:
    """Regenerate every ``_index.md`` in the bundle from current content.

    Repairs indexes that have drifted (e.g. files edited outside the producer
    tools). This is index maintenance, not a concept change, so it does not
    touch ``_log.md``. Returns the regenerated index paths and their count.
    """
    indexes = regenerate_indexes(bundle_root)
    return {
        "action": "reindexed",
        "indexes": [Path(p).relative_to(bundle_root).as_posix() for p in indexes],
        "count": len(indexes),
    }


def get_concept(bundle_root: Path, concept_id: str) -> dict:
    """Read one concept: frontmatter, body, and resolved outgoing links."""
    path = _concept_path(bundle_root, concept_id)
    if not path.exists():
        raise ValueError(f"concept not found: {concept_id}")
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    links = extract_links(doc.body or "", path.parent, bundle_root)
    return {
        "id": concept_id,
        "frontmatter": doc.frontmatter,
        "body": doc.body,
        "links_to": links,
    }


def list_concepts(
    bundle_root: Path, type: str | None = None, prefix: str | None = None
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


def _rel_dir(bundle_root: Path, directory: Path) -> str:
    if directory == bundle_root:
        return ""
    return directory.relative_to(bundle_root).as_posix()


def read_index(bundle_root: Path, dir: str | None = None, depth: int = 1) -> list[dict]:
    """Return ``_index.md`` files for progressive disclosure, breadth-first.

    Starts at ``dir`` (bundle root if omitted) and descends ``depth`` levels
    (1..3). Missing ``_index.md`` files are skipped; read-only.
    """
    if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= 3:
        raise ValueError("depth must be an integer in 1..3")
    root = bundle_root.resolve()
    start = root if not dir else (root / dir).resolve()
    if start != root and root not in start.parents:
        raise ValueError(f"dir escapes the bundle root: {dir}")
    results: list[dict] = []
    level = [start]
    for _ in range(depth):
        nxt: list[Path] = []
        for d in level:
            index_file = d / INDEX_FILENAME
            if index_file.is_file():
                results.append(
                    {
                        "dir": _rel_dir(root, d),
                        "path": index_file.relative_to(root).as_posix(),
                        "content": index_file.read_text(encoding="utf-8"),
                    }
                )
            if d.is_dir():
                nxt.extend(sorted(p for p in d.iterdir() if p.is_dir()))
        level = nxt
        if not level:
            break
    return results


def _log_move(
    from_path: Path,
    to_path: Path,
    frontmatter: dict,
    from_id: str,
    to_id: str,
) -> list[Path]:
    """Append Move entries: an arrival in the dest dir log, and (when the source
    directory differs) a departure in the source dir log. Returns the logs."""
    label = str(frontmatter.get("title") or to_path.stem)
    dt = _now_utc()
    date_group, time = _utc_date(dt), _utc_time(dt)
    dest_log = to_path.parent / LOG_FILENAME
    _append_log(
        dest_log,
        f"* **{time}** **Move**: Moved [{label}]({to_path.name}) from `{from_id}`.",
        date_group,
    )
    logs = [dest_log]
    if from_path.parent != to_path.parent:
        src_log = from_path.parent / LOG_FILENAME
        _append_log(
            src_log,
            f"* **{time}** **Move**: Moved [{label}]({from_path.name}) to `{to_id}`.",
            date_group,
        )
        logs.append(src_log)
    return logs


def _rewrite_inbound_links(
    bundle_root: Path, moved_id: str, id_map: dict[str, str]
) -> list[str]:
    """Rewrite links to the moved concept in every other concept document.

    Returns the ids of concepts whose body changed (sorted). The moved concept
    itself (now at ``moved_id``) is skipped -- its body was rewritten on write.
    """
    bundle = Bundle.load(bundle_root)
    relinked: list[str] = []
    for c in bundle.concepts:
        if c.id == moved_id:
            continue
        path = concept_id_to_path(bundle_root, parse_concept_id(c.id))
        new_body = rewrite_links(c.body, path.parent, path.parent, bundle_root, id_map)
        if new_body != c.body:
            path.write_text(
                OKFDocument(
                    frontmatter=c.document.frontmatter, body=new_body
                ).serialize(),
                encoding="utf-8",
            )
            relinked.append(c.id)
    return sorted(relinked)


def move_concept(bundle_root: Path, from_concept_id: str, to_concept_id: str) -> dict:
    """Relocate a concept to a new id: rewrite links, reindex, and log.

    Moves the file from ``from_concept_id`` to ``to_concept_id``, rewriting the
    moved document's own relative links for its new directory. Inbound links from
    other concepts are rewritten separately (see ``_rewrite_inbound_links``).
    Preserves frontmatter (including ``timestamp``). Fails if the source is
    missing, the destination exists, or the two ids are equal.
    """
    from_path = _concept_path(bundle_root, from_concept_id)
    to_path = _concept_path(bundle_root, to_concept_id)
    if from_path == to_path:
        raise ValueError("source and destination are the same concept")
    if not from_path.exists():
        raise ValueError(f"concept not found: {from_concept_id}")
    if to_path.exists():
        raise ValueError(f"destination already exists: {to_concept_id}")

    from_id = "/".join(parse_concept_id(from_concept_id))
    to_id = "/".join(parse_concept_id(to_concept_id))
    id_map = {from_id: to_id}

    doc = OKFDocument.parse(from_path.read_text(encoding="utf-8"))
    new_body = rewrite_links(
        doc.body or "", from_path.parent, to_path.parent, bundle_root, id_map
    )
    to_path.parent.mkdir(parents=True, exist_ok=True)
    to_path.write_text(
        OKFDocument(frontmatter=doc.frontmatter, body=new_body).serialize(),
        encoding="utf-8",
    )
    from_path.unlink()

    relinked = _rewrite_inbound_links(bundle_root, to_id, id_map)

    logs = _log_move(from_path, to_path, doc.frontmatter, from_id, to_id)
    indexes = regenerate_indexes(bundle_root)
    return {
        "from": from_id,
        "to": to_id,
        "action": "moved",
        "relinked": relinked,
        "logs": [Path(p).relative_to(bundle_root).as_posix() for p in logs],
        "indexes": [Path(p).relative_to(bundle_root).as_posix() for p in indexes],
    }


def _append_log_deletion(concept_path: Path, label: str) -> Path:
    """Append a Deletion entry to the directory's log.

    The label is backticked (not a markdown link) because the file is gone --
    a link entry would itself be a dangling link.
    """
    log_path = concept_path.parent / LOG_FILENAME
    dt = _now_utc()
    _append_log(
        log_path,
        f"* **{_utc_time(dt)}** **Deletion**: Removed `{label}`.",
        _utc_date(dt),
    )
    return log_path


def delete_concept(bundle_root: Path, concept_id: str, force: bool = False) -> dict:
    """Delete a concept; safe by default, ``force`` unlinks inbound references.

    Collects every other concept whose body links to ``concept_id``. When such
    referrers exist and ``force`` is false, deletes nothing and returns the
    referrers (``action="blocked"``). Otherwise unlinks each inbound reference
    (``[label](target.md)`` -> ``label``), removes the file, appends a Deletion
    entry to the directory ``_log.md``, regenerates indexes, and returns a
    summary (``action="deleted"``). Fails if the concept does not exist or the
    id collides with a reserved file name.
    """
    path = _concept_path(bundle_root, concept_id)
    if not path.exists():
        raise ValueError(f"concept not found: {concept_id}")
    deleted_id = "/".join(parse_concept_id(concept_id))
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    label = str(doc.frontmatter.get("title") or path.stem)

    # One pass: find every other concept whose body links to the deleted id.
    referrers: list[tuple[str, Path, dict, str]] = []  # (id, path, fm, new_body)
    for c in Bundle.load(bundle_root).concepts:
        if c.id == deleted_id:
            continue
        c_path = concept_id_to_path(bundle_root, parse_concept_id(c.id))
        new_body = strip_links(c.body, c_path.parent, bundle_root, {deleted_id})
        if new_body != c.body:
            referrers.append((c.id, c_path, c.document.frontmatter, new_body))

    if referrers and not force:
        return {
            "concept_id": deleted_id,
            "action": "blocked",
            "referenced_by": sorted(rid for rid, _, _, _ in referrers),
        }

    unlinked: list[str] = []
    for rid, c_path, fm, new_body in referrers:
        c_path.write_text(
            OKFDocument(frontmatter=fm, body=new_body).serialize(),
            encoding="utf-8",
        )
        unlinked.append(rid)

    path.unlink()
    log_path = _append_log_deletion(path, label)
    indexes = regenerate_indexes(bundle_root)
    return {
        "concept_id": deleted_id,
        "path": path.relative_to(bundle_root).as_posix(),
        "action": "deleted",
        "unlinked": sorted(unlinked),
        "log": log_path.relative_to(bundle_root).as_posix(),
        "indexes": [Path(p).relative_to(bundle_root).as_posix() for p in indexes],
    }


def _log_describe(index_path: Path, cleared: bool) -> Path:
    """Append an Update entry recording a directory-description change."""
    log_path = index_path.parent / LOG_FILENAME
    dt = _now_utc()
    what = "Cleared" if cleared else "Set"
    _append_log(
        log_path,
        f"* **{_utc_time(dt)}** **Update**: {what} description for this directory.",
        _utc_date(dt),
    )
    return log_path


def describe_directory(bundle_root: Path, dir: str, description: str) -> dict:
    """Set or clear a directory's authored description in its ``_index.md`` frontmatter.

    An empty/whitespace ``description`` clears the key (reverting to the
    synthesized contents summary). Reindexes so the value reaches the parent's
    caption, and appends an Update entry to the directory's ``_log.md``. Fails if
    ``dir`` escapes the bundle root, is not a directory, or has no ``_index.md``
    (directories only exist once populated, so there is always an index to edit).
    """
    root = bundle_root.resolve()
    target = root if not dir else (root / dir).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"dir escapes the bundle root: {dir}")
    if not target.is_dir():
        raise ValueError(f"directory not found: {dir}")
    index_path = target / INDEX_FILENAME
    if not index_path.is_file():
        raise ValueError(f"directory has no {INDEX_FILENAME}: {dir}")

    doc = OKFDocument.parse(index_path.read_text(encoding="utf-8"))
    fm = dict(doc.frontmatter)
    desc = description.strip()
    cleared = not desc
    if cleared:
        fm.pop("description", None)
    else:
        fm["description"] = desc

    if fm:
        index_path.write_text(
            OKFDocument(frontmatter=fm, body=doc.body).serialize(), encoding="utf-8"
        )
    else:
        body = doc.body if doc.body.endswith("\n") else doc.body + "\n"
        index_path.write_text(body, encoding="utf-8")

    log_path = _log_describe(index_path, cleared)
    indexes = regenerate_indexes(root)
    return {
        "dir": _rel_dir(root, target),
        "action": "cleared" if cleared else "described",
        "description": None if cleared else desc,
        "log": log_path.relative_to(root).as_posix(),
        "indexes": [Path(p).relative_to(root).as_posix() for p in indexes],
    }
