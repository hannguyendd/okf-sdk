"""Export a subtree of a workspace as a standalone bundle."""
from __future__ import annotations

from okf_core.links import map_absolute_links
from okf_core.storage import Storage, normalize_key


def export_subtree(storage: Storage, path: str, dest: Storage) -> int:
    """Copy every file under ``path/`` into ``dest``, keyed relative to ``path``.

    In ``.md`` files, absolute links into the subtree (``/path/x.md``) are
    rebased to ``/x.md``; links outside it are left unchanged. Returns the
    number of files copied. Raises ``FileNotFoundError`` if ``path`` is not a
    directory.
    """
    root = normalize_key(path)
    if not root or not storage.is_dir(root):
        raise FileNotFoundError(path)
    prefix = root + "/"

    def _rebase(target: str) -> str | None:
        return target[len(prefix):] if target.startswith(prefix) else None

    count = 0
    for key in storage.iter_files(root):
        text = storage.read_text(key)
        if key.endswith(".md"):
            text = map_absolute_links(text, _rebase)
        dest.write_text(key[len(prefix):], text)
        count += 1
    return count
