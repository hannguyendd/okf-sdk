"""sqlite-vec store for a workspace: one embedding per ``_index.md`` file of each
bundle, plus one per bundle description (the reserved key ``""``)."""

from __future__ import annotations

import hashlib
import posixpath
import sqlite3
from collections.abc import Callable
from pathlib import Path

from okf_core import INDEX_FILENAME, METADATA_DIR, OKFDocument, Storage, Workspace

Embedder = Callable[[list[str]], list[list[float]]]

_EXCERPT_CHARS = 200
_DB_FILENAME = "vectors.db"
_DESCRIPTION_KEY = ""  # real keys always end in ``_index.md``
_BUSY_TIMEOUT_MS = 30_000


class VectorStoreError(RuntimeError):
    """The vector store could not be opened, synced, or queried."""


def workspace_db_path(workspace: Workspace) -> Path:
    """``<workspace>/.okf/vectors.db`` -- inside the workspace, outside every bundle."""
    if workspace.path is None:
        raise VectorStoreError(
            f"workspace {workspace.name!r} is not on local storage; "
            "semantic search needs a local vector database"
        )
    return workspace.path / METADATA_DIR / _DB_FILENAME


def _excerpt(text: str) -> str:
    try:
        description = OKFDocument.parse(text).frontmatter.get("description")
    except ValueError:
        description = None
    if isinstance(description, str) and description.strip():
        return description.strip()
    return text[:_EXCERPT_CHARS]


class VectorStore:
    def __init__(self, path: Path | str, *, busy_timeout_ms: int = _BUSY_TIMEOUT_MS) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
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
        self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
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
        self,
        storage: Storage,
        embed: Embedder,
        *,
        bundle: str,
        description: str | None,
        model: str,
        max_chars: int,
    ) -> None:
        """Make the store's rows for ``bundle`` match its ``_index.md`` files and
        its description (``None`` removes the description row).

        Embeds only files whose (truncated) text changed, prunes rows for files that
        no longer exist, and rebuilds everything when the model name or the vector
        dimension changed. Embedding happens *outside* the write transaction, so a
        slow embedding server never blocks other searches, and a sync that finds
        nothing to do takes no write lock. The write is one transaction: on any
        error nothing is stored.
        """
        import sqlite_vec

        root = bundle
        keys = sorted(
            k
            for k in storage.iter_files(suffix=INDEX_FILENAME)
            if posixpath.basename(k) == INDEX_FILENAME
        )
        texts = {k: storage.read_text(k)[:max_chars] for k in keys}
        if description:
            keys.insert(0, _DESCRIPTION_KEY)
            texts[_DESCRIPTION_KEY] = description[:max_chars]
        hashes = {k: hashlib.sha256(t.encode("utf-8")).hexdigest() for k, t in texts.items()}

        try:
            stored_model, stored_dim = self._meta("model"), self._meta("dim")
            rebuild = stored_model is not None and stored_model != model
            existing = (
                {}
                if rebuild
                else dict(self._conn.execute("SELECT key, hash FROM vectors WHERE root=?", (root,)))
            )
            changed = [k for k in keys if existing.get(k) != hashes[k]]
            gone = set(existing) - set(keys)
            if not changed and not gone and not rebuild and stored_model == model:
                return

            vectors = self._embed(embed, [texts[k] for k in changed])
            if vectors and stored_dim is not None and not rebuild and len(vectors[0]) != int(stored_dim):
                # Same model name, different dimension (e.g. the server swapped the
                # loaded model): the old vectors are incomparable, so start over.
                rebuild = True
                rest = [k for k in keys if k not in set(changed)]
                more = self._embed(embed, [texts[k] for k in rest])
                if more and len(more[0]) != len(vectors[0]):
                    raise VectorStoreError("embedder returned vectors of differing dimensions")
                changed, vectors = changed + rest, vectors + more

            self._conn.execute("BEGIN IMMEDIATE")
            try:
                if rebuild:
                    self._conn.execute("DELETE FROM vectors")
                    self._conn.execute("DELETE FROM meta")
                for k in gone:
                    self._conn.execute("DELETE FROM vectors WHERE root=? AND key=?", (root, k))
                for k, v in zip(changed, vectors):
                    self._conn.execute(
                        "INSERT OR REPLACE INTO vectors(root, key, hash, embedding, excerpt)"
                        " VALUES(?, ?, ?, ?, ?)",
                        (
                            root,
                            k,
                            hashes[k],
                            sqlite_vec.serialize_float32(v),
                            texts[k] if k == _DESCRIPTION_KEY else _excerpt(texts[k]),
                        ),
                    )
                if vectors:
                    self._set_meta("dim", str(len(vectors[0])))
                self._set_meta("model", model)
                self._conn.execute("COMMIT")
            except BaseException:
                if self._conn.in_transaction:
                    self._conn.execute("ROLLBACK")
                raise
        except sqlite3.OperationalError as exc:
            raise VectorStoreError(f"vector database error (is it locked by another process?): {exc}") from exc

    @staticmethod
    def _embed(embed: Embedder, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = embed(texts)
        if len(vectors) != len(texts) or len({len(v) for v in vectors}) != 1:
            raise VectorStoreError(
                "embedder returned a different number of vectors than inputs, "
                "or vectors of differing dimensions"
            )
        return vectors

    def prune_bundles(self, keep: set[str]) -> None:
        """Delete every row of a bundle not in ``keep`` (e.g. deleted from disk)."""
        try:
            stored = {r[0] for r in self._conn.execute("SELECT DISTINCT root FROM vectors")}
            gone = stored - keep
            if not gone:
                return
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.executemany("DELETE FROM vectors WHERE root=?", [(g,) for g in gone])
                self._conn.execute("COMMIT")
            except BaseException:
                if self._conn.in_transaction:
                    self._conn.execute("ROLLBACK")
                raise
        except sqlite3.OperationalError as exc:
            raise VectorStoreError(f"vector database error (is it locked by another process?): {exc}") from exc

    def query(
        self, vector: list[float], top_k: int, *, bundles: list[str], dir: str = ""
    ) -> list[dict]:
        """Closest rows of ``bundles`` to ``vector`` (cosine), ranked together, best
        first. A non-empty ``dir`` keeps only indexes at or below it."""
        import sqlite_vec

        if not bundles:
            return []
        prefix = f"{dir}/" if dir else ""
        marks = ",".join("?" * len(bundles))
        try:
            rows = self._conn.execute(
                "SELECT root, key, excerpt, 1 - vec_distance_cosine(embedding, ?) AS score"
                f" FROM vectors WHERE root IN ({marks}) AND substr(key, 1, ?) = ?"
                + (" AND key != ''" if dir else "")
                + " ORDER BY score DESC, root ASC, key ASC LIMIT ?",
                (sqlite_vec.serialize_float32(vector), *bundles, len(prefix), prefix, top_k),
            ).fetchall()
        except sqlite3.Error as exc:
            raise VectorStoreError(f"vector query failed: {exc}") from exc
        return [
            {
                "bundle": root,
                "kind": "bundle" if key == _DESCRIPTION_KEY else "index",
                "dir": posixpath.dirname(key),
                "path": None if key == _DESCRIPTION_KEY else key,
                "score": float(score),
                "excerpt": excerpt,
            }
            for root, key, excerpt, score in rows
        ]
