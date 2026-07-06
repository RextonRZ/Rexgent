import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.storyboard_generator import StoryboardGenerator


@pytest.mark.asyncio
async def test_generate_returns_shots():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value=[
        {"shot_number": 1, "shot_type": "EWS", "camera_movement": "DRONE", "characters_in_frame": [], "action": "Rain-soaked street", "dialogue": None, "lighting": "NEON", "colour_mood": "DESATURATED", "emotional_beat": "dread", "estimated_duration_seconds": 4, "notes": ""},
        {"shot_number": 2, "shot_type": "CU", "camera_movement": "STATIC", "characters_in_frame": ["YUKI"], "action": "Yuki stares", "dialogue": "Something's wrong.", "lighting": "DRAMATIC_SIDE", "colour_mood": "COOL", "emotional_beat": "tension", "estimated_duration_seconds": 5, "notes": ""},
    ])
    gen.prompt_template = "placeholder"

    result = await gen.generate_for_scene(scene_json={"scene_number": 1}, characters_in_scene=[])
    assert len(result) == 2
    assert result[0]["shot_type"] == "EWS"
    assert result[1]["characters_in_frame"] == ["YUKI"]


@pytest.mark.asyncio
async def test_generate_handles_non_list():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value={"bad": "shape"})
    gen.prompt_template = "placeholder"

    result = await gen.generate_for_scene(scene_json={}, characters_in_scene=[])
    assert result == []


@pytest.mark.asyncio
async def test_scene_dialogue_reaches_the_prompt_verbatim():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    captured = {}

    async def fake_chat_json(messages, **kw):
        captured["user"] = messages[-1]["content"]
        return [{
            "shot_number": 1, "shot_type": "MS", "camera_movement": "STATIC",
            "characters_in_frame": ["EMI"], "action": "Emi on the phone",
            "dialogue": "Yes, I understand, Mrs. Tanaka.",
            "lighting": "NATURAL", "colour_mood": "WARM",
            "emotional_beat": "calm", "estimated_duration_seconds": 5, "notes": "",
        }]

    gen.qwen = MagicMock()
    gen.qwen.chat_json = fake_chat_json
    gen.prompt_template = "placeholder"

    scene = {
        "scene_number": 1,
        "heading": "INT. SATO LIVING ROOM - DAY",
        "dialogue": [{"character": "EMI", "line": "Yes, I understand, Mrs. Tanaka."}],
        "stage_directions": ["Emi is on the phone, keeping her voice calm."],
    }
    result = await gen.generate_for_scene(scene_json=scene, characters_in_scene=[])

    # the real line must be visible to the model, and preserved on the shot
    assert "Yes, I understand, Mrs. Tanaka." in captured["user"]
    assert result[0]["dialogue"] == "Yes, I understand, Mrs. Tanaka."


@pytest.mark.asyncio
async def test_shot_budget_grows_to_cover_every_line():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    returned = [
        {"shot_number": i, "shot_type": "MS", "camera_movement": "STATIC",
         "characters_in_frame": [], "action": "x", "dialogue": f"line {i}",
         "lighting": "NATURAL", "colour_mood": "WARM", "emotional_beat": "x",
         "estimated_duration_seconds": 5, "notes": ""}
        for i in range(8)
    ]
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value=returned)
    gen.prompt_template = "placeholder"

    scene = {"scene_number": 1,
             "dialogue": [{"character": "X", "line": f"line {i}"} for i in range(8)]}
    # base budget of 3 must not truncate an 8-line scene
    result = await gen.generate_for_scene(
        scene_json=scene, characters_in_scene=[], max_shots=3)
    assert len(result) == 8


@pytest.mark.asyncio
async def test_shot_budget_capped_for_runaway_scene():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    returned = [
        {"shot_number": i, "shot_type": "MS", "camera_movement": "STATIC",
         "characters_in_frame": [], "action": "x", "dialogue": f"line {i}",
         "lighting": "NATURAL", "colour_mood": "WARM", "emotional_beat": "x",
         "estimated_duration_seconds": 5, "notes": ""}
        for i in range(30)
    ]
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value=returned)
    gen.prompt_template = "placeholder"

    scene = {"scene_number": 1,
             "dialogue": [{"character": "X", "line": f"l{i}"} for i in range(30)]}
    result = await gen.generate_for_scene(scene_json=scene, characters_in_scene=[])
    assert len(result) == StoryboardGenerator._HARD_CAP
