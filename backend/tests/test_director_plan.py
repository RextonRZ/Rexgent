# backend/tests/test_director_plan.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.director.director import plan_scene
from app.director.recommender import recommend_look


def _qwen(plan):
    q = MagicMock()
    q.chat_json = AsyncMock(return_value=plan)
    return q


@pytest.mark.asyncio
async def test_plan_scene_covers_all_lines_and_varies():
    scene = {"scene_number": 1, "description": "a tense standoff",
             "dialogue": [{"character": "A", "line": "Stop."}, {"character": "B", "line": "No."}]}
    plan = [
        {"purpose": "establishing", "shot_size": "EWS", "camera_movement": "PAN_LEFT",
         "lens": "24mm", "composition": "leading_lines", "intended_duration": 3.0,
         "covers_lines": [], "action_beat": "wind moves the dust"},
        {"purpose": "dialogue", "shot_size": "MS", "camera_movement": "STATIC",
         "lens": "50mm", "composition": "rule_of_thirds", "intended_duration": 4.0,
         "covers_lines": [0], "action_beat": "a step forward"},
        {"purpose": "dialogue", "shot_size": "OTS", "camera_movement": "DOLLY_IN",
         "lens": "50mm", "composition": "over_the_shoulder", "intended_duration": 4.0,
         "covers_lines": [1], "action_beat": "a slow shake of the head"},
    ]
    out = await plan_scene(scene, cast=[{"name": "A"}, {"name": "B"}],
                           look=recommend_look("thriller"), budget=4, qwen=_qwen(plan))
    covered = sorted(i for s in out.shots for i in s.covers_lines)
    assert covered == [0, 1]
    assert len(out.shots) <= 4
    # scene-wide light quality flows from the look onto every shot
    assert all(s.light_quality == "side" for s in out.shots)
    # scene-wide stylization flows the same way (thriller -> noir)
    assert all(s.stylization == "noir" for s in out.shots)


@pytest.mark.asyncio
async def test_plan_scene_honors_valid_special_effect_and_drops_invalid():
    scene = {"scene_number": 1, "description": "a quiet street at dawn",
             "dialogue": [{"character": "A", "line": "It's over."}]}
    plan = [
        {"purpose": "establishing", "shot_size": "EWS", "camera_movement": "DRONE",
         "lens": "24mm", "composition": "leading_lines", "intended_duration": 3.0,
         "covers_lines": [], "action_beat": "light creeps over rooftops",
         "special_effect": "time_lapse"},
        {"purpose": "insert", "shot_size": "INSERT", "camera_movement": "STATIC",
         "lens": "85mm", "composition": "centered", "intended_duration": 2.0,
         "covers_lines": [], "action_beat": "a hand on a rail",
         "special_effect": "not_a_real_effect"},
        {"purpose": "dialogue", "shot_size": "MS", "camera_movement": "STATIC",
         "lens": "50mm", "composition": "rule_of_thirds", "intended_duration": 4.0,
         "covers_lines": [0], "action_beat": "a slow exhale"},
    ]
    out = await plan_scene(scene, cast=[{"name": "A"}], look=recommend_look("drama"),
                           budget=5, qwen=_qwen(plan))
    by_purpose = {s.purpose: s for s in out.shots}
    assert by_purpose["establishing"].special_effect == "time_lapse"   # valid term honored
    assert by_purpose["insert"].special_effect is None                 # invalid term dropped
    assert by_purpose["dialogue"].special_effect is None               # default None


@pytest.mark.asyncio
async def test_plan_scene_falls_back_to_empty_plan_on_bad_json():
    scene = {"scene_number": 1, "dialogue": [{"character": "A", "line": "Hi."}]}
    q = MagicMock(); q.chat_json = AsyncMock(return_value={"not": "a list"})
    out = await plan_scene(scene, cast=[{"name": "A"}], look=recommend_look(None),
                           budget=3, qwen=q)
    # bad output -> coverage guard still guarantees the line is boarded
    assert sorted(i for s in out.shots for i in s.covers_lines) == [0]
