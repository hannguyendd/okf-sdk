"""Workspaces: named directories under ``~/.okf/workspaces``.

A *workspace* is itself one OKF bundle: its root holds the concepts.
Workspace metadata (the colour; ``vectors.db``) lives in the hidden
``<workspace>/.okf/`` folder, which holds no concept files.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from okf_core.bundle import Bundle
from okf_core.storage import Storage, open_storage

OKF_HOME_ENV = "OKF_HOME"
METADATA_DIR = ".okf"
WORKSPACE_FILE = "workspace.json"
#: Colours a workspace may be tagged with (UI accent; names, not hex values).
WORKSPACE_COLORS = ("yellow", "pink", "green", "blue", "red", "orange", "purple")
_WORKSPACE_FILE_VERSION = 2
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def okf_home(home: Path | str | None = None) -> Path:
    """The ``.okf`` directory: explicit arg > ``OKF_HOME`` env > ``~/.okf``.

    Pure: nothing is created.
    """
    if home is not None:
        return Path(home)
    env = os.environ.get(OKF_HOME_ENV)
    if env:
        return Path(env)
    return Path.home() / ".okf"


def _validate_name(name: str, kind: str) -> str:
    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid {kind} name: {name!r}")
    return name


def _subdirs(storage: Storage) -> list[str]:
    try:
        entries = storage.list_dir("")
    except FileNotFoundError:
        return []
    return [e.name for e in entries if e.is_dir]


@dataclass(frozen=True)
class Workspace:
    name: str
    storage: Storage

    @property
    def path(self) -> Path | None:
        """Local directory of the workspace, or ``None`` for non-local storage."""
        root = getattr(self.storage, "root", None)
        return Path(root) if root is not None else None

    def load(self) -> Bundle:
        """The workspace as an OKF bundle."""
        return Bundle.load(self.storage)

    def meta_storage(self) -> Storage:
        return self.storage.child(METADATA_DIR)

    # -- metadata (``.okf/workspace.json``) ---------------------------------

    def _read_meta(self) -> dict:
        key = f"{METADATA_DIR}/{WORKSPACE_FILE}"
        try:
            text = self.storage.read_text(key)
        except FileNotFoundError:
            return {"version": _WORKSPACE_FILE_VERSION}
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ValueError(f"corrupt {key} in workspace {self.name!r}: {exc}") from exc
        if isinstance(data, dict) and data.get("version") == 1:
            raise ValueError(f"{key} is version 1; run okf-migrate-v2")
        if not isinstance(data, dict) or data.get("version") != _WORKSPACE_FILE_VERSION:
            raise ValueError(
                f"unsupported or corrupt {key} in workspace {self.name!r}: "
                f"expected {{\"version\": {_WORKSPACE_FILE_VERSION}}}"
            )
        return data

    def _write_meta(self, data: dict) -> None:
        self.storage.write_text(
            f"{METADATA_DIR}/{WORKSPACE_FILE}",
            json.dumps(data, indent=2, sort_keys=True) + "\n",
        )

    def color(self) -> str | None:
        """The workspace's colour (one of ``WORKSPACE_COLORS``), or ``None``."""
        color = self._read_meta().get("color")
        return color if color in WORKSPACE_COLORS else None

    def set_color(self, color: str | None) -> str | None:
        """Set (or clear, with ``None``/blank) the workspace colour; returns it."""
        color = color.strip() if isinstance(color, str) else None
        if not color:
            color = None
        elif color not in WORKSPACE_COLORS:
            raise ValueError(f"Invalid color {color!r}; choose one of {', '.join(WORKSPACE_COLORS)}")
        with self.storage.lock():
            data = self._read_meta()
            if color is None:
                data.pop("color", None)
            else:
                data["color"] = color
            self._write_meta(data)
        return color

class WorkspaceRegistry:
    """The set of workspaces under ``<okf home>/workspaces``."""

    def __init__(self, root: Path | str | Storage | None = None) -> None:
        if root is None:
            root = okf_home() / "workspaces"
        self.root = root if isinstance(root, Storage) else Path(root)
        self.storage = open_storage(root)

    def _workspace(self, name: str) -> Workspace:
        return Workspace(name, self.storage.child(name))

    def exists(self, name: str) -> bool:
        return self.storage.is_dir(_validate_name(name, "workspace"))

    def create(self, name: str) -> Workspace:
        _validate_name(name, "workspace")
        if self.storage.exists(name):
            raise FileExistsError(f"Workspace {name!r} already exists")
        self.storage.mkdir(name)
        ws = self._workspace(name)
        # Stamp the v2 marker so okf-migrate-v2 (which reads a missing file as
        # v1) never rewrites a workspace created after the upgrade.
        ws._write_meta({"version": _WORKSPACE_FILE_VERSION})
        return ws

    def get(self, name: str) -> Workspace:
        if not self.exists(name):
            raise FileNotFoundError(f"No workspace {name!r}")
        return self._workspace(name)

    def list(self) -> list[Workspace]:
        return [self._workspace(n) for n in _subdirs(self.storage) if _NAME_RE.fullmatch(n)]
