"""Workspaces: named directories under ``~/.okf/workspaces`` holding indexes.

A *workspace* is a git-repo-shaped directory; an *index* is a collection of
concepts inside it, and is exactly one bundle (a visible top-level directory).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from okf_core.bundle import Bundle

OKF_HOME_ENV = "OKF_HOME"
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


class LocalStorage:
    """Local-filesystem backend; the single place the registry touches disk."""

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def mkdir(self, path: Path, *, parents: bool = False) -> None:
        path.mkdir(parents=parents, exist_ok=False)

    def list_dirs(self, path: Path) -> list[Path]:
        if not path.is_dir():
            return []
        return sorted(p for p in path.iterdir() if p.is_dir())


@dataclass(frozen=True)
class Workspace:
    name: str
    path: Path
    storage: LocalStorage = field(default_factory=LocalStorage, compare=False, repr=False)

    def indexes(self) -> list[str]:
        """Names of the visible top-level directories (``.``/``_`` prefixed are skipped)."""
        return [
            p.name
            for p in self.storage.list_dirs(self.path)
            if not p.name.startswith((".", "_"))
        ]

    def create_index(self, name: str) -> Path:
        path = self.path / _validate_name(name, "index")
        self.storage.mkdir(path)
        return path

    def index_root(self, name: str) -> Path:
        path = self.path / _validate_name(name, "index")
        if not self.storage.is_dir(path):
            raise FileNotFoundError(f"No index {name!r} in workspace {self.name!r}")
        return path

    def load_index(self, name: str) -> Bundle:
        return Bundle.load(self.index_root(name))


class WorkspaceRegistry:
    """The set of workspaces under ``<okf home>/workspaces``."""

    def __init__(
        self, root: Path | str | None = None, storage: LocalStorage | None = None
    ) -> None:
        self.root = Path(root) if root is not None else okf_home() / "workspaces"
        self.storage = storage or LocalStorage()

    def _workspace(self, name: str) -> Workspace:
        return Workspace(name, self.root / name, self.storage)

    def exists(self, name: str) -> bool:
        return self.storage.is_dir(self.root / _validate_name(name, "workspace"))

    def create(self, name: str) -> Workspace:
        _validate_name(name, "workspace")
        ws = self._workspace(name)
        if self.storage.exists(ws.path):
            raise FileExistsError(f"Workspace {name!r} already exists")
        if not self.storage.exists(self.root):
            self.storage.mkdir(self.root, parents=True)
        self.storage.mkdir(ws.path)
        return ws

    def get(self, name: str) -> Workspace:
        if not self.exists(name):
            raise FileNotFoundError(f"No workspace {name!r}")
        return self._workspace(name)

    def list(self) -> list[Workspace]:
        return [
            self._workspace(p.name)
            for p in self.storage.list_dirs(self.root)
            if _NAME_RE.fullmatch(p.name)
        ]
