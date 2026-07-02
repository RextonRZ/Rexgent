import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.casting_director import distinct_locations, style_from_request


def test_distinct_locations_groups_by_key():
    scenes = [{"number": 1, "location": "Coffee Shop"},
              {"number": 2, "location": "coffee shop"},
              {"number": 3, "location": "Rooftop"}]
    locs = distinct_locations(scenes)
    keys = {l["location_key"]: l["scene_numbers"] for l in locs}
    assert keys["coffee_shop"] == [1, 2]
    assert keys["rooftop"] == [3]


@pytest.mark.asyncio
async def test_style_from_request_reframes_ip():
    qwen = MagicMock()
    qwen.chat_json = AsyncMock(return_value={
        "style_tags": ["stop-motion", "warm pastel"],
        "prompt": "stop-motion toy aesthetic, warm pastel palette",
        "negative_prompt": "photorealistic"})
    out = await style_from_request(qwen, "template", "make it like Toy Story")
    assert "stop-motion" in out["style_tags"]
    assert "prompt" in out


def test_assign_voice_matches_gender():
    from app.services.casting_director import assign_voice
    from app.services.voice_catalog import FEMALE_DEFAULTS, MALE_DEFAULTS
    from unittest.mock import MagicMock
    # female character gets a female preset
    fem = MagicMock(); fem.voice_id = None; fem.gender = "Female"
    assign_voice(fem, 0)
    assert fem.voice_id in FEMALE_DEFAULTS
    assert fem.voice_source == "preset"
    # male character gets a male preset
    male = MagicMock(); male.voice_id = None; male.gender = "male"
    assign_voice(male, 0)
    assert male.voice_id in MALE_DEFAULTS
    # two same-gender characters get distinct presets (rotated by index)
    f2 = MagicMock(); f2.voice_id = None; f2.gender = "woman"
    assign_voice(f2, 1)
    assert f2.voice_id in FEMALE_DEFAULTS and f2.voice_id != fem.voice_id


def test_default_voice_unknown_gender_falls_back():
    from app.services.voice_catalog import default_voice, FEMALE_DEFAULTS, MALE_DEFAULTS
    v = default_voice(None, 0)
    assert v in FEMALE_DEFAULTS + MALE_DEFAULTS
