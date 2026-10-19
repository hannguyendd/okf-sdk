"""Storage interface for OKF bundles, with local-filesystem and in-memory backends.

Everything in ``okf_core`` (and ``okf_mcp``) reads and writes bundle files
through :class:`Storage`, so the backing infrastructure can be swapped. Keys are
bundle-relative POSIX strings (``"tables/orders.md"``); ``""`` is the bundle
root. See ``docs/superpowers/specs/2026-10-19-okf-storage-interface-design.md``.

Backends are chosen with :func:`open_storage` from a location string: a plain
path or ``file://`` URI is local; any other scheme is looked up in the registry
(:func:`register_backend`, then the ``okf_core.storage`` entry-point group), so
optional backends can live in separate packages and keep ``okf_core``'s only
runtime dependency PyYAML.
"""

from __future__ import annotations

import os
import posixpath
import re
import tempfile
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import urlparse
from urllib.request import url2pathname

try:  # POSIX only; Windows degrades to the in-process lock.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

LOCK_FILENAME = ".okf.lock"
ENTRY_POINT_GROUP = "okf_core.storage"


def normalize_key(key: str) -> str:
    """Validate a storage key and return it without a trailing slash.

    Rejects absolute keys, backslashes, and empty / ``.`` / ``..`` segments so a
    backend can never be handed a key that escapes its root.
    """
    if key == "":
        return ""
    key = key.removesuffix("/")
    if key.startswith("/") or "\\" in key:
        raise ValueError(f"invalid storage key: {key!r}")
    for seg in key.split("/"):
        if seg in ("", ".", ".."):
            raise ValueError(f"invalid storage key: {key!r}")
    return key


def _join(prefix: str, key: str) -> str:
    return f"{prefix}/{key}" if prefix and key else prefix or key


@dataclass(frozen=True)
class Entry:
    """A direct child of a directory."""

    name: str
    is_dir: bool


class Storage(ABC):
    """Where a bundle's files live. Keys are bundle-relative POSIX strings.

    A minimal backend implements the six abstract methods; the rest have working
    defaults built on them.
    """

    # -- required ----------------------------------------------------------

    @abstractmethod
    def read_text(self, key: str) -> str:
        """Return the file's text. ``FileNotFoundError`` if absent."""

    @abstractmethod
    def write_text(self, key: str, text: str) -> None:
        """Write the file, creating parents. Atomic per key."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a file (not a directory). ``FileNotFoundError`` if absent."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """True for an existing file or directory."""

    @abstractmethod
    def is_dir(self, key: str) -> bool:
        """True for an existing directory (``""`` = the bundle root)."""

    @abstractmethod
    def list_dir(self, key: str) -> list[Entry]:
        """Sorted direct children. ``FileNotFoundError`` if not a directory."""

    # -- defaults ----------------------------------------------------------

    @property
    def location(self) -> str:
        """Human-readable origin, for error messages."""
        return type(self).__name__

    def mkdir(self, key: str) -> None:
        """Create a directory (and parents). No-op for flat/object stores."""

    def move(self, src: str, dst: str) -> None:
        """Move a file. ``FileNotFoundError`` / ``FileExistsError``; no overwrite."""
        text = self.read_text(src)
        if self.exists(dst):
            raise FileExistsError(dst)
        self.write_text(dst, text)
        self.delete(src)

    def iter_files(self, prefix: str = "", suffix: str = "") -> Iterator[str]:
        """Yield file keys under ``prefix`` recursively, depth-first by name."""
        prefix = normalize_key(prefix)
        try:
            entries = self.list_dir(prefix)
        except FileNotFoundError:
            return
        for e in entries:
            key = _join(prefix, e.name)
            if e.is_dir:
                yield from self.iter_files(key, suffix)
            elif e.name.endswith(suffix):
                yield key

    def lock(self):
        """Exclusive, reentrant context manager for a multi-file write operation."""
        return _thread_lock(self)

    def child(self, prefix: str) -> "Storage":
        """A view of this storage rooted at ``prefix``."""
        return _Scoped(self, normalize_key(prefix))


@contextmanager
def _thread_lock(storage: Storage):
    lk = storage.__dict__.setdefault("_okf_rlock", threading.RLock())
    with lk:
        yield


class _Scoped(Storage):
    """Generic ``child`` view: prefixes every key and shares the parent's lock."""

    def __init__(self, parent: Storage, prefix: str) -> None:
        self._parent, self._prefix = parent, prefix

    def _k(self, key: str) -> str:
        return _join(self._prefix, normalize_key(key))

    @property
    def location(self) -> str:
        return f"{self._parent.location}/{self._prefix}"

    def read_text(self, key):
        return self._parent.read_text(self._k(key))

    def write_text(self, key, text):
        self._parent.write_text(self._k(key), text)

    def delete(self, key):
        self._parent.delete(self._k(key))

    def exists(self, key):
        return self._parent.exists(self._k(key))

    def is_dir(self, key):
        return self._parent.is_dir(self._k(key))

    def list_dir(self, key):
        return self._parent.list_dir(self._k(key))

    def mkdir(self, key):
        self._parent.mkdir(self._k(key))

    def move(self, src, dst):
        self._parent.move(self._k(src), self._k(dst))

    def lock(self):
        return self._parent.lock()

    def child(self, prefix):
        return _Scoped(self._parent, self._k(prefix))


