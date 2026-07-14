# backend/tests/test_stager.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.storyboard_generator import StoryboardGenerator
from app.director.types import ShotPlan, PlannedShot


@pytest.mark.asyncio
async def test_stage_plan_forces_plan_choices_and_fills_dialogue():
    plan = ShotPlan(shots=[
        PlannedShot(purpose="reaction", shot_size="CU", camera_movement="STATIC",
                    lens="85mm", composition="rule_of_thirds", intended_duration=2.0,
                    covers_lines=[], action_beat="eyes widen", light_quality="side"),
        PlannedShot(purpose="dialogue", shot_size="OTS", camera_movement="DOLLY_IN",
                    lens="50mm", composition="over_the_shoulder", intended_duration=4.0,
                    covers_lines=[0], action_beat="a step in", light_quality="side"),
    ])
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    gen.qwen = MagicMock()
    # the LLM tries to "help" by returning MS for both — the stager must OVERRIDE from the plan
    gen.qwen.chat_json = AsyncMock(return_value=[
        {"shot_number": 1, "shot_type": "MS", "action": "she reacts", "dialogue": None,
         "characters_in_frame": ["A"], "subjects": [{"character": "A"}]},
        {"shot_number": 2, "shot_type": "MS", "action": "he presses", "dialogue": "You lied.",
         "characters_in_frame": ["A", "B"], "subjects": [{"character": "B"}]},
    ])
    gen.prompt_template = "staging placeholder"

    scene = {"scene_number": 1, "dialogue": [{"character": "B", "line": "You lied."}]}
    shots = await gen.stage_plan(scene, characters_in_scene=[{"name": "A"}, {"name": "B"}], plan=plan)

    assert [s["shot_type"] for s in shots] == ["CU", "OTS"]          # plan wins, not the LLM's MS
    assert [s["camera_movement"] for s in shots] == ["STATIC", "DOLLY_IN"]
    assert shots[0]["director_json"]["purpose"] == "reaction"
    assert shots[0]["director_json"]["lens"] == "85mm"
    assert shots[0]["director_json"]["light_quality"] == "side"    # scene-wide light carried through
    assert shots[0]["dialogue"] is None                              # non-verbal beat stays silent
    assert shots[1]["dialogue"] == "You lied."                       # covers_lines[0] filled verbatim
    assert shots[1]["director_json"]["intended_duration"] == 4.0


@pytest.mark.asyncio
async def test_stage_plan_raises_on_llm_failure_for_caller_fallback():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(side_effect=RuntimeError("llm down"))
    gen.prompt_template = "x"
    plan = ShotPlan(shots=[PlannedShot("dialogue", "MS", "STATIC", "50mm",
                    "rule_of_thirds", 5.0, [0], "a beat")])
    with pytest.raises(RuntimeError):
        await gen.stage_plan({"scene_number": 1, "dialogue": [{"line": "Hi"}]},
                             characters_in_scene=[], plan=plan)
