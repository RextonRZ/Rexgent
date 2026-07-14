import pytest
from types import SimpleNamespace
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


@pytest.mark.asyncio
async def test_native_talk_frames_open_speaking():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "p", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    await crafter.craft(
        shot={"shot_type": "MS", "dialogue": "I can't believe this.",
              "estimated_duration_seconds": 5, "action": "sits"},
        character_visuals={"KIM": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", native_talk=True)
    content = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "aloud" in content or "audibly" in content          # native speaking instruction present
    assert "I can't believe this." in content                   # the line is passed
    assert "must never be sharply front-facing" not in content  # NOT the hide-mouth coverage block


@pytest.mark.asyncio
async def test_native_talk_off_keeps_coverage():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "p", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    await crafter.craft(
        shot={"shot_type": "MS", "dialogue": "I can't believe this.",
              "estimated_duration_seconds": 5, "action": "sits"},
        character_visuals={"KIM": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", lipsync=False, native_talk=False)
    content = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "must never be sharply front-facing" in content       # hide-mouth coverage unchanged when off


@pytest.mark.asyncio
async def test_native_talk_preserves_exact_line_through_sanitizer():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Medium shot of a woman at a table.",
        "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    line = "San-Ha, you look like you've seen a ghost."
    result = await crafter.craft(
        shot={"shot_type": "MS", "dialogue": line,
              "estimated_duration_seconds": 5, "action": "walks in"},
        character_visuals={"YOON": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", native_talk=True)
    # the EXACT scripted line must survive the text sanitizer (it was truncated
    # to "ve seen a ghost." before this fix)
    assert line in result["prompt"]


@pytest.mark.asyncio
async def test_native_talk_does_not_suppress_mouth_in_negative():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Medium shot of a woman.",
        "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MS", "dialogue": "Hello there.",
              "estimated_duration_seconds": 5, "action": "sits"},
        character_visuals={"KIM": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", native_talk=True)
    # native talk WANTS a readable talking mouth — the anti-mouth backstop is gone
    assert "clear front-facing talking mouth close-up" not in result["negative_prompt"]


@pytest.mark.asyncio
async def test_coverage_still_suppresses_mouth_in_negative():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Medium shot of a woman.",
        "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MS", "dialogue": "Hello there.",
              "estimated_duration_seconds": 5, "action": "sits"},
        character_visuals={"KIM": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", lipsync=False, native_talk=False)
    # unchanged when native talk is off: the mouth is still suppressed
    assert "clear front-facing talking mouth close-up" in result["negative_prompt"]


def test_image_ref_legend_maps_each_image_to_its_person():
    from app.services.reference_stack import image_ref_legend
    legend = image_ref_legend([
        {"url": "u1", "role": "identity", "character": "KIM"},
        {"url": "u2", "role": "costume", "character": "KIM"},
        {"url": "u3", "role": "identity", "character": "YOON"},
        {"url": "u4", "role": "location"}])
    assert "[Image 1] is KIM's face" in legend
    assert "[Image 2] is KIM's outfit" in legend
    assert "[Image 3] is YOON's face" in legend
    assert "[Image 4] is the location and set" in legend
    assert image_ref_legend([]) == ""


@pytest.mark.asyncio
async def test_image_legend_prepended_and_survives_sanitizer():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Medium shot of a woman.", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    legend = "Reference image guide: [Image 1] is KIM's face."
    result = await crafter.craft(
        shot={"shot_type": "MS", "estimated_duration_seconds": 5, "action": "sits"},
        character_visuals={"KIM": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", image_legend=legend)
    # the [Image N] tokens must survive the text sanitizer and lead the prompt
    assert result["prompt"].startswith(legend)
    assert "[Image 1]" in result["prompt"]


@pytest.mark.asyncio
async def test_native_talk_names_the_speaker_in_multi_person_shot():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Two people at a table.", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    line = "Joo-Won, I can't believe you're here."
    result = await crafter.craft(
        shot={"shot_type": "MS", "dialogue": line, "estimated_duration_seconds": 5, "action": "sits"},
        character_visuals={"KIM SAN-HA": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", native_talk=True, speaker="KIM SAN-HA")
    p = result["prompt"]
    assert "KIM SAN-HA is the one speaking" in p     # the speaker is named
    assert line in p                                  # the exact line survives
    assert "keeps a closed, still mouth" in p         # others held silent


@pytest.mark.asyncio
async def test_eyeline_appended_from_blocking():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={"prompt": "Two people in a room.", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MS", "estimated_duration_seconds": 5},
        character_visuals={"KIM": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse",
        blocking={"subjects": [{"character": "KIM", "eyeline": "at Yoon"},
                               {"character": "YOON", "eyeline": "off-camera left"}]})
    assert "looks at Yoon" in result["prompt"]


@pytest.mark.asyncio
async def test_final_prompt_normalizes_typographic_chars():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "black heels — she turns, the � light fading",
        "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(shot={"shot_type": "MS", "estimated_duration_seconds": 5},
                                 character_visuals={}, target_model="happyhorse")
    assert "�" not in result["prompt"]   # replacement char gone
    assert "—" not in result["prompt"]    # em dash normalized


@pytest.mark.asyncio
async def test_environment_appended_when_missing():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={"prompt": "A tense close-up.", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MS", "estimated_duration_seconds": 5},
        character_visuals={"KIM": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse",
        scene_setting={"location": "a dark street", "set_items": ["a parked sedan with bright headlights", "a broken streetlamp"]})
    assert "parked sedan" in result["prompt"] or "dark street" in result["prompt"]


@pytest.mark.asyncio
async def test_cinematic_flag_injects_camera_motion_sound(monkeypatch):
    import app.mcp_tools.scene_prompt_craft as spc
    monkeypatch.setattr(spc, "get_settings", lambda: SimpleNamespace(cinematic_prompt=True))
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={"prompt": "p", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    await crafter.craft(shot={"shot_type": "MS", "camera_movement": "DOLLY_IN", "estimated_duration_seconds": 5},
                        character_visuals={}, target_model="happyhorse")
    content = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "camera move" in content.lower()
    assert "sound" in content.lower()


@pytest.mark.asyncio
async def test_cinematic_flag_off_no_injection(monkeypatch):
    import app.mcp_tools.scene_prompt_craft as spc
    monkeypatch.setattr(spc, "get_settings", lambda: SimpleNamespace(cinematic_prompt=False))
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={"prompt": "p", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    await crafter.craft(shot={"shot_type": "MS", "estimated_duration_seconds": 5},
                        character_visuals={}, target_model="happyhorse")
    content = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "CINEMATIC" not in content


@pytest.mark.asyncio
async def test_craft_weaves_lens_and_composition_from_director_json(monkeypatch):
    from app.mcp_tools.scene_prompt_craft import ScenePromptCraft
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "A woman stands in a doorway.", "negative_prompt": ""})
    crafter.prompt_template = "placeholder"
    shot = {"shot_type": "CU", "action": "she turns",
            "director_json": {"light_quality": "soft", "lens": "85mm",
                              "composition": "rule_of_thirds"}}
    out = await crafter.craft(shot, character_visuals={}, target_model="happyhorse")
    # controls-first: the technical controls PREPEND, then the scene text
    assert out["prompt"].startswith("Soft light, 85mm lens, rule-of-thirds composition.")
    assert "85mm" in out["prompt"]
    assert "rule-of-thirds" in out["prompt"] or "rule of thirds" in out["prompt"]
    assert "woman stands in a doorway" in out["prompt"]     # scene survives


@pytest.mark.asyncio
async def test_craft_without_director_json_unchanged(monkeypatch):
    from app.mcp_tools.scene_prompt_craft import ScenePromptCraft
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "A woman stands in a doorway.", "negative_prompt": ""})
    crafter.prompt_template = "placeholder"
    out = await crafter.craft({"shot_type": "CU", "action": "she turns"},
                              character_visuals={}, target_model="happyhorse")
    assert "mm" not in out["prompt"]  # no lens clause injected
