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
    # bloat guard: deterministic clauses (solo hold, identity lock, emotion,
    # reaction-face visibility) ride every minimal solo shot — budgeted, but
    # never runaway
    assert len(result["prompt"].split()) <= 115


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
    # KIM is ALONE in frame and Yoon is her off-screen listener: the eyeline
    # sits beside the lens and the off-frame name never enters the prompt
    # (naming Yoon here used to risk rendering a second person)
    assert "Eyelines: KIM looks just beside the camera" in result["prompt"]
    assert "Yoon" not in result["prompt"]


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
async def test_craft_optics_not_duplicated_in_prefix(monkeypatch):
    # consolidation (one controls statement): lens/composition/light_quality are
    # NOT re-prepended as a second controls clause — the model body states them
    # once (it sees director_json in the shot data). Only director TREATMENTS
    # (special_effect/stylization) lead; here there are none, so nothing prepends.
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
    assert not out["prompt"].startswith("Soft light")      # no duplicate controls prefix
    assert "85mm lens" not in out["prompt"]                # optics not re-injected
    assert "woman stands in a doorway" in out["prompt"]    # scene survives
    assert out["prompt"].rstrip().endswith("Duration: 5 seconds.")  # duration LAST


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


def _spc():
    from app.mcp_tools.scene_prompt_craft import ScenePromptCraft
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "A quiet street at dawn.", "negative_prompt": ""})
    crafter.prompt_template = "placeholder"
    return crafter


@pytest.mark.asyncio
async def test_craft_prefix_is_treatments_only():
    # the treatments prefix carries ONLY special_effect + stylization (a look
    # the model body won't state); the optical controls (light/lens/composition)
    # are NOT duplicated here — they live once in the body.
    crafter = _spc()
    shot = {"shot_type": "EWS", "action": "light creeps in",
            "director_json": {"stylization": "cinematic", "special_effect": "tilt_shift",
                              "light_quality": "side", "lens": "24mm",
                              "composition": "leading_lines"}}
    out = await crafter.craft(shot, character_visuals={}, target_model="wan")
    assert out["prompt"].startswith("Tilt-shift, cinematic.")
    assert "24mm" not in out["prompt"]          # optics not duplicated in the prefix
    assert "leading-lines" not in out["prompt"]


@pytest.mark.asyncio
async def test_craft_to_wan_scenery_gets_ambience_and_score():
    # a faceless scenery beat (establishing / atmosphere) carries its OWN
    # suitable sound: rich ambience, SFX and a subtle mood-matched score —
    # these are exactly the moments music belongs
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "EWS", "action": "wind on an empty street",
         "estimated_duration_seconds": 5, "emotional_beat": "lonely calm"},
        character_visuals={}, target_model="wan", to_wan=True)
    p = out["prompt"]
    assert "atmospheric musical score" in p
    assert "lonely calm" in p
    assert "No dialogue" in p
    # duration is LAST; the sound tail sits just before it
    assert p.rstrip().endswith("Duration: 5 seconds.")
    assert p.index("ambient sound") < p.index("Duration:")


@pytest.mark.asyncio
async def test_prev_frame_report_feeds_the_opening_state():
    # the VL frame handoff: what the previous clip ACTUALLY ended on reaches
    # the prompt, with the opening-state rule attached
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "action": "she rises"},
        character_visuals={"ANNA": "a woman"}, target_model="happyhorse",
        prev_frame_report="The woman in the navy shirt is seated on the sofa, "
                          "hands folded; the door behind her is closed.")
    sent = crafter.qwen.chat_json.call_args.kwargs["messages"][1]["content"]
    assert "actually ENDED like this" in sent
    assert "seated on the sofa" in sent
    assert "OPENING STATE" in sent


@pytest.mark.asyncio
async def test_two_person_shot_eyelines_lock_to_each_other():
    # scene 1 shot 5: BOTH characters looked into the lens. In a two-person
    # shot a vague or camera eyeline deterministically becomes "at {other}".
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "action": "she reacts"},
        character_visuals={"CATHERINE": "a woman", "AIDEN": "a boy"},
        target_model="happyhorse",
        blocking={"subjects": [
            {"character": "CATHERINE", "eyeline": "camera"},
            {"character": "AIDEN", "eyeline": "toward the other character"}]})
    p = out["prompt"]
    assert "CATHERINE looks at AIDEN" in p
    assert "AIDEN looks at CATHERINE" in p
    assert "lens" not in p


