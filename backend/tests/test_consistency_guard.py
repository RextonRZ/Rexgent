import pytest
from unittest.mock import AsyncMock, MagicMock
from app.mcp_tools.consistency_guard import ConsistencyGuard


def make_guard(frame_score, diagnosis=None):
    guard = ConsistencyGuard.__new__(ConsistencyGuard)
    guard.embedder = MagicMock()
    guard.embedder.model = MagicMock()
    guard.embedder.model.embed = MagicMock(return_value=[0.5] * 512)
    guard.embedder.compare_vectors = MagicMock(return_value=frame_score)
    guard.qwen = MagicMock()
    guard.qwen.chat_vision_json = AsyncMock(return_value=diagnosis or {
        "reason": "lighting obscured the face", "suggested_change": "brighten key light"
    })
    guard._sample = MagicMock(return_value=[b"f1", b"f2", b"f3"])
    return guard


@pytest.mark.asyncio
async def test_pass_above_threshold():
    guard = make_guard(0.88)
    result = await guard.validate(
        clip_url="http://x/c.mp4", duration=5,
        expected_characters=[{"name": "Yuki", "face_vector": [0.5] * 512}],
        threshold=0.6,
    )
    assert result["overall_pass"] is True
    assert result["recommendation"] == "APPROVE"
    assert result["diagnosis"] is None


@pytest.mark.asyncio
async def test_fail_triggers_vlm_diagnosis():
    guard = make_guard(0.30, diagnosis={"reason": "wrong hairstyle", "suggested_change": "use short black hair"})
    result = await guard.validate(
        clip_url="http://x/c.mp4", duration=5,
        expected_characters=[{"name": "Yuki", "face_vector": [0.5] * 512}],
        threshold=0.6,
    )
    assert result["overall_pass"] is False
    assert result["recommendation"] == "RETRY_TARGETED"
    assert result["diagnosis"]["suggested_change"] == "use short black hair"
    assert "short black hair" in result["retry_instruction"]


@pytest.mark.asyncio
async def test_character_without_vector_skipped():
    guard = make_guard(0.9)
    result = await guard.validate(
        clip_url="http://x/c.mp4", duration=5,
        expected_characters=[{"name": "NoRef", "face_vector": None}],
        threshold=0.6,
    )
    assert result["character_results"][0]["detected"] is False
    # Unverifiable does not block overall pass.
    assert result["overall_pass"] is True


@pytest.mark.asyncio
async def test_diagnosis_fallback_on_bad_response():
    guard = make_guard(0.20, diagnosis=["not a dict"])
    result = await guard.validate(
        clip_url="http://x/c.mp4", duration=5,
        expected_characters=[{"name": "Yuki", "face_vector": [0.5] * 512}],
        threshold=0.6,
    )
    assert result["overall_pass"] is False
    assert result["diagnosis"]["reason"] == "unknown"
