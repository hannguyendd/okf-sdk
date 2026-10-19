"""sqlite-vec store holding one embedding per ``_index.md`` file of a bundle."""

from __future__ import annotations

import hashlib
import posixpath
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

from okf_core import INDEX_FILENAME, LocalStorage, OKFDocument, Storage

Embedder = Callable[[list[str]], list[list[float]]]

_EXCERPT_CHARS = 200
_BUSY_TIMEOUT_MS = 30_000


class VectorStoreError(RuntimeError):
    """The vector store could not be opened, synced, or queried."""


def default_db_path(storage: Storage) -> Path:
    """Sibling ``<bundle_root>.vectors.db`` -- outside the bundle, never inside it."""
    if isinstance(storage, LocalStorage):
        return Path(str(storage.root) + ".vectors.db")
    raise VectorStoreError(
        f"no default vector database location for storage {storage.location!r}; "
        "set OKF_VECTOR_DB to a local file path"
    )


def _excerpt(text: str) -> str:
    try:
        description = OKFDocument.parse(text).frontmatter.get("description")
    except ValueError:
        description = None
    if isinstance(description, str) and description.strip():
        return description.strip()
    return text[:_EXCERPT_CHARS]


class VectorStore:
    def __init__(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._lock = threading.Lock()
        try:
            import sqlite_vec

            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
        except (ImportError, AttributeError, sqlite3.Error) as exc:
            self._conn.close()
            raise VectorStoreError(
                "cannot load the sqlite-vec extension: this Python's sqlite3 module "
                "must allow loadable extensions (uv-managed Python does) and the "
                f"'sqlite-vec' package must be installed ({exc})"
            ) from exc
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        self._conn.executescript(
            "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);"
            "CREATE TABLE IF NOT EXISTS vectors("
            " root TEXT NOT NULL, key TEXT NOT NULL, hash TEXT NOT NULL,"
            " embedding BLOB NOT NULL, excerpt TEXT NOT NULL,"
            " PRIMARY KEY(root, key));"
        )

    def close(self) -> None:
        self._conn.close()

    def _meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, value))

    def sync(
        self, storage: Storage, embed: Embedder, *, model: str, max_chars: int
    ) -> None:
        """Make the store match the bundle's ``_index.md`` files.

        Embeds only files whose (truncated) text changed, prunes rows for files that
        no longer exist, and rebuilds everything when ``model`` changed. One
        transaction: on any error nothing is written.
        """
        import sqlite_vec

        root = storage.location
        keys = sorted(
            k
            for k in storage.iter_files(suffix=INDEX_FILENAME)
            if posixpath.basename(k) == INDEX_FILENAME
        )
        texts = {k: storage.read_text(k)[:max_chars] for k in keys}
        hashes = {k: hashlib.sha256(t.encode("utf-8")).hexdigest() for k, t in texts.items()}

        with self._lock:
            conn = self._conn
            conn.execute("BEGIN IMMEDIATE")
            try:
                stored_model = self._meta("model")
                stored_dim = self._meta("dim")
                if stored_model is not None and stored_model != model:
                    conn.execute("DELETE FROM vectors")
                    conn.execute("DELETE FROM meta")
                    stored_dim = None
                existing = dict(
                    conn.execute("SELECT key, hash FROM vectors WHERE root=?", (root,))
                )
                for gone in set(existing) - set(keys):
                    conn.execute("DELETE FROM vectors WHERE root=? AND key=?", (root, gone))
                changed = [k for k in keys if existing.get(k) != hashes[k]]
                if changed:
                    vectors = embed([texts[k] for k in changed])
                    dims = {len(v) for v in vectors}
                    if len(vectors) != len(changed) or len(dims) != 1:
                        raise VectorStoreError(
                            "embedder returned a different number of vectors than "
                            "inputs, or vectors of differing dimensions"
                        )
                    dim = dims.pop()
                    if stored_dim is not None and int(stored_dim) != dim:
                        raise VectorStoreError(
                            f"embedder returned dimension {dim} but the store holds "
                            f"{stored_dim} for model {model!r}"
                        )
                    for k, v in zip(changed, vectors):
                        conn.execute(
                            "INSERT OR REPLACE INTO vectors(root, key, hash, embedding, excerpt)"
                            " VALUES(?, ?, ?, ?, ?)",
                            (root, k, hashes[k], sqlite_vec.serialize_float32(v), _excerpt(texts[k])),
                        )
                    self._set_meta("dim", str(dim))
                self._set_meta("model", model)
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise

    def query(
        self, storage: Storage, vector: list[float], top_k: int, dir: str = ""
    ) -> list[dict]:
        """Closest ``_index.md`` files to ``vector`` (cosine), best first."""
        import sqlite_vec

        prefix = f"{dir}/" if dir else ""
        try:
            rows = self._conn.execute(
                "SELECT key, excerpt, 1 - vec_distance_cosine(embedding, ?) AS score"
                " FROM vectors WHERE root=? AND substr(key, 1, ?) = ?"
                " ORDER BY score DESC, key ASC LIMIT ?",
                (sqlite_vec.serialize_float32(vector), storage.location, len(prefix), prefix, top_k),
            ).fetchall()
        except sqlite3.Error as exc:
            raise VectorStoreError(f"vector query failed: {exc}") from exc
        return [
            {"dir": posixpath.dirname(key), "path": key, "score": float(score), "excerpt": excerpt}
            for key, excerpt, score in rows
        ]