@pytest.mark.asyncio
async def test_back_turned_subject_stays_back_turned():
    # a hold showing someone's back must not rotate them to camera — the
    # revealed face never matches the cast
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "action": "they hold the moment"},
        character_visuals={"DEOK": "a man"}, target_model="wan",
        blocking={"subjects": [{"character": "DEOK",
                                "facing": "away-from-camera"}]})
    assert "keeps their back to the camera" in out["prompt"]
    assert "turning around to face the camera" in out["negative_prompt"]


@pytest.mark.asyncio
async def test_negative_bans_invented_facial_hair_and_blemishes():
    # scene 2 shot 3 grew a beard and a moustache on a clean-shaven man, and
    # close-ups invented pimples — banned unless a description wears them
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "action": "he listens"},
        character_visuals={"DEOK": "a man with a sharp jawline, short black hair"},
        target_model="happyhorse")
    neg = out["negative_prompt"]
    assert "beard" in neg and "mustache" in neg
    assert "acne" in neg and "pimples" in neg


@pytest.mark.asyncio
async def test_negative_bans_duplicated_people():
    # scene 1 shot 2 rendered TWO Lucases from the prev-frame reference —
    # any peopled shot bans rendering the same person twice
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "action": "they argue"},
        character_visuals={"ANGELINE": "a girl", "LUCAS": "a boy"},
        target_model="happyhorse")
    neg = out["negative_prompt"]
    assert "same person twice" in neg
    assert "duplicate" in neg


@pytest.mark.asyncio
async def test_no_duplicate_ban_on_empty_frame():
    # a scenery shot has no people to duplicate — the ban stays out so the
    # negative doesn't smuggle person-language into an empty landscape
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "LS", "action": "the empty street"},
        character_visuals={}, target_model="wan")
    assert "same person twice" not in out["negative_prompt"]


@pytest.mark.asyncio
async def test_described_beard_is_not_banned():
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "action": "he listens"},
        character_visuals={"JAE": "an older man with a salt-and-pepper beard"},
        target_model="happyhorse")
    assert "beard" not in out["negative_prompt"].replace("salt-and-pepper beard", "")
    # skin bans still apply
    assert "acne" in out["negative_prompt"]


@pytest.mark.asyncio
async def test_scenery_shots_skip_the_facial_bans():
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "EWS", "action": "the empty shore"},
        character_visuals={}, target_model="wan", to_wan=True)
    assert "beard" not in out["negative_prompt"]
    assert "acne" not in out["negative_prompt"]


@pytest.mark.asyncio
async def test_craft_to_wan_peopled_hold_keeps_music_out():
    # a silent held beat sits BETWEEN two spoken lines — a 3s score swell
    # mid-conversation jars against the talking clips around it
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "action": "they hold the silence",
         "estimated_duration_seconds": 3},
        character_visuals={"ANNA": "a woman in a navy sweater"},
        target_model="wan", to_wan=True)
    p = out["prompt"]
    assert "Ambient sound and diegetic sound effects. No dialogue. No background music." in p
    assert "musical score" not in p


@pytest.mark.asyncio
async def test_craft_to_wan_false_is_byte_identical_to_default_path():
    # the wan sound tail must NOT appear when to_wan is False, and the output must
    # be byte-identical to the pre-existing (no-param) path.
    a = _spc()
    b = _spc()
    shot = {"shot_type": "EWS", "action": "wind on an empty street",
            "estimated_duration_seconds": 5}
    out_default = await a.craft(shot, character_visuals={}, target_model="wan")
    out_false = await b.craft(shot, character_visuals={}, target_model="wan", to_wan=False)
    assert out_default["prompt"] == out_false["prompt"]           # byte-identical
    assert "No dialogue. No background music." not in out_false["prompt"]


