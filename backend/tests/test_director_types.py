from app.director.types import PlannedShot, ShotPlan, LookProfile


def test_planned_shot_construct_and_defaults():
    ps = PlannedShot(purpose="reaction", shot_size="CU", camera_movement="STATIC",
                     lens="85mm", composition="rule_of_thirds", intended_duration=2.0,
                     covers_lines=[], action_beat="a slow, held glance")
    assert ps.blocking_delta is None and ps.transition_in is None
    assert ps.light_quality == "soft"


def test_shot_plan_and_look_profile():
    plan = ShotPlan(shots=[])
    assert plan.shots == []
    look = LookProfile(lighting="NATURAL", colour_mood="WARM", lens_bias="50mm",
                       camera_pace="slow")
    assert look.bgm_hint is None
    assert look.light_quality == "soft"
