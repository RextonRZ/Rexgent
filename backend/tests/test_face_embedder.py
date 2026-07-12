import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.face_embedder import FaceEmbedder


def _mock_qwen(description):
    client = MagicMock()
    client.chat_vision_json = AsyncMock(return_value=description)
    return patch("app.services.qwen_client.QwenClient", return_value=client)


@pytest.mark.asyncio
async def test_extract_returns_vector_and_description():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.model = MagicMock()
    embedder.model.embed = MagicMock(return_value=[0.1] * 512)

    with _mock_qwen({
        "face_description": "sharp cheekbones, almond eyes",
        "embedding_keywords": ["sharp cheekbones", "short black hair"],
    }):
        result = await embedder.extract(image_bytes=b"fakejpg", image_url="https://x/y.jpg")
    assert len(result["vector"]) == 512
    assert "sharp cheekbones" in result["description"]["face_description"]


@pytest.mark.asyncio
async def test_extract_no_face_returns_none_vector():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.model = MagicMock()
    embedder.model.embed = MagicMock(return_value=None)

    with _mock_qwen({"face_description": "no face"}):
        result = await embedder.extract(image_bytes=b"x", image_url="https://x/y.jpg")
    assert result["vector"] is None


@pytest.mark.asyncio
async def test_vector_survives_a_qwen_failure():
    """The identity lock must not depend on the Qwen key/description: if the
    vision call raises (no key, flaky VL), the ArcFace vector still comes back
    and the face stays locked. This is the deployed bug that left faces
    unmatched — the QwenClient construction used to abort the whole embed."""
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.model = MagicMock()
    embedder.model.embed = MagicMock(return_value=[0.2] * 512)

    with patch("app.services.qwen_client.QwenClient", side_effect=RuntimeError("no key")):
        result = await embedder.extract(image_bytes=b"x", image_url="https://x/y.jpg")
    assert len(result["vector"]) == 512  # the face is still locked
    assert result["description"] == {"face_description": "", "embedding_keywords": []}


@pytest.mark.asyncio
async def test_extract_handles_non_dict_description():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.model = MagicMock()
    embedder.model.embed = MagicMock(return_value=[0.2] * 512)

    with _mock_qwen(["bad"]):
        result = await embedder.extract(image_bytes=b"x", image_url="https://x/y.jpg")
    assert result["description"]["embedding_keywords"] == []


def test_compare_vectors_uses_cosine():
    score = FaceEmbedder.compare_vectors([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert abs(score - 1.0) < 1e-6
