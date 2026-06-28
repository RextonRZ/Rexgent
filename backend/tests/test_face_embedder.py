import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.face_embedder import FaceEmbedder


@pytest.mark.asyncio
async def test_extract_embedding_returns_structured_data():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.qwen = MagicMock()
    embedder.qwen.chat_vision_json = AsyncMock(return_value={
        "face_description": "sharp cheekbones, almond eyes, strong jaw",
        "distinctive_features": ["silver earring", "small scar on chin"],
        "embedding_keywords": ["sharp cheekbones", "almond eyes", "strong jaw", "short black hair"],
    })

    result = await embedder.extract_embedding("https://example.com/face.jpg")
    assert "face_description" in result
    assert len(result["embedding_keywords"]) > 0


@pytest.mark.asyncio
async def test_extract_embedding_handles_non_dict():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.qwen = MagicMock()
    embedder.qwen.chat_vision_json = AsyncMock(return_value=["bad"])

    result = await embedder.extract_embedding("https://example.com/face.jpg")
    assert result["embedding_keywords"] == []


@pytest.mark.asyncio
async def test_compare_faces_returns_score():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.qwen = MagicMock()
    embedder.qwen.chat_vision_json = AsyncMock(return_value={
        "similarity_score": 0.85,
        "matching_features": ["cheekbones", "hair style"],
        "missing_features": [],
    })

    score = await embedder.compare_faces(
        stored_embedding={"embedding_keywords": ["sharp cheekbones", "short black hair"]},
        frame_url="https://example.com/frame.jpg",
    )
    assert 0.0 <= score <= 1.0
    assert score == 0.85


@pytest.mark.asyncio
async def test_compare_faces_handles_bad_score():
    embedder = FaceEmbedder.__new__(FaceEmbedder)
    embedder.qwen = MagicMock()
    embedder.qwen.chat_vision_json = AsyncMock(return_value={"similarity_score": "not a number"})

    score = await embedder.compare_faces(
        stored_embedding={"embedding_keywords": ["x"]},
        frame_url="https://example.com/frame.jpg",
    )
    assert score == 0.5
