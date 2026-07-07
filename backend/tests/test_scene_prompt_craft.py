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


@pytest.mark.asyncio
async def test_craft_injects_scene_setting_into_llm_input():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Wide shot, living room", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={"shot_type": "LS"}, character_visuals={}, target_model="wan",
        scene_setting={"location": "living room",
                       "set_items": ["blue ceramic vase on the oak table"],
                       "current_state": ["the blue vase lies shattered"]})
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Scene setting" in user_msg
    assert "blue ceramic vase" in user_msg
    assert "shattered" in user_msg


@pytest.mark.asyncio
async def test_craft_without_setting_has_no_setting_block():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(shot={}, character_visuals={}, target_model="wan")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Scene setting" not in user_msg


@pytest.mark.asyncio
async def test_craft_injects_adjacent_shot_actions():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "man stands alone breathing hard", "negative_prompt": "",
        "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={"shot_type": "MS", "action": "the man catches his breath"},
        character_visuals={}, target_model="happyhorse",
        prev_action="woman runs into the alley, man chases her",
        next_action="the man turns and walks toward a door")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Previous shot" in user_msg
    assert "do NOT replay" in user_msg
    assert "woman runs into the alley" in user_msg
    assert "Next shot" in user_msg


@pytest.mark.asyncio
async def test_craft_without_adjacent_shots_has_no_continuity_block():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(shot={}, character_visuals={}, target_model="wan")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Continuity with adjacent shots" not in user_msg


@pytest.mark.asyncio
async def test_craft_stages_foreground_character_as_occlusion():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "man in doorway", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={"shot_type": "OTS", "action": "the door opens on a man with a sword"},
        character_visuals={}, target_model="happyhorse",
        foreground_characters=["Woman Xin"])
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Foreground occlusion" in user_msg
    assert "Woman Xin" in user_msg
    assert "face turned away" in user_msg


@pytest.mark.asyncio
async def test_craft_without_foreground_has_no_occlusion_block():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(shot={}, character_visuals={}, target_model="wan")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Foreground occlusion" not in user_msg
