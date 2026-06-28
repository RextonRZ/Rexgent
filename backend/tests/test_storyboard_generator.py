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
