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


@pytest.mark.asyncio
async def test_assign_voice_designs_when_missing():
    from app.services.casting_director import assign_voice
    from unittest.mock import AsyncMock, MagicMock
    qwen = MagicMock(); qwen.design_voice = AsyncMock(return_value="designed:42")
    char = MagicMock(); char.voice_id = None; char.visual_description = "gruff detective"
    await assign_voice(qwen, char)
    assert char.voice_id == "designed:42"
    assert char.voice_source == "designed"
