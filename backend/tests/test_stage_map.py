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


# ── held-object continuity: a carried prop threads across the scene's shots ──

def test_held_object_carries_forward_when_a_shot_omits_it():
    # the birdcage bug: Angeline holds a cage in shot 1, the board omits it in
    # shot 2, and the render dropped it. Held objects thread forward like sides.
    from app.services.stage_map import thread_held_objects
    shots = [
        {"subjects": [{"character": "ANGELINE", "holding": "a birdcage"}],
         "reverse_angle": False},
        {"subjects": [{"character": "ANGELINE"}], "reverse_angle": False},
    ]
    fixed, notes = thread_held_objects(shots)
    assert fixed[1]["subjects"][0]["holding"] == "a birdcage"
    assert len(notes) == 1


def test_new_held_object_overrides_the_carried_one():
    # picking up something new replaces what was carried, and that carries on
    from app.services.stage_map import thread_held_objects
    shots = [
        {"subjects": [{"character": "LUCAS", "holding": "a soccer ball"}]},
        {"subjects": [{"character": "LUCAS", "holding": "a letter"}]},
        {"subjects": [{"character": "LUCAS"}]},
    ]
    fixed, _ = thread_held_objects(shots)
    assert fixed[2]["subjects"][0]["holding"] == "a letter"


def test_held_object_stops_when_set_down():
    # a visible release (sets it down / hands it off) stops the thread
    from app.services.stage_map import thread_held_objects
    shots = [
        {"subjects": [{"character": "ANGELINE", "holding": "a birdcage"}]},
        {"subjects": [{"character": "ANGELINE",
                       "action": "sets the cage down on the table"}]},
        {"subjects": [{"character": "ANGELINE"}]},
    ]
    fixed, _ = thread_held_objects(shots)
    assert "holding" not in fixed[1]["subjects"][0]        # released this shot
    assert fixed[2]["subjects"][0].get("holding") is None  # stays released


def test_empty_hands_are_never_threaded():
    from app.services.stage_map import thread_held_objects
    shots = [
        {"subjects": [{"character": "MIA"}]},
        {"subjects": [{"character": "MIA"}]},
    ]
    fixed, notes = thread_held_objects(shots)
    assert "holding" not in fixed[1]["subjects"][0]
    assert notes == []


def test_thread_held_objects_skips_blockless_shots():
    from app.services.stage_map import thread_held_objects
    shots = [None,
             {"subjects": [{"character": "A", "holding": "a lantern"}]},
             None,
             {"subjects": [{"character": "A"}]}]
    fixed, _ = thread_held_objects(shots)
    assert fixed[3]["subjects"][0]["holding"] == "a lantern"


# ── proximity: you cannot walk toward someone you are already with ──────────

def test_approach_to_established_partner_is_rewritten():
    # the scene-2 bug: shot 2 has them standing together talking, shot 3's
    # board wrote "Angeline walks to Leo" — a teleport-reset the depth
    # enforcer allowed because the action claimed movement
    from app.services.stage_map import enforce_proximity
    shots = [
        {"subjects": [{"character": "ANGELINE"}, {"character": "LEO"}],
         "action": "They stand facing each other, talking."},
        {"subjects": [{"character": "ANGELINE", "action": "walks over to Leo, reaching out"},
                      {"character": "LEO"}],
         "action": "Angeline walks over to Leo, reaching out."},
    ]
    fixed, notes = enforce_proximity(shots)
    assert fixed[1]["subjects"][0]["action"] == "stands with Leo, reaching out"
    assert fixed[1]["action"] == "Angeline stands with Leo, reaching out."
    assert len(notes) >= 1


def test_first_approach_is_left_alone():
    # not yet together: the approach is real staging and survives
    from app.services.stage_map import enforce_proximity
    shots = [
        {"subjects": [{"character": "ANGELINE"}],
         "action": "Angeline stands alone by the fence."},
        {"subjects": [{"character": "ANGELINE", "action": "walks toward Leo"},
                      {"character": "LEO"}],
         "action": "Angeline walks toward Leo."},
    ]
    fixed, notes = enforce_proximity(shots)
    assert fixed[1]["action"] == "Angeline walks toward Leo."
    assert notes == []


def test_separation_resets_proximity():
    # stepping away breaks the pair: a later approach is legitimate again
    from app.services.stage_map import enforce_proximity
    shots = [
        {"subjects": [{"character": "A"}, {"character": "B"}], "action": "They talk."},
        {"subjects": [{"character": "A", "action": "turns and walks away from B"}],
         "action": "A turns and walks away from B."},
        {"subjects": [{"character": "A", "action": "walks back to B"},
                      {"character": "B"}],
         "action": "A walks back to B."},
    ]
    fixed, notes = enforce_proximity(shots)
    assert fixed[2]["action"] == "A walks back to B."
    assert notes == []


def test_proximity_skips_blockless_shots():
    from app.services.stage_map import enforce_proximity
    shots = [None,
             {"subjects": [{"character": "A"}, {"character": "B"}], "action": "They talk."},
             None,
             {"subjects": [{"character": "A", "action": "runs to B"}, {"character": "B"}],
              "action": "A runs to B."}]
    fixed, notes = enforce_proximity(shots)
    assert "stands with B" in fixed[3]["action"]
    assert len(notes) >= 1