@pytest.mark.asyncio
async def test_craft_to_wan_dialogue_shot_never_gets_no_dialogue_clause():
    # a Wan-flagged shot that (contrary to routing) carries a line must NOT get the
    # No-dialogue tail — the tail is only for silent visual shots.
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "dialogue": "We have to leave.",
         "estimated_duration_seconds": 5},
        character_visuals={}, target_model="wan", to_wan=True)
    assert "No dialogue." not in out["prompt"]
    assert "No background music." not in out["prompt"]


# ── prompt-formula rework: type tag, env-first, appendages before duration ──

@pytest.mark.asyncio
async def test_craft_type_tag_single_speaker():
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MCU", "action": "she speaks", "dialogue": "Hello.",
         "estimated_duration_seconds": 5},
        character_visuals={"Anna": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse")
    assert out["prompt"].startswith("Single speaker.")


@pytest.mark.asyncio
async def test_craft_type_tag_group_conversation():
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "action": "they talk", "dialogue": "Hello.",
         "estimated_duration_seconds": 5},
        character_visuals={"Anna": {"video_prompt_fragment": "a woman"},
                           "Deok": {"video_prompt_fragment": "a man"}},
        target_model="happyhorse")
    assert out["prompt"].startswith("Group conversation.")


@pytest.mark.asyncio
async def test_craft_silent_shot_has_no_type_tag():
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "EWS", "action": "an empty cliff", "estimated_duration_seconds": 5},
        character_visuals={}, target_model="wan")
    assert not out["prompt"].startswith("Single speaker.")
    assert not out["prompt"].startswith("Group conversation.")


@pytest.mark.asyncio
async def test_craft_eyeline_gated_to_in_frame_cast():
    # the S1-1 scenery leak: a stray blocking subject on a no-cast shot must NOT
    # put a named person into a Wan prompt via the eyeline appendage
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "EWS", "action": "empty cliff at dusk", "estimated_duration_seconds": 5},
        character_visuals={},                      # scenery: NO in-frame cast
        target_model="wan",
        blocking={"subjects": [{"character": "Anna", "eyeline": "toward the sea"}]})
    assert "Anna" not in out["prompt"]
    assert "Eyelines" not in out["prompt"]


@pytest.mark.asyncio
async def test_craft_native_talk_line_sits_before_duration():
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MCU", "action": "she speaks", "dialogue": "Who are you?",
         "estimated_duration_seconds": 5},
        character_visuals={"Anna": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", native_talk=True, speaker="Anna")
    p = out["prompt"]
    assert "Who are you?" in p
    assert p.rstrip().endswith("Duration: 5 seconds.")     # duration LAST
    assert p.index("Who are you?") < p.index("Duration:")  # speech before it


@pytest.mark.asyncio
async def test_identity_pins_survive_a_paraphrasing_body():
    # the Snowy bug: the crafter LLM paraphrased Angeline and DROPPED the
    # "no eyewear" pin — the render invented glasses and a headband. The pins
    # must be re-stated deterministically and the unworn items banned.
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "CU, a young girl points excitedly at the fence, warm daylight",
        "negative_prompt": "blurry", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "CU", "dialogue": "There he is!",
              "estimated_duration_seconds": 5},
        character_visuals={"ANGELINE": {"video_prompt_fragment":
            "8-year-old girl, shoulder-length straight black hair center-parted "
            "and loose, clean-shaven, no eyewear"}},
        target_model="happyhorse", native_talk=True, speaker="ANGELINE")
    p = result["prompt"].lower()
    assert "no eyewear" in p
    assert "no hair accessories" in p
    neg = result["negative_prompt"].lower()
    assert "eyeglasses" in neg
    assert "headband" in neg


@pytest.mark.asyncio
async def test_worn_eyewear_and_accessories_are_never_banned():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "MCU, a teenage boy hesitates in the doorway",
        "negative_prompt": "blurry", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MCU", "estimated_duration_seconds": 5},
        character_visuals={"THEO": {"video_prompt_fragment":
            "teenage boy wearing black rectangular glasses, short wavy hair "
            "with a blue headband, clean-shaven"}},
        target_model="happyhorse")
    p = result["prompt"].lower()
    assert "black rectangular glasses" in p     # the pin is re-stated
    neg = result["negative_prompt"].lower()
    assert "eyeglasses" not in neg
    assert "headband" not in neg


