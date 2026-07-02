import pytest
from unittest.mock import AsyncMock, MagicMock
from app.mcp_tools.continuity_agent import ContinuityAgent, combine_scores


def test_combine_scores_weights_face_highest():
    s = combine_scores(face=0.9, outfit=0.5, background=0.5)
    # face 0.5, outfit 0.25, background 0.25 -> 0.45+0.125+0.125 = 0.70 -> 70
    assert s == 70


def test_combine_scores_handles_missing_face():
    s = combine_scores(face=None, outfit=0.8, background=0.6)
    assert 0 <= s <= 100


@pytest.mark.asyncio
async def test_validate_never_recommends_retry():
    agent = ContinuityAgent.__new__(ContinuityAgent)
    agent.embedder = MagicMock()
    agent.embedder.model = MagicMock()
    agent.embedder.model.embed = MagicMock(return_value=[0.5] * 512)
    agent.embedder.compare_vectors = MagicMock(return_value=0.2)
    agent._sample = MagicMock(return_value=[b"f"])
    agent.qwen = MagicMock()
    agent.qwen.chat_vision_json = AsyncMock(return_value={"outfit_score": 0.3, "background_score": 0.4, "reason": "x"})
    agent.vl_prompt = "compare"
    agent.vl_model = "qwen3-vl-plus"
    bible = {"characters": {"Mia": {"variants": [{"plate_image_url": "u", "scene_numbers": [1], "is_default": True,
                                                   "face_vector": [0.5] * 512}]}},
             "location_by_scene": {1: "loc"}}
    out = await agent.validate(clip_url="c", duration=5, characters_in_frame=["Mia"], bible=bible, scene_number=1)
    assert "retry_instruction" not in out
    assert out["overall_pass"] is False
    assert 0 <= out["continuity_score"] <= 100
