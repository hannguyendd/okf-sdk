"""Producer operations over an OKF bundle (framework-agnostic)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from okf_core import (
    OKFDocument,
    concept_id_to_path,
    parse_concept_id,
    regenerate_indexes,
)

_RESERVED = ("index", "log")


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
    if parts[-1] in _RESERVED:
        raise ValueError(
            f"concept_id {concept_id!r} collides with a reserved file name"
        )
    return concept_id_to_path(bundle_root, parts)


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _today_iso() -> str:
    return date.today().isoformat()


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
    log_path = concept_path.parent / "log.md"
    entry = f"* **{action}**: {verb} [{label}]({concept_path.name})."
    _append_log(log_path, entry, _today_iso())
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
