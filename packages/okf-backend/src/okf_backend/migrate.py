"""``okf-migrate-v2``: migrate bundle-era (v1) workspaces to the v2 layout.

In v1 each visible top-level directory of a workspace was a *bundle* whose
concept links were rooted at that directory (``/t.md``). In v2 the workspace
itself is the one bundle, so those links gain the directory as a prefix
(``/B/t.md``), bundle descriptions move into each directory's ``_index.md``,
and ``okf_version`` moves to the workspace root ``_index.md``.
"""
from __future__ import annotations

import argparse
import json
import sys

from okf_core import (
    INDEX_FILENAME,
    METADATA_DIR,
    RESERVED_FILENAMES,
    WORKSPACE_FILE,
    OKFDocument,
    Storage,
    WorkspaceRegistry,
    map_absolute_links,
)

from okf_backend.operations import reindex_bundle

_META_KEY = f"{METADATA_DIR}/{WORKSPACE_FILE}"
_VECTORS_KEY = f"{METADATA_DIR}/vectors.db"


def _version_key(v: object) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in str(v).split("."))
    except ValueError:
        return (-1,)


def _read_v1(storage: Storage) -> dict:
    try:
        text = storage.read_text(_META_KEY)
    except FileNotFoundError:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"corrupt {_META_KEY}")
    return data


def _old_bundles(storage: Storage) -> list[str]:
    try:
        entries = storage.list_dir("")
    except FileNotFoundError:
        return []
    return sorted(e.name for e in entries if e.is_dir and not e.name.startswith((".", "_")))


def migrate_workspace(storage: Storage, *, dry_run: bool = False) -> list[str]:
    """Migrate one workspace in place; returns one line per action or warning.

    Every new file text is computed into a plan before the first write, so a
    parse or data error leaves the workspace untouched (a re-run can never
    double-prefix links). With ``dry_run`` the plan is logged, never applied.
    """
    meta = _read_v1(storage)
    version = meta.get("version", 1) if meta else 1
    if isinstance(version, bool) or version not in (1, 2):
        raise ValueError(f"unsupported {_META_KEY} version {version!r}; expected 1 or 2")
    if version == 2:
        return ["already v2"]
    descriptions = meta.get("bundles") or {}
    if not isinstance(descriptions, dict):
        descriptions = {}
    log: list[str] = []
    plan: dict[str, str] = {}

    versions: dict[str, object] = {}
    for b in _old_bundles(storage):
        for key in sorted(storage.iter_files(b, ".md")):
            if key.rsplit("/", 1)[-1] in RESERVED_FILENAMES:
                continue
            doc = OKFDocument.parse(storage.read_text(key))
            new_body = map_absolute_links(doc.body, lambda t, b=b: f"{b}/{t}")
            if new_body != doc.body:
                doc.body = new_body
                plan[key] = doc.serialize()
                log.append(f"rewrote links in {key}")

        index_key = f"{b}/{INDEX_FILENAME}"
        doc = (
            OKFDocument.parse(storage.read_text(index_key))
            if storage.exists(index_key)
            else OKFDocument()
        )
        changed = False
        entry = descriptions.get(b)
        desc = entry.get("description") if isinstance(entry, dict) else None
        if desc:
            if doc.frontmatter.get("description"):
                log.append(f"kept _index.md description for {b}")
            else:
                doc.frontmatter["description"] = desc
                changed = True
                log.append(f"moved description of {b} into {index_key}")
        if "okf_version" in doc.frontmatter:
            versions[b] = doc.frontmatter.pop("okf_version")
            changed = True
        if changed:
            plan[index_key] = doc.serialize()

    root_key = INDEX_FILENAME
    root_doc = (
        OKFDocument.parse(storage.read_text(root_key)) if storage.exists(root_key) else OKFDocument()
    )
    candidates = list(versions.values())
    if root_doc.frontmatter.get("okf_version"):
        candidates.append(root_doc.frontmatter["okf_version"])
    if candidates:
        best = max(candidates, key=_version_key)
        if len({str(v) for v in candidates}) > 1:
            log.append(
                "warning: okf_version values differ across bundles "
                f"({', '.join(sorted({str(v) for v in candidates}))}); using {best}"
            )
        if root_doc.frontmatter.get("okf_version") != best:
            root_doc.frontmatter["okf_version"] = best
            plan[root_key] = root_doc.serialize()
            log.append(f"set okf_version {best} on root {INDEX_FILENAME}")

    new_meta: dict = {"version": 2}
    if meta.get("color"):
        new_meta["color"] = meta["color"]
    # Marker last in the plan: it flips the workspace to v2 only after all
    # content writes; the reindex that follows is re-runnable.
    plan[_META_KEY] = json.dumps(new_meta, indent=2, sort_keys=True) + "\n"
    log.append(f"wrote {_META_KEY} (version 2)")
    has_vectors = storage.exists(_VECTORS_KEY)
    if has_vectors:
        log.append(f"deleted {_VECTORS_KEY} (rebuilt on next search)")
    log.append("regenerated _index.md files")

    if not dry_run:
        for key, text in plan.items():
            storage.write_text(key, text)
        if has_vectors:
            storage.delete(_VECTORS_KEY)
        reindex_bundle(storage)
    return log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="okf-migrate-v2", description="Migrate bundle-era OKF workspaces to v2."
    )
    parser.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    args = parser.parse_args(argv)
    failed = False
    for ws in WorkspaceRegistry().list():
        print(f"{ws.name}:")
        try:
            lines = migrate_workspace(ws.storage, dry_run=args.dry_run)
        except Exception as exc:  # keep going with the other workspaces
            print(f"  error: {exc}", file=sys.stderr)
            failed = True
            continue
        for line in lines:
            print(f"  {line}")
    if failed:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