@pytest.mark.asyncio
async def test_emotional_beat_lands_as_visible_expression():
    # scene 2 shot 5: beat said "confusion and hurt" but the render came out
    # neutral — the beat must reach the prompt as an on-face instruction
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "MS, a girl faces a boy near the garden fence",
        "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MS", "estimated_duration_seconds": 5,
              "emotional_beat": "Confusion and hurt, with a hint of betrayal"},
        character_visuals={"ANGELINE": {"video_prompt_fragment": "8-year-old girl"}},
        target_model="happyhorse")
    p = result["prompt"]
    assert "Confusion and hurt" in p
    assert "facial expressions" in p


def test_decamera_action_redirects_lens_stares():
    # boards leak camera-referential staging into ACTION text; rendered
    # literally it pulls a straight into the lens stare
    from app.mcp_tools.scene_prompt_craft import decamera_action
    out = decamera_action("She is now closer to the camera, still searching.")
    assert "camera," not in out.split("off-camera")[0] or "viewer" in out
    assert "the viewer" in out
    assert "never into the lens" in out
    # camera-free actions pass through untouched
    plain = "She kneels by the hutch."
    assert decamera_action(plain) == plain
    assert decamera_action(None) is None


def test_solo_eyeline_absorbs_into_the_task():
    # the Dora the Explorer case: a solo subject presenting to camera while
    # supposedly searching — vague eyelines resolve to task absorption
    from app.mcp_tools.scene_prompt_craft import solo_eyeline
    out = solo_eyeline("off-camera")
    assert "what they are doing" in out and "never" in out
    assert solo_eyeline("at the camera") == out
    # a SPECIFIC eyeline the board wrote survives untouched
    assert solo_eyeline("at the empty hutch") == "at the empty hutch"


@pytest.mark.asyncio
async def test_solo_shot_bans_fourth_wall_and_absorbs():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Medium close-up, a girl searching the bushes",
        "negative_prompt": "blurry", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MCU", "action": "She searches the bushes",
              "estimated_duration_seconds": 5},
        character_visuals={"Angeline": {"video_prompt_fragment": "an 8-year-old girl"}},
        target_model="happyhorse",
        blocking={"subjects": [{"character": "Angeline", "eyeline": "off-camera"}]})
    assert "absorbed in what they are doing" in result["prompt"]
    assert "looking at the camera" in result["negative_prompt"]
    assert "breaking the fourth wall" in result["negative_prompt"]


def test_solo_eyeline_to_offscreen_listener_sits_beside_the_lens():
    # a clean single in a conversation: the listener is off-frame at the
    # camera position — the gaze rests just past the lens, never into it,
    # and never gets rewritten into task absorption
    from app.mcp_tools.scene_prompt_craft import resolve_solo_eyeline
    text, mode = resolve_solo_eyeline("at Theo", ["Angeline"])
    assert mode == "listener"
    assert "off-screen" in text and "never directly into" in text
    assert "Theo" not in text  # off-frame names must not enter the prompt
    # explicit off-screen direction from the board counts too
    text2, mode2 = resolve_solo_eyeline("at Mia, off-screen near camera", ["Rex"])
    assert mode2 == "listener"


def test_solo_eyeline_objects_and_vague_keep_old_behavior():
    from app.mcp_tools.scene_prompt_craft import resolve_solo_eyeline
    # an OBJECT eyeline the board wrote survives untouched (authored)
    text, mode = resolve_solo_eyeline("at the empty hutch", ["Angeline"])
    assert (text, mode) == ("at the empty hutch", "authored")
    # vague still resolves to task absorption
    text2, mode2 = resolve_solo_eyeline("off-camera", ["Angeline"])
    assert mode2 == "absorbed" and "what they are doing" in text2
    # the subject s own name (self-reference noise) is not a listener
    text3, mode3 = resolve_solo_eyeline("at Angeline", ["Angeline"])
    assert mode3 == "absorbed"


