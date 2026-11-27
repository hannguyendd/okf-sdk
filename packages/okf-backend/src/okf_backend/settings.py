"""Environment-driven settings shared by the OKF frontends."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from okf_core import okf_home
from pydantic_settings import BaseSettings, SettingsConfigDict

from okf_backend.embeddings import EmbeddingConfig


def env_files() -> tuple[Path, ...]:
    """Dotenv files to read, lowest priority first: ``<OKF_HOME>/.env``, ``./.env``.

    The home file lets a server started from any directory (e.g. an ``okf-mcp``
    stdio server that Claude Code spawns in another project) find its settings.
    Real environment variables beat both; missing files are skipped.
    """
    return (okf_home() / ".env", Path(".env"))


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OKF_", extra="ignore"
    )

    def __init__(self, **values: Any) -> None:
        # Resolved per instance so a changed OKF_HOME or cwd is honoured;
        # an explicit ``_env_file`` (including ``None``) still wins.
        values.setdefault("_env_file", env_files())
        super().__init__(**values)

    # Semantic search. Leave unset to keep it disabled. ``embedding_url`` is an
    # OpenAI-compatible base URL including any ``/v1`` prefix. Vectors live in
    # ``<workspace>/.okf/vectors.db``.
    embedding_url: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_max_chars: int = 6000

    def embedding_config(self) -> EmbeddingConfig | None:
        """The embedding client config, or ``None`` unless url and model are set."""
        if self.embedding_url and self.embedding_model:
            return EmbeddingConfig(
                url=self.embedding_url,
                model=self.embedding_model,
                api_key=self.embedding_api_key,
            )
        return None
