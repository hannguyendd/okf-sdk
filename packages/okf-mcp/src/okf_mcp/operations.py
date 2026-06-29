"""Producer operations over an OKF bundle (framework-agnostic)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from okf_core import concept_id_to_path, parse_concept_id

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
