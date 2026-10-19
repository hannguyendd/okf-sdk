"""Validate an OKF bundle against the conformance-blocking MUST rules.

This checks the nine MUST / MUST NOT rules of OKF v0.1 (see ``CONFORMANCE.md``
§5). It is intentionally stricter than :class:`okf_core.bundle.Bundle`, which is
permissive and silently skips malformed or reserved files; the validator instead
reports every violation it finds.

Run as a script::

    python -m okf_core.validate path/to/bundle
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from okf_core.constants import INDEX_FILENAME, LOG_FILENAME
from okf_core.storage import Storage, open_storage

_FRONTMATTER_DELIM = "---"

_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S", re.MULTILINE)
_BULLET_RE = re.compile(r"^[ \t]*[-*+][ \t]+(.*)$", re.MULTILINE)
_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
_LEVEL2_HEADING_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


@dataclass
class Violation:
    """A single conformance-blocking failure."""

    rule: str
    path: str
    message: str


def _split_frontmatter(text: str) -> tuple[str, dict[str, Any]]:
    """Classify a document's leading frontmatter block.

    Returns ``(status, frontmatter)`` where status is one of ``missing``,
    ``unterminated``, ``invalid_yaml``, ``not_mapping``, or ``ok``. The mapping
    is populated only when status is ``ok``.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return ("missing", {})
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            end = i
            break
    if end is None:
        return ("unterminated", {})
    try:
        fm = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError:
        return ("invalid_yaml", {})
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        return ("not_mapping", {})
    return ("ok", fm)


def _check_concept(rel: str, text: str) -> list[Violation]:
    out: list[Violation] = []
    status, fm = _split_frontmatter(text)
    if status in ("missing", "unterminated"):
        out.append(
            Violation(
                "DOC-02",
                rel,
                "concept document has no terminated '---' frontmatter block",
            )
        )
        return out
    if status in ("invalid_yaml", "not_mapping"):
        out.append(Violation("DOC-03", rel, "frontmatter is not a YAML mapping"))
        return out
    type_value = fm.get("type")
    if not isinstance(type_value, str) or not type_value.strip():
        out.append(
            Violation("FM-01", rel, "frontmatter has no non-empty string 'type'")
        )
    return out


def _check_index(rel: str, text: str, is_root: bool) -> list[Violation]:
    out: list[Violation] = []
    lines = text.splitlines()
    has_block = bool(lines) and lines[0].strip() == _FRONTMATTER_DELIM
    if has_block:
        status, fm = _split_frontmatter(text)
        allowed = {"description", "okf_version"} if is_root else {"description"}
        if status != "ok" or set(fm) - allowed:
            allowed_str = "', '".join(sorted(allowed))
            out.append(
                Violation(
                    "IDX-01",
                    rel,
                    f"{INDEX_FILENAME} frontmatter may declare only '{allowed_str}'",
                )
            )
    if not _HEADING_RE.search(text):
        out.append(Violation("IDX-02", rel, f"{INDEX_FILENAME} has no section heading"))
    for bullet in _BULLET_RE.findall(text):
        if not _LINK_RE.search(bullet):
            out.append(
                Violation(
                    "IDX-02", rel, f"{INDEX_FILENAME} list entry is not a markdown link"
                )
            )
            break
    return out


def _check_log(rel: str, text: str) -> list[Violation]:
    out: list[Violation] = []
    lines = text.splitlines()
    if lines and lines[0].strip() == _FRONTMATTER_DELIM:
        out.append(
            Violation(
                "RSV-01",
                rel,
                f"{LOG_FILENAME} must not be used as a concept (has frontmatter)",
            )
        )
    for heading in _LEVEL2_HEADING_RE.findall(text):
        try:
            datetime.strptime(heading.strip(), "%Y-%m-%d")
        except ValueError:
            out.append(
                Violation(
                    "LOG-01",
                    rel,
                    f"{LOG_FILENAME} date heading '{heading.strip()}' is not ISO YYYY-MM-DD",
                )
            )
    return out


def validate_bundle(root: Path | str | Storage) -> list[Violation]:
    """Return every MUST / MUST NOT violation in the bundle at ``root``.

    An empty list means the bundle is conformant with OKF v0.1. Raises
    ``FileNotFoundError`` if ``root`` is not a directory.
    """
    storage = open_storage(root)
    if not storage.is_dir(""):
        raise FileNotFoundError(f"Bundle directory not found: {storage.location}")
    violations: list[Violation] = []
    for rel in storage.iter_files(suffix=".md"):
        name = rel.rsplit("/", 1)[-1]
        try:
            text = storage.read_text(rel)
        except UnicodeDecodeError:
            violations.append(Violation("DOC-01", rel, "file is not valid UTF-8"))
            continue
        if name == INDEX_FILENAME:
            violations.extend(_check_index(rel, text, is_root=rel == INDEX_FILENAME))
        elif name == LOG_FILENAME:
            violations.extend(_check_log(rel, text))
        else:
            violations.extend(_check_concept(rel, text))
    return violations


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m okf_core.validate <bundle-dir>", file=sys.stderr)
        return 2
    root = Path(argv[0])
    try:
        violations = validate_bundle(root)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    if not violations:
        print(f"OK: {root} is a conformant OKF v0.1 bundle.")
        return 0
    for v in sorted(violations, key=lambda v: (v.path, v.rule)):
        print(f"{v.path}: {v.rule}: {v.message}")
    print(f"\n{len(violations)} violation(s).", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