class MemoryStorage(Storage):
    """In-memory backend: a fast test double and a reference implementation."""

    def __init__(self) -> None:
        self._files: dict[str, str] = {}
        self._dirs: set[str] = set()

    @property
    def location(self) -> str:
        return "memory"

    def _mark_parents(self, key: str) -> None:
        parts = key.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            self._dirs.add("/".join(parts[:i]))

    def read_text(self, key):
        key = normalize_key(key)
        try:
            return self._files[key]
        except KeyError:
            raise FileNotFoundError(key) from None

    def write_text(self, key, text):
        key = normalize_key(key)
        if not key or key in self._dirs:
            raise IsADirectoryError(key)
        self._mark_parents(key)
        self._files[key] = text

    def delete(self, key):
        key = normalize_key(key)
        if key not in self._files:
            raise FileNotFoundError(key)
        del self._files[key]

    def exists(self, key):
        key = normalize_key(key)
        return key in self._files or self.is_dir(key)

    def is_dir(self, key):
        key = normalize_key(key)
        return key == "" or key in self._dirs

    def mkdir(self, key):
        key = normalize_key(key)
        if key:
            self._mark_parents(key + "/x")

    def list_dir(self, key):
        key = normalize_key(key)
        if not self.is_dir(key):
            raise FileNotFoundError(key)
        base = key + "/" if key else ""
        out: dict[str, bool] = {}
        for k in self._files:
            if k.startswith(base):
                head, sep, _ = k[len(base) :].partition("/")
                out[head] = out.get(head, False) or bool(sep)
        for d in self._dirs:
            if d.startswith(base) and d != key:
                out[d[len(base) :].partition("/")[0]] = True
        return [Entry(n, out[n]) for n in sorted(out)]


class _RootLock:
    """Per-root lock state shared by every ``LocalStorage`` on the same root."""

    def __init__(self) -> None:
        self.rlock = threading.RLock()
        self.depth = 0
        self.fd: int | None = None


_ROOT_LOCKS: dict[str, _RootLock] = {}
_ROOT_LOCKS_GUARD = threading.Lock()


def _root_lock(root: Path) -> _RootLock:
    with _ROOT_LOCKS_GUARD:
        return _ROOT_LOCKS.setdefault(str(root), _RootLock())


class LocalStorage(Storage):
    """Local-filesystem backend rooted at a directory (the default backend)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self._rl = _root_lock(self.root)

    @property
    def location(self) -> str:
        return str(self.root)

    def _p(self, key: str) -> Path:
        key = normalize_key(key)
        return self.root.joinpath(*key.split("/")) if key else self.root

    def read_text(self, key):
        return self._p(key).read_bytes().decode("utf-8")

    def write_text(self, key, text):
        path = self._p(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".okf-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(text.encode("utf-8"))
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def delete(self, key):
        path = self._p(key)
        if path.is_dir():
            raise IsADirectoryError(key)
        path.unlink()

    def exists(self, key):
        return self._p(key).exists()

    def is_dir(self, key):
        return self._p(key).is_dir()

    def list_dir(self, key):
        path = self._p(key)
        if not path.is_dir():
            raise FileNotFoundError(key)
        return [Entry(c.name, c.is_dir()) for c in sorted(path.iterdir())]

    def mkdir(self, key):
        self._p(key).mkdir(parents=True, exist_ok=True)

    def move(self, src, dst):
        s, d = self._p(src), self._p(dst)
        if not s.is_file():
            raise FileNotFoundError(src)
        if d.exists():
            raise FileExistsError(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        os.rename(s, d)

    def child(self, prefix):
        return LocalStorage(self._p(prefix))

    @contextmanager
    def lock(self):
        rl = self._rl
        with rl.rlock:
            rl.depth += 1
            try:
                if rl.depth == 1 and fcntl is not None and self.root.is_dir():
                    rl.fd = os.open(
                        self.root / LOCK_FILENAME, os.O_RDWR | os.O_CREAT, 0o644
                    )
                    fcntl.flock(rl.fd, fcntl.LOCK_EX)
                yield
            finally:
                if rl.depth == 1 and rl.fd is not None:
                    try:
                        fcntl.flock(rl.fd, fcntl.LOCK_UN)
                    finally:
                        os.close(rl.fd)
                        rl.fd = None
                rl.depth -= 1


# ---- selection ------------------------------------------------------------

BackendFactory = Callable[[str], Storage]
_BACKENDS: dict[str, BackendFactory] = {}
_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*)://")


def register_backend(scheme: str, factory: BackendFactory) -> None:
    """Register ``factory(location) -> Storage`` for ``scheme://`` locations."""
    _BACKENDS[scheme.lower()] = factory


def _entry_points():
    return entry_points(group=ENTRY_POINT_GROUP)


def is_uri(location: str | Path) -> bool:
    """True when ``location`` is a ``scheme://`` URI (a drive letter is not)."""
    return isinstance(location, str) and _SCHEME_RE.match(location) is not None


def open_storage(location: "Storage | Path | str") -> Storage:
    """Resolve a location to a :class:`Storage`.

    A ``Storage`` is returned as is; a ``Path``, plain string, or ``file://`` URI
    opens a :class:`LocalStorage`; any other ``scheme://`` goes to the backend
    registered for that scheme (registry first, then entry points).
    """
    if isinstance(location, Storage):
        return location
    if isinstance(location, Path) or not is_uri(location):
        return LocalStorage(location)
    scheme = _SCHEME_RE.match(location).group(1).lower()  # type: ignore[union-attr]
    if scheme == "file":
        return LocalStorage(url2pathname(urlparse(location).path))
    factory = _BACKENDS.get(scheme)
    if factory is None:
        for ep in _entry_points():
            if ep.name.lower() == scheme:
                factory = ep.load()
                break
    if factory is None:
        known = sorted({"file", *_BACKENDS})
        raise ValueError(
            f"unknown storage scheme {scheme!r} in {location!r} "
            f"(registered: {', '.join(known)}); is the backend package installed?"
        )
    return factory(location)
