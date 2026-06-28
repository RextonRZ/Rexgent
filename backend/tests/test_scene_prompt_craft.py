import pytest
from unittest.mock import AsyncMock, MagicMock
from app.mcp_tools.scene_prompt_craft import ScenePromptCraft


@pytest.mark.asyncio
async def test_craft_returns_prompt_no_names():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Close-up, static camera, young East Asian woman with sharp cheekbones, tense expression, dramatic side lighting, desaturated tones, 5s",
        "negative_prompt": "blurry, distorted face, text, watermark",
        "model_parameters": {"resolution": "1080p", "duration": 5, "audio_mode": "auto"},
    })
    crafter.prompt_template = "placeholder"

    result = await crafter.craft(
        shot={"shot_type": "CU", "camera_movement": "STATIC", "action": "She stares", "lighting": "DRAMATIC_SIDE", "colour_mood": "DESATURATED", "emotional_beat": "tension", "estimated_duration_seconds": 5},
        character_visuals={"Detective Yuki": {"video_prompt_fragment": "young East Asian woman, sharp cheekbones"}},
        target_model="wan",
    )
    assert "prompt" in result
    assert "Yuki" not in result["prompt"]
    assert len(result["prompt"].split()) <= 80


@pytest.mark.asyncio
async def test_craft_handles_non_dict():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value=["bad"])
    crafter.prompt_template = "placeholder"

    result = await crafter.craft(shot={}, character_visuals={}, target_model="happyhorse")
    assert result["prompt"] == ""
