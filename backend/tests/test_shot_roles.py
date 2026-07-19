from app.services.shot_roles import classify_shot_role, angle_changed


def test_no_frame_anchor_is_anchor():
    assert classify_shot_role(
        has_frame_anchor=False, has_locked_newcomer=False, is_angle_change=False) == "anchor"


def test_locked_newcomer_is_entrance():
    assert classify_shot_role(
        has_frame_anchor=True, has_locked_newcomer=True, is_angle_change=False) == "entrance"


def test_angle_change_is_reangle():
    assert classify_shot_role(
        has_frame_anchor=True, has_locked_newcomer=False, is_angle_change=True) == "continue_reangle"


def test_default_is_continue_hold():
    assert classify_shot_role(
        has_frame_anchor=True, has_locked_newcomer=False, is_angle_change=False) == "continue_hold"


def test_newcomer_wins_over_angle_change():
    assert classify_shot_role(
        has_frame_anchor=True, has_locked_newcomer=True, is_angle_change=True) == "entrance"


def test_no_anchor_wins_over_everything():
    assert classify_shot_role(
        has_frame_anchor=False, has_locked_newcomer=True, is_angle_change=True) == "anchor"


def test_reverse_angle_flag_is_an_angle_change():
    assert angle_changed("MS", "MS", reverse_angle=True) is True


def test_shot_type_change_is_an_angle_change():
    assert angle_changed("MS", "CU", reverse_angle=False) is True


def test_same_shot_type_no_reverse_is_no_change():
    assert angle_changed("MS", "ms", reverse_angle=False) is False


def test_unknown_shot_types_do_not_crash():
    assert angle_changed(None, None, reverse_angle=False) is False


def test_prev_frame_never_rides_an_angle_change():
    # an angle change is a CUT: seeding the old frame into the new angle made
    # props/cast morph mid-shot (雪球 materialized in her hands on an MS->OTS
    # cut); the VL text handoff carries continuity across cuts instead
    from app.services.shot_roles import prev_frame_may_ride
    base = dict(guarded_on=True, same_scene=True, has_prev_frame=True,
                cast_safe=True)
    assert prev_frame_may_ride(**base, is_angle_change=False) is True
    assert prev_frame_may_ride(**base, is_angle_change=True) is False


def test_prev_frame_needs_every_guard():
    from app.services.shot_roles import prev_frame_may_ride
    for missing in ("guarded_on", "same_scene", "has_prev_frame", "cast_safe"):
        kw = dict(guarded_on=True, same_scene=True, has_prev_frame=True,
                  cast_safe=True, is_angle_change=False)
        kw[missing] = False
        assert prev_frame_may_ride(**kw) is False, missing
