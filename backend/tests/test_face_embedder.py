import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.face_embedder import FaceEmbedder


@pytest.mark.asyncio
async def test_extract_returns_vector_and_description():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.qwen = MagicMock()
    embedder.qwen.chat_vision_json = AsyncMock(return_value={
        "face_description": "sharp cheekbones, almond eyes",
        "embedding_keywords": ["sharp cheekbones", "short black hair"],
    })
    embedder.model = MagicMock()
    embedder.model.embed = MagicMock(return_value=[0.1] * 512)

    result = await embedder.extract(image_bytes=b"fakejpg", image_url="https://x/y.jpg")
    assert len(result["vector"]) == 512
    assert "sharp cheekbones" in result["description"]["face_description"]


@pytest.mark.asyncio
async def test_extract_no_face_returns_none_vector():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.qwen = MagicMock()
    embedder.qwen.chat_vision_json = AsyncMock(return_value={"face_description": "no face"})
    embedder.model = MagicMock()
    embedder.model.embed = MagicMock(return_value=None)

    result = await embedder.extract(image_bytes=b"x", image_url="https://x/y.jpg")
    assert result["vector"] is None


@pytest.mark.asyncio
async def test_extract_handles_non_dict_description():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.qwen = MagicMock()
    embedder.qwen.chat_vision_json = AsyncMock(return_value=["bad"])
    embedder.model = MagicMock()
    embedder.model.embed = MagicMock(return_value=[0.2] * 512)

    result = await embedder.extract(image_bytes=b"x", image_url="https://x/y.jpg")
    assert result["description"]["embedding_keywords"] == []


def test_compare_vectors_uses_cosine():
    score = FaceEmbedder.compare_vectors([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert abs(score - 1.0) < 1e-6
