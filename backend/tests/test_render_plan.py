from types import SimpleNamespace
from app.services.render_plan import predict_scene_plan


def _shot(n, chars, stype="MS", dialogue="hi", tier="wan", fg=None):
    return SimpleNamespace(number=n, characters_in_frame=chars, shot_type=stype,
                           dialogue=dialogue, quality_tier=tier, blocking_json=None,
                           estimated_duration_seconds=5, id=f"s{n}",
                           foreground_characters=(fg or []))


BIBLE = {"characters": {"A": {"variants": [{"plate_image_url": "a", "is_default": True}]},
                        "B": {"variants": [{"plate_image_url": "b", "is_default": True}]}}}


def test_v2_first_shot_is_happyhorse_anchor():
    shots = [_shot(1, ["A"]), _shot(2, ["A"])]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="happyhorse", anchor_lipsync=False,
                              lipsync_enabled=True)
    assert plan[0]["model"] == "happyhorse"
    assert plan[1]["model"] == "wan"


def test_v2_newcomer_is_happyhorse_entrance():
    shots = [_shot(1, ["A"]), _shot(2, ["A", "B"])]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="happyhorse", anchor_lipsync=False,
                              lipsync_enabled=True)
    assert plan[1]["model"] == "happyhorse"


def test_v2_lipsync_badge_on_single_speaker_continue():
    shots = [_shot(1, ["A"]), _shot(2, ["A"], stype="MS")]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="happyhorse", anchor_lipsync=False,
                              lipsync_enabled=True)
    assert plan[1]["lipsync"] is True


def test_v2_anchor_lipsync_badge_only_when_flag_on():
    shots = [_shot(1, ["A"])]   # anchor, single speaker, has dialogue
    off = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                             anchor_ref_model="happyhorse", anchor_lipsync=False,
                             lipsync_enabled=True)
    on = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                            anchor_ref_model="happyhorse", anchor_lipsync=True,
                            lipsync_enabled=True)
    assert off[0]["lipsync"] is False        # anchor: no badge unless anchor_lipsync on
    assert on[0]["lipsync"] is True


def test_flag_off_uses_quality_tier_label():
    shots = [_shot(1, ["A"], tier="wan"), _shot(2, ["A"], tier="happyhorse")]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=False,
                              anchor_ref_model="happyhorse", anchor_lipsync=False,
                              lipsync_enabled=True)
    assert plan[0]["model"] == "wan" and plan[1]["model"] == "happyhorse"
    assert plan[0]["lipsync"] is False


def test_foreground_only_character_is_not_a_newcomer():
    shots = [_shot(1, ["A"]), _shot(2, ["A", "B"], fg=["B"])]  # B is back-to-camera
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="happyhorse", anchor_lipsync=False,
                              lipsync_enabled=True)
    assert plan[1]["model"] == "wan"       # continue_hold, NOT entrance


def test_lipsync_enabled_false_suppresses_badge():
    shots = [_shot(1, ["A"]), _shot(2, ["A"])]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="happyhorse", anchor_lipsync=False,
                              lipsync_enabled=False)
    assert plan[1]["lipsync"] is False


def test_anchor_ref_model_wan_uses_wan_for_anchors():
    shots = [_shot(1, ["A"])]
    plan = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                              anchor_ref_model="wan", anchor_lipsync=False, lipsync_enabled=True)
    assert plan[0]["model"] == "wan"


def test_wan_on_same_cast_routes_reangle_to_wan():
    # shot 2: same cast as shot 1 but a framing change -> continue_reangle
    shots = [_shot(1, ["A"], stype="MS"), _shot(2, ["A"], stype="OTS")]
    off = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                             anchor_ref_model="happyhorse", anchor_lipsync=False,
                             lipsync_enabled=True)
    on = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                            anchor_ref_model="happyhorse", anchor_lipsync=False,
                            lipsync_enabled=True, wan_on_same_cast=True)
    assert off[1]["model"] == "happyhorse"   # reangle -> HappyHorse by default
    assert on[1]["model"] == "wan"           # same cast -> wan continuation


def test_wan_on_same_cast_still_happyhorse_for_new_character():
    # a NEW character (entrance) must stay HappyHorse even with the flag on
    shots = [_shot(1, ["A"]), _shot(2, ["A", "B"])]
    on = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                            anchor_ref_model="happyhorse", anchor_lipsync=False,
                            lipsync_enabled=True, wan_on_same_cast=True)
    assert on[1]["model"] == "happyhorse"


def test_native_talk_badges_a_multi_person_happyhorse_shot():
    # shot 2: B enters (entrance -> happyhorse), TWO faces visible, has dialogue
    shots = [_shot(1, ["A"]), _shot(2, ["A", "B"])]
    off = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                             anchor_ref_model="happyhorse", anchor_lipsync=False,
                             lipsync_enabled=True)
    on = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                            anchor_ref_model="happyhorse", anchor_lipsync=False,
                            lipsync_enabled=True, happyhorse_native_talk=True)
    assert on[1]["model"] == "happyhorse"
    assert off[1]["lipsync"] is False   # 2 faces, no native talk -> no lip badge
    assert on[1]["lipsync"] is True     # native talk -> talks even with 2 faces


def test_continuation_routes_to_happyhorse_when_flagged():
    shots = [_shot(1, ["A"]), _shot(2, ["A"])]   # shot 2 = continue_hold (same cast, same framing)
    off = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                             anchor_ref_model="happyhorse", anchor_lipsync=False, lipsync_enabled=True)
    on = predict_scene_plan(shots, BIBLE, identity_routing_v2=True,
                            anchor_ref_model="happyhorse", anchor_lipsync=False, lipsync_enabled=True,
                            route_continuation_to_happyhorse=True)
    assert off[1]["model"] == "wan"
    assert on[1]["model"] == "happyhorse"
