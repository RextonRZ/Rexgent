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
async def test_craft_neutralizes_character_named_location():
    # "Bear's apartment" where Bear is a person must reach the model as a plain
    # room, or the video renders the animal Bear inside the apartment
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "wide shot, apartment", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={"shot_type": "LS"},
        character_visuals={"Bear": {"video_prompt_fragment": "burly bearded man"}},
        target_model="wan",
        scene_setting={"location": "Bear's apartment", "set_items": ["Bear's armchair"]})
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    setting_line = [l for l in user_msg.splitlines() if "Scene setting" in l or "location" in l]
    joined = "\n".join(setting_line)
    assert "Bear's" not in joined       # possessive gone
    assert "apartment" in user_msg      # the room survives
    assert "armchair" in user_msg       # the prop survives, minus the name


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


@pytest.mark.asyncio
async def test_unsynced_dialogue_shot_gets_mouth_hiding_coverage():
    # the hybrid: a line that will NOT be mouth-driven is framed off the
    # readable mouth (OTS / profile / listener), never front-facing talking
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    result = await crafter.craft(
        shot={"shot_type": "MCU", "dialogue": "We need to go, now."},
        character_visuals={}, target_model="happyhorse")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Dialogue delivery" in user_msg
    assert "coverage" in user_msg
    assert "never be sharply front-facing" in user_msg
    assert "mid-conversation" not in user_msg
    assert "We need to go, now." in user_msg
    # the secondary backstop rides the negative prompt
    assert "talking mouth close-up" in result["negative_prompt"]


@pytest.mark.asyncio
async def test_lipsynced_dialogue_shot_stays_front_facing():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    result = await crafter.craft(
        shot={"shot_type": "MCU", "dialogue": "We need to go, now."},
        character_visuals={}, target_model="wan", lipsync=True)
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "mid-conversation" in user_msg
    assert "We need to go, now." in user_msg
    assert "talking mouth close-up" not in result["negative_prompt"]


@pytest.mark.asyncio
async def test_blocking_renders_absolute_positions():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={"shot_type": "MS"},
        character_visuals={}, target_model="happyhorse",
        blocking={"subjects": [
            {"character": "SOL", "frame_position": "FG", "screen_side": "right",
             "facing": "screen-left", "eyeline": "at the figure",
             "action": "stepping backward toward camera"},
            {"character": "FIGURE", "frame_position": "BG", "screen_side": "left",
             "facing": "screen-right", "action": "advancing"},
        ], "reverse_angle": False})
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Blocking (rule 12" in user_msg
    assert "SOL: FG, screen-right, facing screen-left" in user_msg
    assert "FIGURE: BG, screen-left, facing screen-right, advancing" in user_msg
    assert "REVERSE ANGLE" not in user_msg


@pytest.mark.asyncio
async def test_reverse_angle_is_declared():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={}, character_visuals={}, target_model="happyhorse",
        blocking={"subjects": [{"character": "SOL", "screen_side": "left"}],
                  "reverse_angle": True})
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "deliberate REVERSE ANGLE" in user_msg


@pytest.mark.asyncio
async def test_silent_shot_has_no_delivery_block():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(shot={"shot_type": "WS"}, character_visuals={},
                        target_model="happyhorse")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Dialogue delivery" not in user_msg


@pytest.mark.asyncio
async def test_blocking_posture_reaches_the_prompt():
    """posture=sitting must be SAID, not implied — without it the model
    invented one ('sitting on the bed' rendered standing at a window)."""
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={"shot_type": "OTS"},
        character_visuals={}, target_model="happyhorse",
        blocking={"subjects": [
            {"character": "LINDA", "frame_position": "MG", "screen_side": "right",
             "posture": "sitting", "facing": "away-from-camera",
             "action": "holding the phone"},
        ], "reverse_angle": False})
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "LINDA: MG, sitting, screen-right, facing away-from-camera" in user_msg


@pytest.mark.asyncio
async def test_presence_rule_anchors_listed_characters():
    """Characters the prompt lists must exist from frame one — without this
    the model invents arrivals (a person rising out of the ground, popping in
    as the framing tightens)."""
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={"shot_type": "MS", "action": "stands at the spot"},
        character_visuals={"EIRIK": {"video_prompt_fragment": "tall athlete"}},
        target_model="happyhorse")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Presence (rule 20)" in user_msg
    assert "ALREADY in the frame" in user_msg


@pytest.mark.asyncio
async def test_no_presence_rule_without_characters():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(shot={"shot_type": "WS", "action": "empty stadium"},
                        character_visuals={}, target_model="happyhorse")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Presence (rule 20)" not in user_msg
