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


def test_string_subjects_do_not_crash_the_enforcer():
    # the live crash: the model returned subjects as bare name strings
    shots = [{"subjects": ["IM SOL", "RYU SUN-JAE"], "reverse_angle": False},
             blocking(("IM SOL", "left"))]
    _, notes = enforce_scene_sides(shots)
    assert notes == []


def test_flattened_subject_string_unpacks_to_fields():
    from app.services.stage_map import normalize_subjects
    subs = normalize_subjects([
        "character_name: IM SOL, frame_position: FG, screen_side: left, "
        "facing: screen-right, eyeline: at DOCTOR, action: standing still, looking down"
    ])
    assert subs == [{
        "character": "IM SOL",
        "frame_position": "FG",
        "screen_side": "left",
        "facing": "screen-right",
        "eyeline": "at DOCTOR",
        "action": "standing still, looking down",
    }]


def test_flattened_subject_with_posture_key():
    from app.services.stage_map import normalize_subjects
    subs = normalize_subjects([
        "character_name: RYU SUN-JAE, frame_position: BG, posture: lying, "
        "action: lying unconscious on the bed"
    ])
    assert subs == [{"character": "RYU SUN-JAE", "frame_position": "BG",
                     "posture": "lying",
                     "action": "lying unconscious on the bed"}]


def test_flattened_subject_with_bare_leading_name():
    from app.services.stage_map import normalize_subjects
    subs = normalize_subjects(["IM SOL, frame_position: MG, screen_side: right"])
    assert subs == [{"character": "IM SOL", "frame_position": "MG",
                     "screen_side": "right"}]


def test_dict_with_geometry_trapped_in_character_value_is_repaired():
    from app.services.stage_map import normalize_subjects
    subs = normalize_subjects([
        {"character": "character_name: NURSE, screen_side: left, facing: screen-right"}
    ])
    assert subs == [{"character": "NURSE", "screen_side": "left",
                     "facing": "screen-right"}]


def test_structured_dicts_and_plain_names_stay_untouched():
    from app.services.stage_map import normalize_subjects
    subs = normalize_subjects([
        {"character": "IM SOL", "screen_side": "left"},
        "DOCTOR",
    ])
    assert subs == [{"character": "IM SOL", "screen_side": "left"},
                    {"character": "DOCTOR"}]


def test_normalize_subjects_coerces_and_filters():
    from app.services.stage_map import normalize_subjects
    assert normalize_subjects(["IM SOL", {"character": "RYU", "screen_side": "left"},
                               42, "  "]) == [
        {"character": "IM SOL"},
        {"character": "RYU", "screen_side": "left"},
    ]
    assert normalize_subjects("IM SOL") is None
    assert normalize_subjects([]) is None
    assert normalize_subjects(None) is None
