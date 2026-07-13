from app.services.shot_roles import classify_shot_role, angle_changed


def test_no_frame_anchor_is_anchor():
    assert classify_shot_role(
        has_frame_anchor=False, has_locked_newcomer=False, angle_changed=False) == "anchor"


def test_locked_newcomer_is_entrance():
    assert classify_shot_role(
        has_frame_anchor=True, has_locked_newcomer=True, angle_changed=False) == "entrance"


def test_angle_change_is_reangle():
    assert classify_shot_role(
        has_frame_anchor=True, has_locked_newcomer=False, angle_changed=True) == "continue_reangle"


def test_default_is_continue_hold():
    assert classify_shot_role(
        has_frame_anchor=True, has_locked_newcomer=False, angle_changed=False) == "continue_hold"


def test_newcomer_wins_over_angle_change():
    assert classify_shot_role(
        has_frame_anchor=True, has_locked_newcomer=True, angle_changed=True) == "entrance"


def test_reverse_angle_flag_is_an_angle_change():
    assert angle_changed("MS", "MS", reverse_angle=True) is True


def test_shot_type_change_is_an_angle_change():
    assert angle_changed("MS", "CU", reverse_angle=False) is True


def test_same_shot_type_no_reverse_is_no_change():
    assert angle_changed("MS", "ms", reverse_angle=False) is False


def test_unknown_shot_types_do_not_crash():
    assert angle_changed(None, None, reverse_angle=False) is False
