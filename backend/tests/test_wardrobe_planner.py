import pytest
from unittest.mock import AsyncMock
from app.services.wardrobe_planner import WardrobePlanner, map_variant_for_scene


@pytest.mark.asyncio
async def test_plan_wardrobe_parses_variants():
    planner = WardrobePlanner.__new__(WardrobePlanner)
    planner.qwen = type("Q", (), {})()
    planner.qwen.chat_json = AsyncMock(return_value={
        "characters": [{"name": "Mia",
            "variants": [{"label": "uniform", "outfit_description": "navy uniform", "scene_numbers": [1, 2]},
                         {"label": "dress", "outfit_description": "red dress", "scene_numbers": [3]}]}]
    })
    planner.prompt_template = "x"
    # a script that EARNS the change (a time jump) keeps both variants, so this
    # exercises multi-variant parsing without the collapse backstop firing
    out = await planner.plan(
        structured={"scenes": [{"number": 3, "description": "Three days later, at the pier."}]},
        characters=[{"name": "Mia"}])
    assert out["Mia"][0]["label"] == "uniform"
    assert out["Mia"][1]["scene_numbers"] == [3]


@pytest.mark.asyncio
async def test_plan_collapses_to_one_outfit_without_an_earned_change():
    # no time jump / motivated change in the script -> the per-scene variants
    # collapse to a single outfit covering every scene
    planner = WardrobePlanner.__new__(WardrobePlanner)
    planner.qwen = type("Q", (), {})()
    planner.qwen.chat_json = AsyncMock(return_value={
        "characters": [{"name": "Mia",
            "variants": [{"label": "look1", "outfit_description": "navy shirt", "scene_numbers": [1]},
                         {"label": "look2", "outfit_description": "navy top", "scene_numbers": [2]}]}]
    })
    planner.prompt_template = "x"
    out = await planner.plan(
        structured={"scenes": [{"number": 1, "description": "They talk."},
                               {"number": 2, "description": "They keep talking."}]},
        characters=[{"name": "Mia"}])
    assert len(out["Mia"]) == 1
    assert out["Mia"][0]["scene_numbers"] == [1, 2]


def test_map_variant_for_scene_picks_matching():
    variants = [{"label": "uniform", "scene_numbers": [1, 2], "is_default": True},
                {"label": "dress", "scene_numbers": [3], "is_default": False}]
    assert map_variant_for_scene(variants, 3)["label"] == "dress"
    assert map_variant_for_scene(variants, 2)["label"] == "uniform"


def test_map_variant_for_scene_falls_back_to_default():
    variants = [{"label": "uniform", "scene_numbers": [1], "is_default": True},
                {"label": "dress", "scene_numbers": [3], "is_default": False}]
    assert map_variant_for_scene(variants, 99)["label"] == "uniform"
