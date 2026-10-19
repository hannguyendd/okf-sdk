import json
import math

import httpx
import pytest

from okf_mcp.embeddings import EmbeddingConfig, EmbeddingError, embed_texts


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok(vectors):
    """Response whose ``data`` lists ``vectors`` with their positional index."""
    return httpx.Response(
        200,
        json={"data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)]},
    )


def _cfg(**kw):
    return EmbeddingConfig(url="http://h/v1", model="m", **kw)


def test_posts_to_embeddings_path_with_model_and_input():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return _ok([[1.0, 0.0], [0.0, 1.0]])

    embed_texts(["a", "b"], _cfg(), client=_client(handler))

    assert seen["url"] == "http://h/v1/embeddings"
    assert seen["body"] == {"model": "m", "input": ["a", "b"]}
    assert seen["auth"] is None


def test_sends_bearer_token_when_api_key_set():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return _ok([[1.0, 0.0]])

    embed_texts(["a"], _cfg(api_key="k"), client=_client(handler))

    assert seen["auth"] == "Bearer k"


def test_vectors_are_l2_normalized_and_ordered_by_index():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 5.0]},
                    {"index": 0, "embedding": [3.0, 4.0]},
                ]
            },
        )

    vectors = embed_texts(["a", "b"], _cfg(), client=_client(handler))

    assert vectors[0] == pytest.approx([0.6, 0.8])
    assert vectors[1] == pytest.approx([0.0, 1.0])
    for v in vectors:
        assert math.sqrt(sum(x * x for x in v)) == pytest.approx(1.0)


def test_batches_by_batch_size():
    calls = []

    def handler(request):
        batch = json.loads(request.content)["input"]
        calls.append(batch)
        return _ok([[1.0, 0.0]] * len(batch))

    vectors = embed_texts(
        ["a", "b", "c", "d", "e"], _cfg(batch_size=2), client=_client(handler)
    )

    assert calls == [["a", "b"], ["c", "d"], ["e"]]
    assert len(vectors) == 5


def test_raises_on_count_mismatch():
    def handler(request):
        return _ok([[1.0, 0.0]])

    with pytest.raises(EmbeddingError):
        embed_texts(["a", "b"], _cfg(), client=_client(handler))


def test_raises_on_http_error_status():
    def handler(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(EmbeddingError):
        embed_texts(["a"], _cfg(), client=_client(handler))


def test_raises_on_connect_error():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(EmbeddingError):
        embed_texts(["a"], _cfg(), client=_client(handler))


def test_raises_on_mixed_dimensions():
    def handler(request):
        return _ok([[1.0, 0.0], [1.0, 0.0, 0.0]])

    with pytest.raises(EmbeddingError):
        embed_texts(["a", "b"], _cfg(), client=_client(handler))
