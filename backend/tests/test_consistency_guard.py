import pytest
from unittest.mock import AsyncMock, MagicMock
from app.mcp_tools.consistency_guard import ConsistencyGuard


def make_guard(score):
    guard = ConsistencyGuard.__new__(ConsistencyGuard)
    guard.face_embedder = MagicMock()
    guard.face_embedder.compare_faces = AsyncMock(return_value=score)
    return guard


@pytest.mark.asyncio
async def test_validate_passes_above_threshold():
    guard = make_guard(0.88)
    result = await guard.validate(
        frame_urls=["https://example.com/f1.jpg", "https://example.com/f2.jpg", "https://example.com/f3.jpg"],
        expected_characters=[{"name": "Yuki", "face_embedding": {"embedding_keywords": ["sharp cheekbones"]}, "face_keywords": ["sharp cheekbones"]}],
        threshold=0.75,
    )
    assert result["overall_pass"] is True
    assert result["recommendation"] == "APPROVE"


@pytest.mark.asyncio
async def test_validate_retry_stronger_face():
    guard = make_guard(0.68)
    result = await guard.validate(
        frame_urls=["https://example.com/f1.jpg"],
        expected_characters=[{"name": "Yuki", "face_embedding": {}, "face_keywords": []}],
        threshold=0.75,
    )
    assert result["overall_pass"] is False
    assert result["recommendation"] == "RETRY_STRONGER_FACE"


@pytest.mark.asyncio
async def test_validate_retry_same_prompt():
    guard = make_guard(0.50)
    result = await guard.validate(
        frame_urls=["https://example.com/f1.jpg"],
        expected_characters=[{"name": "Yuki", "face_embedding": {}, "face_keywords": []}],
        threshold=0.75,
    )
    assert result["recommendation"] == "RETRY_SAME_PROMPT"


@pytest.mark.asyncio
async def test_validate_manual_review():
    guard = make_guard(0.30)
    result = await guard.validate(
        frame_urls=["https://example.com/f1.jpg"],
        expected_characters=[{"name": "Yuki", "face_embedding": {}, "face_keywords": []}],
        threshold=0.75,
    )
    assert result["recommendation"] == "MANUAL_REVIEW"


@pytest.mark.asyncio
async def test_validate_no_characters_passes():
    guard = make_guard(0.0)
    result = await guard.validate(
        frame_urls=["https://example.com/f1.jpg"],
        expected_characters=[],
        threshold=0.75,
    )
    assert result["overall_pass"] is True
    assert result["recommendation"] == "APPROVE"
