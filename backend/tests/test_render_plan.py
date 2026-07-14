from types import SimpleNamespace
from app.services.render_plan import predict_scene_plan


def _shot(n, chars, stype="MS", dialogue="hi", tier="wan"):
    return SimpleNamespace(number=n, characters_in_frame=chars, shot_type=stype,
                           dialogue=dialogue, quality_tier=tier, blocking_json=None,
                           estimated_duration_seconds=5, id=f"s{n}")


BIBLE = {"characters": {"A": {"variants": [{"plate_image_url": "a", "is_default": True}]},
                        "B": {"variants": [{"plate_image_url": "b", "is_default": True}]}}}


def test_v2_first_shot_is_happyhorse_anchor():
    shots = [_shot(1, ["A"]), _shot(2, ["A"])]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="happyhorse", anchor_lipsync=False)
    assert plan[0]["model"] == "happyhorse"
    assert plan[1]["model"] == "wan"


def test_v2_newcomer_is_happyhorse_entrance():
    shots = [_shot(1, ["A"]), _shot(2, ["A", "B"])]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="happyhorse", anchor_lipsync=False)
    assert plan[1]["model"] == "happyhorse"


def test_v2_lipsync_badge_on_single_speaker_continue():
    shots = [_shot(1, ["A"]), _shot(2, ["A"], stype="MS")]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="happyhorse", anchor_lipsync=False)
    assert plan[1]["lipsync"] is True


def test_v2_anchor_lipsync_badge_only_when_flag_on():
    shots = [_shot(1, ["A"])]   # anchor, single speaker, has dialogue
    off = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                             anchor_ref_model="happyhorse", anchor_lipsync=False)
    on = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                            anchor_ref_model="happyhorse", anchor_lipsync=True)
    assert off[0]["lipsync"] is False        # anchor: no badge unless anchor_lipsync on
    assert on[0]["lipsync"] is True


def test_flag_off_uses_quality_tier_label():
    shots = [_shot(1, ["A"], tier="wan"), _shot(2, ["A"], tier="happyhorse")]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=False,
                              anchor_ref_model="happyhorse", anchor_lipsync=False)
    assert plan[0]["model"] == "wan" and plan[1]["model"] == "happyhorse"
    assert plan[0]["lipsync"] is False
