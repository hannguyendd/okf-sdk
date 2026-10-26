"""Workspaces: named directories under ``~/.okf/workspaces`` holding indexes.

A *workspace* is a git-repo-shaped directory; an *index* is a collection of
concepts inside it, and is exactly one bundle (a visible top-level directory).
Workspace metadata (bundle descriptions) lives in ``<workspace>/.okf/``, which
the hidden-name rule keeps from ever being mistaken for an index.
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
MAX_DESCRIPTION_CHARS = 1000
_WORKSPACE_FILE_VERSION = 1
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


def _clean_description(text: str | None) -> str | None:
    if text is None or not text.strip():
        return None
    text = text.strip()
    if len(text) > MAX_DESCRIPTION_CHARS:
        raise ValueError(
            f"description is {len(text)} chars; the maximum is {MAX_DESCRIPTION_CHARS}"
        )
    return text


@dataclass(frozen=True)
class Workspace:
    name: str
    storage: Storage

    @property
    def path(self) -> Path | None:
        """Local directory of the workspace, or ``None`` for non-local storage."""
        root = getattr(self.storage, "root", None)
        return Path(root) if root is not None else None

    def indexes(self) -> list[str]:
        """Names of the visible top-level directories (``.``/``_`` prefixed are skipped)."""
        return [n for n in _subdirs(self.storage) if not n.startswith((".", "_"))]

    def create_index(self, name: str, description: str | None = None) -> Storage:
        _validate_name(name, "index")
        _clean_description(description)  # validate before anything is created
        self._read_meta()
        if self.storage.exists(name):
            raise FileExistsError(f"Index {name!r} already exists in workspace {self.name!r}")
        self.storage.mkdir(name)
        if description is not None:
            self.set_description(name, description)
        return self.storage.child(name)

    def bundle_storage(self, name: str) -> Storage:
        _validate_name(name, "index")
        if not self.storage.is_dir(name):
            raise FileNotFoundError(f"No index {name!r} in workspace {self.name!r}")
        return self.storage.child(name)

    def index_root(self, name: str) -> Path:
        storage = self.bundle_storage(name)
        root = getattr(storage, "root", None)
        if root is None:
            raise ValueError(f"workspace {self.name!r} is not on local storage")
        return Path(root)

    def load_index(self, name: str) -> Bundle:
        return Bundle.load(self.bundle_storage(name))

    def meta_storage(self) -> Storage:
        return self.storage.child(METADATA_DIR)

    # -- bundle descriptions (``.okf/workspace.json``) -----------------------

    def _read_meta(self) -> dict:
        key = f"{METADATA_DIR}/{WORKSPACE_FILE}"
        try:
            text = self.storage.read_text(key)
        except FileNotFoundError:
            return {"version": _WORKSPACE_FILE_VERSION, "bundles": {}}
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ValueError(f"corrupt {key} in workspace {self.name!r}: {exc}") from exc
        if (
            not isinstance(data, dict)
            or data.get("version") != _WORKSPACE_FILE_VERSION
            or not isinstance(data.get("bundles"), dict)
        ):
            raise ValueError(
                f"unsupported or corrupt {key} in workspace {self.name!r}: "
                f"expected {{\"version\": {_WORKSPACE_FILE_VERSION}, \"bundles\": {{...}}}}"
            )
        return data

    def _entry(self, data: dict, name: str) -> str | None:
        entry = data["bundles"].get(name)
        description = entry.get("description") if isinstance(entry, dict) else None
        return description if isinstance(description, str) else None

    def description(self, name: str) -> str | None:
        _validate_name(name, "index")
        return self._entry(self._read_meta(), name)

    def set_description(self, name: str, text: str | None) -> str | None:
        """Set (or clear, with ``None``/blank) a bundle's description; returns it."""
        cleaned = _clean_description(text)
        with self.storage.lock():
            data = self._read_meta()
            self.bundle_storage(name)
            live = set(self.indexes())
            bundles = {k: v for k, v in data["bundles"].items() if k in live}
            bundles[name] = {"description": cleaned}
            data["bundles"] = bundles
            self.storage.write_text(
                f"{METADATA_DIR}/{WORKSPACE_FILE}",
                json.dumps(data, indent=2, sort_keys=True) + "\n",
            )
        return cleaned

    def bundles_info(self) -> list[dict]:
        """``[{"name", "description"}]`` for every index, sorted by name."""
        data = self._read_meta()
        return [{"name": n, "description": self._entry(data, n)} for n in self.indexes()]


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
        return self._workspace(name)

    def get(self, name: str) -> Workspace:
        if not self.exists(name):
            raise FileNotFoundError(f"No workspace {name!r}")
        return self._workspace(name)

    def list(self) -> list[Workspace]:
        return [self._workspace(n) for n in _subdirs(self.storage) if _NAME_RE.fullmatch(n)]
