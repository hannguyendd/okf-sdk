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
