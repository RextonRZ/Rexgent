from app.services.shot_duration_fitter import fit_shot_durations


def _plan(shots):
    return [{"scene_number": 1, "shots": shots}]


def test_long_line_bumps_its_shot_to_the_next_tier():
    # a 7s line cannot fit a 5s shot -> render that shot at 10s
    plan = _plan([
        {"id": "a", "duration": 5, "has_dialogue": True},
        {"id": "b", "duration": 5, "has_dialogue": True},
    ])
    lines = [
        {"scene_number": 1, "line_index": 0, "duration": 7.0},
        {"scene_number": 1, "line_index": 1, "duration": 2.0},
    ]
    changes = fit_shot_durations(plan, lines)
    assert changes == {"a": 10}  # b's 2s line fits its 5s shot — untouched


def test_short_lines_keep_the_small_tier():
    plan = _plan([{"id": "a", "duration": 5, "has_dialogue": True}])
    lines = [{"scene_number": 1, "line_index": 0, "duration": 3.0}]
    assert fit_shot_durations(plan, lines) == {}


def test_oversized_shot_shrinks_back_to_fit():
    # a 10s shot holding a 2s line wastes render money -> back to 5s
    plan = _plan([{"id": "a", "duration": 10, "has_dialogue": True}])
    lines = [{"scene_number": 1, "line_index": 0, "duration": 2.0}]
    assert fit_shot_durations(plan, lines) == {"a": 5}


def test_extra_lines_fold_onto_the_last_speaking_shot():
    # 3 lines, 2 speaking shots: lines 2+3 share shot b, which must hold both
    plan = _plan([
        {"id": "a", "duration": 5, "has_dialogue": True},
        {"id": "b", "duration": 5, "has_dialogue": True},
    ])
    lines = [
        {"scene_number": 1, "line_index": 0, "duration": 2.0},
        {"scene_number": 1, "line_index": 1, "duration": 3.0},
        {"scene_number": 1, "line_index": 2, "duration": 3.0},
    ]
    changes = fit_shot_durations(plan, lines)
    assert changes == {"b": 10}  # 3.0 + 3.0 + gaps > 5s


def test_silent_shots_and_scenes_untouched():
    plan = [
        {"scene_number": 1, "shots": [{"id": "a", "duration": 5, "has_dialogue": False}]},
        {"scene_number": 2, "shots": [{"id": "b", "duration": 5, "has_dialogue": True}]},
    ]
    # scene 2 has no synthesized lines -> nothing to fit
    lines = [{"scene_number": 1, "line_index": 0, "duration": 9.0}]
    assert fit_shot_durations(plan, lines) == {}


def test_line_longer_than_the_top_tier_caps_at_it():
    plan = _plan([{"id": "a", "duration": 5, "has_dialogue": True}])
    lines = [{"scene_number": 1, "line_index": 0, "duration": 14.0}]
    # can't render 15s — cap at the largest tier; placement's no-overlap
    # rule absorbs the spill
    assert fit_shot_durations(plan, lines) == {"a": 10}
