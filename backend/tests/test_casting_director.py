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


def test_assign_voice_picks_preset():
    from app.services.casting_director import assign_voice, VOICE_POOL
    from unittest.mock import MagicMock
    char = MagicMock(); char.voice_id = None
    assign_voice(char, 0)
    assert char.voice_id == VOICE_POOL[0]
    assert char.voice_source == "preset"
    # a second character (index 1) gets a different preset
    char2 = MagicMock(); char2.voice_id = None
    assign_voice(char2, 1)
    assert char2.voice_id == VOICE_POOL[1]
    assert char2.voice_id != char.voice_id