@pytest.mark.asyncio
async def test_solo_listener_shot_keeps_near_lens_gaze():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Medium close-up, a girl speaking",
        "negative_prompt": "blurry", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MCU", "action": "She pleads with him",
              "estimated_duration_seconds": 5},
        character_visuals={"Angeline": {"video_prompt_fragment": "an 8-year-old girl"}},
        target_model="happyhorse",
        blocking={"subjects": [{"character": "Angeline", "eyeline": "at Theo"}]})
    # the listener clause replaces the absorbed clause...
    assert "speaking to someone OFF-SCREEN" in result["prompt"]
    assert "absorbed in what they are doing" not in result["prompt"]
    # ...and the negative bans only the true lens stare, not near-lens gaze
    assert "staring directly into the lens" in result["negative_prompt"]
    assert "looking at the camera" not in result["negative_prompt"]


def test_child_scale_clause_pins_the_height_gap():
    from app.mcp_tools.scene_prompt_craft import child_scale_clause
    visuals = {"Angeline": {"video_prompt_fragment": "a realistic 8-year-old girl"},
               "John": {"video_prompt_fragment": "a 17-year-old boy, lean"}}
    clause = child_scale_clause(visuals)
    assert "8-year-old" in clause and "shorter" in clause
    # two adults: no clause
    adults = {"A": {"video_prompt_fragment": "a woman in her 30s"},
              "B": {"video_prompt_fragment": "a 40-year-old man"}}
    assert child_scale_clause(adults) == ""


def test_headwear_pin_finds_cap_in_outfit():
    # the Lucas cap bug: a knit cap lives in the OUTFIT (kept out of the
    # identity fragment by design), so the pin must read the outfit, not just
    # the fragment
    from app.mcp_tools.scene_prompt_craft import headwear_pin
    pin = headwear_pin("8-year-old boy, short brown hair, no eyewear",
                       "navy hoodie, blue jeans, a navy knit cap")
    assert "knit cap" in pin.lower()


def test_headwear_pin_matches_common_headwear_words():
    from app.mcp_tools.scene_prompt_craft import headwear_pin
    assert headwear_pin("", "a red beanie")
    assert headwear_pin("", "a straw hat")
    # a hood counts; a hooded sweatshirt alone does not falsely trigger
    assert headwear_pin("", "hood pulled up over the head")
    # neck scarf is not headwear
    assert headwear_pin("", "a woollen neck scarf") == ""


def test_headwear_pin_empty_when_bare_headed():
    from app.mcp_tools.scene_prompt_craft import headwear_pin
    assert headwear_pin("a girl, long black hair", "white t-shirt, denim overalls") == ""


@pytest.mark.asyncio
async def test_headwear_pinned_when_body_drops_it():
    # the Lucas cap bug: on an OTS reverse angle the crafter LLM's body
    # omitted the knit cap and the render dropped it. The cap lives in
    # outfit_this_shot, so it must be re-pinned deterministically like the
    # eyewear/hair pins already are.
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "OTS, a young boy faces a girl across the backyard, overcast light",
        "negative_prompt": "blurry", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "OTS", "estimated_duration_seconds": 5},
        character_visuals={"LUCAS": {
            "video_prompt_fragment": "8-year-old boy, short brown hair, no eyewear",
            "outfit_this_shot": "navy hoodie, blue jeans, a navy knit cap"}},
        target_model="happyhorse")
    assert "knit cap" in result["prompt"].lower()   # re-stated by the identity lock


@pytest.mark.asyncio
async def test_bare_headed_character_gets_no_cap_pin():
    # a character with no headwear must not have one invented into the lock
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "MS, a girl stands by the fence, warm daylight",
        "negative_prompt": "blurry", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MS", "estimated_duration_seconds": 5},
        character_visuals={"ANGELINE": {
            "video_prompt_fragment": "8-year-old girl, long red hair, no eyewear",
            "outfit_this_shot": "white t-shirt, denim overalls"}},
        target_model="happyhorse")
    import re as _re
    p = result["prompt"].lower()
    # word boundaries: "hat" must not false-match "what they are doing"
    assert not _re.search(r"\b(cap|beanie|hat|hood|toque)\b", p)


