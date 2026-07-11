from app.services.stage_map import enforce_scene_sides


def blocking(*subjects, reverse=False):
    return {"subjects": [{"character": c, "screen_side": s} for c, s in subjects],
            "reverse_angle": reverse}


def test_first_placement_establishes_the_side():
    shots = [blocking(("SOL", "right"), ("FIGURE", "left")),
             blocking(("SOL", "right"), ("FIGURE", "left"))]
    _, notes = enforce_scene_sides(shots)
    assert notes == []


def test_drift_is_snapped_back():
    # the verified bug: consecutive shots flipped who is left and who is right
    shots = [blocking(("SOL", "right"), ("FIGURE", "left")),
             blocking(("SOL", "left"), ("FIGURE", "right"))]
    fixed, notes = enforce_scene_sides(shots)
    assert fixed[1]["subjects"][0]["screen_side"] == "right"
    assert fixed[1]["subjects"][1]["screen_side"] == "left"
    assert len(notes) == 2


def test_center_is_neutral():
    # a dolly-in single putting someone center is not a violation, and does
    # not re-establish their side
    shots = [blocking(("SOL", "right")),
             blocking(("SOL", "center")),
             blocking(("SOL", "left"))]
    fixed, notes = enforce_scene_sides(shots)
    assert fixed[1]["subjects"][0]["screen_side"] == "center"
    assert fixed[2]["subjects"][0]["screen_side"] == "right"  # snapped
    assert len(notes) == 1


def test_reverse_angle_re_establishes_everyone():
    shots = [blocking(("SOL", "right"), ("FIGURE", "left")),
             blocking(("SOL", "left"), ("FIGURE", "right"), reverse=True),
             blocking(("SOL", "left"), ("FIGURE", "right"))]
    _, notes = enforce_scene_sides(shots)
    assert notes == []  # deliberate reverse, then consistent with the NEW line


def test_shots_without_blocking_pass_through():
    shots = [None, blocking(("SOL", "right")), None, blocking(("SOL", "right"))]
    _, notes = enforce_scene_sides(shots)
    assert notes == []
