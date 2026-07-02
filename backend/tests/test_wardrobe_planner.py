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
    out = await planner.plan(structured={"scenes": []}, characters=[{"name": "Mia"}])
    assert out["Mia"][0]["label"] == "uniform"
    assert out["Mia"][1]["scene_numbers"] == [3]


def test_map_variant_for_scene_picks_matching():
    variants = [{"label": "uniform", "scene_numbers": [1, 2], "is_default": True},
                {"label": "dress", "scene_numbers": [3], "is_default": False}]
    assert map_variant_for_scene(variants, 3)["label"] == "dress"
    assert map_variant_for_scene(variants, 2)["label"] == "uniform"


def test_map_variant_for_scene_falls_back_to_default():
    variants = [{"label": "uniform", "scene_numbers": [1], "is_default": True},
                {"label": "dress", "scene_numbers": [3], "is_default": False}]
    assert map_variant_for_scene(variants, 99)["label"] == "uniform"