@pytest.mark.asyncio
async def test_blocking_surfaces_held_object():
    # the birdcage bug: a carried object on a subject must reach the prompt so
    # the model keeps it in hand instead of dropping it between shots
    crafter = _spc()
    await crafter.craft(
        {"shot_type": "MS", "action": "she turns to the boy"},
        character_visuals={"ANGELINE": "a girl"}, target_model="happyhorse",
        blocking={"subjects": [
            {"character": "ANGELINE", "frame_position": "MG", "screen_side": "left",
             "holding": "a birdcage"}]})
    sent = crafter.qwen.chat_json.call_args.kwargs["messages"][1]["content"]
    assert "holding a birdcage" in sent


@pytest.mark.asyncio
async def test_two_person_shot_holds_mutual_gaze_to_the_end():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "Two people arguing in a room",
        "negative_prompt": "blurry", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    result = await crafter.craft(
        shot={"shot_type": "MS", "estimated_duration_seconds": 5},
        character_visuals={"Angeline": {"video_prompt_fragment": "a girl"},
                           "John": {"video_prompt_fragment": "a boy"}},
        target_model="happyhorse",
        blocking={"subjects": [{"character": "Angeline", "eyeline": "off-camera"},
                               {"character": "John", "eyeline": "off-camera"}]})
    # both clips ended with the pair turned to the lens: the hold runs to
    # the final frame and the negative bans the turn outright
    assert "for the ENTIRE shot" in result["prompt"]
    assert "final frame" in result["prompt"]
    assert "turning to face the camera" in result["negative_prompt"]


@pytest.mark.asyncio
async def test_exiting_character_gets_back_stays_back():
    # s4sh3: "Angeline ... runs away ... runs out of the frame" — the stager
    # wrote facing 'right' (off-vocab) so the back-clause never fired, and the
    # model turned her to the lens at the clip tail. An EXIT action is itself
    # the signal: the runner recedes, back to camera, never turning around.
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "LS", "estimated_duration_seconds": 5,
         "action": "Angeline, still holding the note, runs away through the "
                   "backyard, her silhouette disappearing into the distance. "
                   "Claire stands in the background as Angeline runs out of the frame."},
        character_visuals={"Angeline": "a girl", "Claire": "a woman"},
        target_model="wan",
        blocking={"subjects": [
            {"character": "Angeline", "facing": "right", "posture": "running"},
            {"character": "Claire", "facing": "left"}]})
    # singular "keeps" proves ONLY Angeline exits — Claire stands watching
    # (a plural join would read "Angeline, Claire keep their back...")
    assert "Angeline keeps their back to the camera" in out["prompt"]
    assert "turning around to face the camera" in out["negative_prompt"]


@pytest.mark.asyncio
async def test_walking_to_the_door_is_not_an_exit():
    # movement inside the room is not an exit — no back-clause forced
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "MS", "estimated_duration_seconds": 5,
         "action": "Anna runs to the door and stops, listening."},
        character_visuals={"Anna": "a woman"}, target_model="happyhorse",
        blocking={"subjects": [{"character": "Anna", "facing": "screen-left"}]})
    assert "back to the camera" not in out["prompt"]


@pytest.mark.asyncio
async def test_emotional_closeup_pins_the_face_visible():
    # s3sh2: a reaction CU rendered the back of her head — the whole point of
    # the shot (her expression) was invisible. A silent emotional close-up
    # must SAY the face is visible and ban the rear view.
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "CU", "estimated_duration_seconds": 4,
         "emotional_beat": "Intense emotional pain and confusion",
         "action": "She processes what she has overheard."},
        character_visuals={"Angeline": "a girl"}, target_model="happyhorse",
        blocking={"subjects": [{"character": "Angeline", "facing": "screen"}]})
    assert "face is clearly visible" in out["prompt"]
    assert "back of head" in out["negative_prompt"]


@pytest.mark.asyncio
async def test_deliberate_back_shot_keeps_its_back():
    # an explicitly staged back view (negative-space beat) is not overridden
    crafter = _spc()
    out = await crafter.craft(
        {"shot_type": "CU", "estimated_duration_seconds": 4,
         "emotional_beat": "quiet grief",
         "action": "She stands motionless at the window."},
        character_visuals={"Angeline": "a girl"}, target_model="wan",
        blocking={"subjects": [{"character": "Angeline",
                                "facing": "away-from-camera"}]})
    assert "face is clearly visible" not in out["prompt"]
    assert "keeps their back to the camera" in out["prompt"]


