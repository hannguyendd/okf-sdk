"""Client for an OpenAI-compatible ``/embeddings`` endpoint (e.g. a local server)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import httpx


class EmbeddingError(RuntimeError):
    """The embedding server was unreachable or returned an unusable response."""


@dataclass(frozen=True)
class EmbeddingConfig:
    url: str  # base URL incl. any version prefix; ``/embeddings`` is appended
    model: str
    api_key: str | None = None
    timeout: float = 30.0
    batch_size: int = 32


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else list(vector)


def _embed_batch(
    batch: list[str], config: EmbeddingConfig, client: httpx.Client
) -> list[list[float]]:
    endpoint = f"{config.url.rstrip('/')}/embeddings"
    headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
    try:
        response = client.post(
            endpoint,
            json={"model": config.model, "input": batch},
            headers=headers,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda d: d["index"])
        vectors = [list(map(float, d["embedding"])) for d in data]
    except httpx.HTTPError as exc:
        raise EmbeddingError(f"embedding request to {endpoint} failed: {exc}") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise EmbeddingError(f"unexpected response from {endpoint}: {exc}") from exc
    if len(vectors) != len(batch):
        raise EmbeddingError(
            f"{endpoint} returned {len(vectors)} vectors for {len(batch)} inputs"
        )
    return vectors


def embed_texts(
    texts: list[str],
    config: EmbeddingConfig,
    *,
    client: httpx.Client | None = None,
) -> list[list[float]]:
    """Embed ``texts`` in batches; returns L2-normalized vectors in input order."""
    owned = client is None
    client = client or httpx.Client(timeout=config.timeout)
    try:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), config.batch_size):
            vectors.extend(
                _embed_batch(texts[start : start + config.batch_size], config, client)
            )
    finally:
        if owned:
            client.close()
    if len({len(v) for v in vectors}) > 1:
        raise EmbeddingError("embedding server returned vectors of differing dimensions")
    return [_normalize(v) for v in vectors]
