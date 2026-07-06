import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.set_dresser import SetDresser, setting_for_shot


SET_JSON = {
    "set_items": ["blue ceramic vase on the oak side table", "rain streaked window"],
    "state_changes": [{"from_shot": 3, "state": "the blue vase lies shattered beside the table"}],
}


def _dresser(payload):
    d = SetDresser.__new__(SetDresser)
    d.qwen = MagicMock()
    d.qwen.chat_json = AsyncMock(return_value=payload)
    d.prompt_template = "placeholder"
    return d


@pytest.mark.asyncio
async def test_dress_returns_items_and_changes():
    d = _dresser(SET_JSON)
    out = await d.dress({"scene_number": 1}, [{"shot_number": 1}])
    assert out["set_items"] == SET_JSON["set_items"]
    assert out["state_changes"][0]["from_shot"] == 3


@pytest.mark.asyncio
async def test_dress_tolerates_garbage():
    d = _dresser(["not", "a", "dict"])
    out = await d.dress({}, [])
    assert out == {"set_items": [], "state_changes": []}
    d2 = _dresser({"set_items": None, "state_changes": [{"no_state": True}, "junk"]})
    out2 = await d2.dress({}, [])
    assert out2["set_items"] == []
    assert out2["state_changes"] == []


def test_setting_before_change_keeps_pristine_set():
    setting, changed = setting_for_shot(SET_JSON, "apartment living room", shot_number=2)
    assert changed is False
    assert "current_state" not in setting
    assert setting["set_items"] == SET_JSON["set_items"]
    assert setting["location"] == "apartment living room"


def test_setting_from_change_shot_applies_state_and_suppresses_plate():
    for n in (3, 4, 9):
        setting, changed = setting_for_shot(SET_JSON, "apartment living room", shot_number=n)
        assert changed is True, n
        assert setting["current_state"] == ["the blue vase lies shattered beside the table"]


def test_setting_none_when_scene_has_nothing():
    setting, changed = setting_for_shot(None, None, shot_number=1)
    assert setting is None
    assert changed is False


def test_setting_location_only_still_pins_the_room():
    setting, changed = setting_for_shot(None, "rooftop at night", shot_number=1)
    assert changed is False
    assert setting == {"location": "rooftop at night", "set_items": []}