@pytest.mark.asyncio
async def test_two_person_native_talk_pins_the_speakers_face():
    # "the cast most of it facing back when talk": in two-person dialogue
    # shots nothing said WHOSE face must be on camera, so speakers delivered
    # lines as the back of a head. The craft must pin the named speaker
    # front/three-quarter and allow only a listener to be seen from behind.
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "p", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    await crafter.craft(
        shot={"shot_type": "OTS", "dialogue": "Angeline, wait!",
              "estimated_duration_seconds": 5, "action": "pleads"},
        character_visuals={"CLAIRE": {"video_prompt_fragment": "a woman"},
                           "ANGELINE": {"video_prompt_fragment": "a girl"}},
        target_model="happyhorse", native_talk=True, speaker="Claire")
    content = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Claire's face" in content
    assert "never the back of the head" in content


@pytest.mark.asyncio
async def test_solo_native_talk_needs_no_speaker_name_clause():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "p", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    await crafter.craft(
        shot={"shot_type": "MCU", "dialogue": "Snowy, where are you?",
              "estimated_duration_seconds": 5, "action": "searches"},
        character_visuals={"ANGELINE": {"video_prompt_fragment": "a girl"}},
        target_model="happyhorse", native_talk=True, speaker="Angeline")
    content = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Angeline's face" not in content   # solo framing already covers it


@pytest.mark.asyncio
async def test_bridge_from_prev_opens_on_the_last_frame():
    # the shot-to-shot teleport fix: the clip opens on exactly the previous
    # shot's final frame, holds it a beat, then moves into this shot's staging
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "p", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    await crafter.craft(
        shot={"shot_type": "MS", "dialogue": "", "estimated_duration_seconds": 5,
              "action": "Claire stands in the doorway"},
        character_visuals={"CLAIRE": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse", bridge_from_prev=True)
    content = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "motionless" in content
    assert "final reference image" in content


@pytest.mark.asyncio
async def test_no_bridge_without_the_flag():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "p", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"
    await crafter.craft(
        shot={"shot_type": "MS", "dialogue": "", "estimated_duration_seconds": 5,
              "action": "Claire stands in the doorway"},
        character_visuals={"CLAIRE": {"video_prompt_fragment": "a woman"}},
        target_model="happyhorse")
    content = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "motionless" not in content


def test_child_scale_clause_reads_chinese_ages():
    # zh fragments write 10岁 / 三十八岁 — the English-only age regex never
    # matched, so the height pin silently skipped zh casts and the girl
    # rendered taller than her mother
    from app.mcp_tools.scene_prompt_craft import child_scale_clause
    visuals = {"安吉琳": {"video_prompt_fragment": "10岁的小女孩，扎着马尾辫"},
               "玛丽": {"video_prompt_fragment": "三十八岁的母亲，围着围裙"}}
    clause = child_scale_clause(visuals)
    assert "10" in clause
    assert "shorter" in clause


def test_creature_scale_clause_pins_small_pets():
    # the rendered rabbit ballooned to half the girl's height — nothing pinned
    # a creature's real-world size the way child_scale_clause pins children
    from app.mcp_tools.scene_prompt_craft import creature_scale_clause
    visuals = {"安吉琳": {"video_prompt_fragment": "10岁的小女孩"},
               "雪球": {"video_prompt_fragment": "一只蓬松的白色小兔子，戴着红色项圈"}}
    clause = creature_scale_clause(visuals)
    assert "rabbit" in clause
    assert "small" in clause
    assert "every frame" in clause


def test_creature_scale_clause_silent_without_creatures_or_humans():
    from app.mcp_tools.scene_prompt_craft import creature_scale_clause
    assert creature_scale_clause({"A": {"video_prompt_fragment": "a tall man"}}) == ""
    # a creature alone in frame has no human to scale against
    assert creature_scale_clause(
        {"雪球": {"video_prompt_fragment": "一只白色小兔子"}}) == ""
