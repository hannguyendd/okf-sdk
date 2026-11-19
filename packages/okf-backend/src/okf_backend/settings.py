"""Environment-driven settings shared by the OKF frontends."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from okf_backend.embeddings import EmbeddingConfig


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OKF_", env_file=".env", extra="ignore"
    )

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
