from app.services.stage_map import enforce_scene_sides


def blocking(*subjects, reverse=False):
    return {"subjects": [{"character": c, "screen_side": s} for c, s in subjects],
            "reverse_angle": reverse}


def test_frame_position_drift_snaps_back_without_movement():
    # shot 5 -> 6: the pair stood close, then teleported far apart. Depth
    # (frame_position) now carries like screen sides: it may only change when
    # the subject's own action MOVES them.
    from app.services.stage_map import enforce_scene_sides as ess
    shots = [
        {"subjects": [{"character": "A", "screen_side": "left", "frame_position": "MG"}],
         "reverse_angle": False},
        {"subjects": [{"character": "A", "screen_side": "left", "frame_position": "BG"}],
         "reverse_angle": False},
    ]
    fixed, notes = ess(shots)
    assert fixed[1]["subjects"][0]["frame_position"] == "MG"   # snapped
    assert len(notes) == 1


def test_frame_position_change_with_movement_is_kept():
    from app.services.stage_map import enforce_scene_sides as ess
    shots = [
        {"subjects": [{"character": "A", "screen_side": "left", "frame_position": "BG"}],
         "reverse_angle": False},
        {"subjects": [{"character": "A", "screen_side": "left", "frame_position": "FG",
                       "action": "walking toward camera, closing the distance"}],
         "reverse_angle": False},
    ]
    fixed, notes = ess(shots)
    assert fixed[1]["subjects"][0]["frame_position"] == "FG"   # a real move
    assert notes == []


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


def test_json_stringified_subject_unpacks():
    # production drift: the subject arrives as a JSON object AS A STRING,
    # where the quote between key and colon defeats the marker regex
    from app.services.stage_map import normalize_subjects
    import json
    payload = json.dumps({"character": "CATHERINE", "frame_position": "FG",
                          "screen_side": "left", "posture": "sitting",
                          "eyeline": "at POLICE OFFICER"})
    assert normalize_subjects([payload]) == [{
        "character": "CATHERINE", "frame_position": "FG",
        "screen_side": "left", "posture": "sitting",
        "eyeline": "at POLICE OFFICER"}]
    # and the same JSON trapped inside a dict's character value
    assert normalize_subjects([{"character": payload}]) == [{
        "character": "CATHERINE", "frame_position": "FG",
        "screen_side": "left", "posture": "sitting",
        "eyeline": "at POLICE OFFICER"}]


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


def test_new_pairing_side_collision_re_establishes():
    # the Snowy bug: THEO established screen-left beside MRS. JONES (shot 3),
    # then paired with ANGELINE (shot 5) the storyboard put him right — the
    # snap dragged him back left ON TOP of Angeline. Two subjects cannot share
    # a lateral side in one shot: the fresh pairing wins and re-establishes.
    shots = [blocking(("THEO", "left"), ("MRS. JONES", "right")),
             blocking(("ANGELINE", "left"), ("THEO", "right")),
             blocking(("ANGELINE", "left"), ("THEO", "right"))]
    fixed, notes = enforce_scene_sides(shots)
    s5 = {s["character"]: s["screen_side"] for s in fixed[1]["subjects"]}
    s6 = {s["character"]: s["screen_side"] for s in fixed[2]["subjects"]}
    assert s5 == {"ANGELINE": "left", "THEO": "right"}
    assert s6 == {"ANGELINE": "left", "THEO": "right"}


def test_storyboard_giving_both_the_same_side_still_splits():
    # even a genuinely bad board (both subjects left) must not reach the
    # renderer as two people on one side
    shots = [blocking(("A", "left"), ("B", "left"))]
    fixed, _ = enforce_scene_sides(shots)
    sides = sorted(s["screen_side"] for s in fixed[0]["subjects"])
    assert sides == ["left", "right"]
