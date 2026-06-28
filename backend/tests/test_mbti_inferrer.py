import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.mbti_inferrer import MBTIInferrer


@pytest.mark.asyncio
async def test_infer_returns_mbti():
    inferrer = MBTIInferrer.__new__(MBTIInferrer)
    inferrer.qwen = MagicMock()
    inferrer.qwen.chat_json = AsyncMock(return_value={
        "mbti_type": "INTJ",
        "confidence": 82,
        "dimension_analysis": {"E_vs_I": "introverted", "S_vs_N": "intuitive", "T_vs_F": "thinking", "J_vs_P": "judging"},
        "key_traits": ["strategic", "reserved", "decisive"],
        "how_this_affects_dialogue": "terse and precise",
    })
    inferrer.prompt_template = "placeholder"

    result = await inferrer.infer(
        character_name="Yuki",
        dialogue_samples=["I don't trust machines."],
        personality_summary="Guarded detective.",
    )
    assert result["mbti_type"] == "INTJ"
    assert result["confidence"] == 82


@pytest.mark.asyncio
async def test_infer_builds_user_content():
    inferrer = MBTIInferrer.__new__(MBTIInferrer)
    inferrer.qwen = MagicMock()
    inferrer.qwen.chat_json = AsyncMock(return_value={"mbti_type": "ENFP", "confidence": 70})
    inferrer.prompt_template = "system prompt"

    await inferrer.infer(
        character_name="Aria",
        dialogue_samples=["Hello world"],
        personality_summary="Curious AI.",
        actions_summary="Explores freely.",
    )

    call_args = inferrer.qwen.chat_json.call_args
    user_msg = call_args[1]["messages"][1]["content"]
    assert "Aria" in user_msg
    assert "Curious AI" in user_msg
    assert "Explores freely" in user_msg


@pytest.mark.asyncio
async def test_infer_handles_non_dict():
    inferrer = MBTIInferrer.__new__(MBTIInferrer)
    inferrer.qwen = MagicMock()
    inferrer.qwen.chat_json = AsyncMock(return_value=["bad"])
    inferrer.prompt_template = "placeholder"

    result = await inferrer.infer(
        character_name="X", dialogue_samples=[], personality_summary="y"
    )
    assert result["mbti_type"] is None
