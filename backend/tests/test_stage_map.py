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


# ── Chinese verb coverage: the zh drama's actions were invisible to every ────
# ── verb regex, so proximity resets, moves and exits all slipped through ─────

def test_zh_approach_to_established_partner_is_rewritten():
    # scene 2: shot 1 stages 安吉琳+玛丽 together; shot 2's "玛丽向安吉琳走去"
    # is a teleport-reset — the prev frame already shows them side by side, so
    # the render spawned a SECOND 玛丽 walking in. Must rewrite like the
    # English pass does.
    from app.services.stage_map import enforce_proximity
    shots = [
        {"action": "安吉琳和玛丽站在花园外。",
         "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
        {"action": "玛丽向安吉琳走去，安慰她。",
         "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
    ]
    _, notes = enforce_proximity(shots)
    assert notes, "zh approach toward an established partner must be rewritten"
    assert "走去" not in shots[1]["action"]
    assert "站在安吉琳身旁" in shots[1]["action"]


def test_zh_approach_verb_variants_are_rewritten():
    from app.services.stage_map import enforce_proximity
    for phrase in ("玛丽走向安吉琳", "玛丽朝安吉琳跑来", "玛丽靠近安吉琳"):
        shots = [
            {"action": "两人并肩而立。",
             "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
            {"action": phrase,
             "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
        ]
        _, notes = enforce_proximity(shots)
        assert notes, phrase


def test_zh_turn_toward_is_not_an_approach():
    # 转向玛丽 (turns toward) is legitimate staging, not a walk-over reset
    from app.services.stage_map import enforce_proximity
    shots = [
        {"action": "安吉琳和玛丽站在一起。",
         "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
        {"action": "安吉琳转向玛丽，手指着前方。",
         "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
    ]
    _, notes = enforce_proximity(shots)
    assert notes == []
    assert shots[1]["action"] == "安吉琳转向玛丽，手指着前方。"


def test_zh_separation_breaks_the_pair():
    # after 玛丽转身离开, a fresh approach is legitimate staging again
    from app.services.stage_map import enforce_proximity
    shots = [
        {"action": "两人站在一起。",
         "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
        {"action": "玛丽转身离开了花园。",
         "subjects": [{"character": "玛丽"}]},
        {"action": "玛丽走向安吉琳。",
         "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
    ]
    _, notes = enforce_proximity(shots)
    assert notes == []
    assert "走向" in shots[2]["action"]


def test_zh_movement_allows_depth_change():
    # 翻过栅栏 is real movement — the depth change must be KEPT, not snapped
    from app.services.stage_map import enforce_scene_sides as ess
    shots = [
        {"subjects": [{"character": "安吉琳", "screen_side": "left",
                       "frame_position": "MG"}], "reverse_angle": False},
        {"subjects": [{"character": "安吉琳", "screen_side": "left",
                       "frame_position": "BG",
                       "action": "安吉琳翻过栅栏，走进花园"}],
         "reverse_angle": False},
    ]
    fixed, notes = ess(shots)
    assert fixed[1]["subjects"][0]["frame_position"] == "BG"
    assert notes == []


def test_zh_release_stops_held_threading():
    from app.services.stage_map import thread_held_objects
    shots = [
        {"subjects": [{"character": "安吉琳", "holding": "一个鸟笼"}]},
        {"subjects": [{"character": "安吉琳", "action": "安吉琳把鸟笼放下"}]},
        {"subjects": [{"character": "安吉琳"}]},
    ]
    _, notes = thread_held_objects(shots)
    assert shots[1]["subjects"][0].get("holding") is None
    assert shots[2]["subjects"][0].get("holding") is None


# ── barrier depth: a character SEEN THROUGH a fence/window is on its far ─────
# ── side, staged deep background — never beside the onlookers ────────────────

def test_seen_through_barrier_stages_far_background():
    # 安吉琳透过栅栏看到雪球 — 雪球 rendered BESIDE the two women instead of
    # beyond the fence: nothing carried the far-side depth into blocking
    from app.services.stage_map import enforce_barrier_depth
    shots = [{
        "action": "安吉琳透过栅栏看到雪球被拴在树旁，她的眼睛瞪大了。",
        "subjects": [
            {"character": "安吉琳", "frame_position": "MG", "screen_side": "left"},
            {"character": "雪球", "frame_position": "MG", "screen_side": "right"},
        ]}]
    _, notes = enforce_barrier_depth(shots)
    pos = shots[0]["subjects"][1]["frame_position"]
    assert "far background" in pos and "栅栏" in pos
    assert shots[0]["subjects"][0]["frame_position"] == "MG"   # onlooker untouched
    assert notes


def test_barrier_depth_threads_until_a_crossing():
    # the far-side placement persists into later shots of the scene (shot 2
    # still shows 雪球 beyond the fence) until someone crosses (翻过栅栏)
    from app.services.stage_map import enforce_barrier_depth
    shots = [
        {"action": "安吉琳透过栅栏看到雪球。",
         "subjects": [{"character": "安吉琳", "frame_position": "MG"},
                      {"character": "雪球", "frame_position": "MG"}]},
        {"action": "安吉琳转向玛丽，手指着雪球。",
         "subjects": [{"character": "安吉琳", "frame_position": "MG"},
                      {"character": "雪球", "frame_position": "MG"}]},
        {"action": "安吉琳翻过栅栏，跑向雪球。",
         "subjects": [{"character": "安吉琳", "frame_position": "MG"},
                      {"character": "雪球", "frame_position": "MG"}]},
    ]
    _, _ = enforce_barrier_depth(shots)
    assert "far background" in shots[1]["subjects"][1]["frame_position"]
    # after the crossing the barrier no longer separates them
    assert shots[2]["subjects"][1]["frame_position"] == "MG"


def test_english_seen_through_barrier_also_stages_far_background():
    from app.services.stage_map import enforce_barrier_depth
    shots = [{
        "action": "Angeline sees Snowy through the fence, tied to a tree.",
        "subjects": [
            {"character": "Angeline", "frame_position": "MG"},
            {"character": "Snowy", "frame_position": "MG"},
        ]}]
    _, notes = enforce_barrier_depth(shots)
    pos = shots[0]["subjects"][1]["frame_position"]
    assert "far background" in pos and "fence" in pos
    assert notes


def test_barrier_separated_pair_may_still_approach_after_crossing():
    # sharing a frame ACROSS the fence is not togetherness: after 安吉琳
    # climbs over, her 跑向雪球 is legitimate staging, never a teleport-reset
    from app.services.stage_map import enforce_barrier_depth, enforce_proximity
    shots = [
        {"action": "安吉琳透过栅栏看到雪球被拴在树旁。",
         "subjects": [{"character": "安吉琳", "frame_position": "MG"},
                      {"character": "雪球", "frame_position": "MG"}]},
        {"action": "安吉琳翻过栅栏，跑向雪球。",
         "subjects": [{"character": "安吉琳", "frame_position": "MG"},
                      {"character": "雪球", "frame_position": "MG"}]},
    ]
    _, _ = enforce_barrier_depth(shots)
    _, notes = enforce_proximity(shots)
    assert notes == []
    assert "跑向雪球" in shots[1]["action"]


# ── tether: a pet tied to something stays tied, and the tie reaches blocking ─

def test_tethered_pet_threads_until_picked_up():
    # 雪球被拴在树旁 rendered with the rope lying unattached and the collar
    # flickering: the tie lived only in one shot's prose. Thread it like held
    # props so every shot's blocking states the leash, until a release.
    from app.services.stage_map import thread_tethered
    shots = [
        {"action": "雪球被拴在树旁，项圈连着一根麻绳。",
         "subjects": [{"character": "雪球"}, {"character": "安吉琳"}]},
        {"action": "安吉琳隔着栅栏看着雪球。",
         "subjects": [{"character": "雪球"}, {"character": "安吉琳"}]},
        {"action": "安吉琳抱起雪球，紧紧搂在怀里。",
         "subjects": [{"character": "雪球"}, {"character": "安吉琳"}]},
    ]
    _, notes = thread_tethered(shots)
    assert "树旁" in (shots[0]["subjects"][0].get("tethered") or "")
    assert shots[1]["subjects"][0].get("tethered")          # threads forward
    assert not shots[2]["subjects"][0].get("tethered")      # picked up -> free
    assert shots[0]["subjects"][1].get("tethered") is None  # others untouched
    assert notes


def test_tethered_english_form_works_too():
    from app.services.stage_map import thread_tethered
    shots = [{"action": "Snowy is tied to the tree by a worn rope.",
              "subjects": [{"character": "Snowy"}]}]
    _, _ = thread_tethered(shots)
    assert "tree" in (shots[0]["subjects"][0].get("tethered") or "")


# ── restated contact: a grab already made must not be re-performed ───────────

def test_restated_grab_becomes_still_holding():
    # shot 3 grabbed the arm; shot 4 restated 抓住 as a fresh action, so the
    # render replayed the grab with an awkward re-approach
    from app.services.stage_map import continue_restated_contact
    shots = [
        {"action": "玛丽慌张地抓住安吉琳的手臂，阻止她进入花园。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
        {"action": "玛丽绝望地喊叫，手紧紧抓住安吉琳的手臂。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
    ]
    _, notes = continue_restated_contact(shots)
    assert "抓住安吉琳" not in shots[1]["action"]
    assert "抓着安吉琳" in shots[1]["action"]
    assert "仍" in shots[1]["action"]
    assert notes


def test_released_grip_may_grab_again():
    from app.services.stage_map import continue_restated_contact
    shots = [
        {"action": "玛丽抓住安吉琳的手臂。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
        {"action": "玛丽松开了手，退后一步。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
        {"action": "玛丽再次抓住安吉琳的手臂。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
    ]
    _, notes = continue_restated_contact(shots)
    assert "抓住安吉琳" in shots[2]["action"]   # legitimate fresh grab
    assert notes == []


def test_first_grab_is_never_rewritten():
    from app.services.stage_map import continue_restated_contact
    shots = [{"action": "玛丽一把抓住安吉琳的手腕。",
              "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]}]
    _, notes = continue_restated_contact(shots)
    assert "抓住" in shots[0]["action"]
    assert notes == []


# ── world anchors: camera blocking says MG-right, which is satisfied both ────
# ── inside and outside the fence — the WORLD position must thread too ────────

def test_anchor_establishes_and_threads():
    from app.services.stage_map import thread_anchors
    shots = [
        {"action": "玛丽站在花园外，脸色苍白。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
        {"action": "玛丽绝望地喊叫。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
    ]
    _, notes = thread_anchors(shots)
    assert shots[0]["subjects"][0].get("anchor") == "花园外"
    assert shots[1]["subjects"][0].get("anchor") == "花园外"   # threads
    assert shots[0]["subjects"][1].get("anchor") is None        # unplaced stays free
    assert notes


def test_anchor_moves_with_movement_verbs():
    from app.services.stage_map import thread_anchors
    shots = [
        {"action": "安吉琳站在栅栏旁。", "subjects": [{"character": "安吉琳"}]},
        {"action": "安吉琳跑到大树下，蹲下身。", "subjects": [{"character": "安吉琳"}]},
        {"action": "安吉琳低头不语。", "subjects": [{"character": "安吉琳"}]},
    ]
    _, _ = thread_anchors(shots)
    assert shots[0]["subjects"][0]["anchor"] == "栅栏旁"
    assert shots[1]["subjects"][0]["anchor"] == "大树下"
    assert shots[2]["subjects"][0]["anchor"] == "大树下"


def test_anchor_english_forms():
    from app.services.stage_map import thread_anchors
    shots = [
        {"action": "Mary stands outside the fence, pale.",
         "subjects": [{"character": "Mary"}]},
        {"action": "Mary shouts desperately.",
         "subjects": [{"character": "Mary"}]},
        {"action": "Mary walks to the gate.",
         "subjects": [{"character": "Mary"}]},
    ]
    _, _ = thread_anchors(shots)
    assert "fence" in shots[0]["subjects"][0]["anchor"]
    assert "fence" in shots[1]["subjects"][0]["anchor"]
    assert "gate" in shots[2]["subjects"][0]["anchor"]


def test_anchor_never_crosses_into_another_characters_clause():
    # "玛丽问安吉琳站在花园外做什么" anchored BOTH at the garbage place
    # "花园外做什么" — the gap must not span another subject's name, and a
    # capture containing a question word is not a place
    from app.services.stage_map import thread_anchors
    shots = [{"action": "玛丽问安吉琳站在花园外做什么。",
              "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]}]
    _, _ = thread_anchors(shots)
    assert shots[0]["subjects"][0].get("anchor") is None
    assert shots[0]["subjects"][1].get("anchor") is None


def test_anchor_ignores_non_places_and_person_anchors():
    from app.services.stage_map import thread_anchors
    shots = [
        {"action": "玛丽和安吉琳站在一起。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
        {"action": "玛丽站在安吉琳身旁，紧紧抱住她。",
         "subjects": [{"character": "玛丽"}, {"character": "安吉琳"}]},
    ]
    _, _ = thread_anchors(shots)
    assert shots[0]["subjects"][0].get("anchor") is None   # 一起 is not a place
    assert shots[1]["subjects"][0].get("anchor") is None   # a person is not a landmark


def test_departure_clears_the_anchor():
    from app.services.stage_map import thread_anchors
    shots = [
        {"action": "玛丽站在花园外。", "subjects": [{"character": "玛丽"}]},
        {"action": "玛丽转身离开，走向大门。", "subjects": [{"character": "玛丽"}]},
        {"action": "玛丽低头不语。", "subjects": [{"character": "玛丽"}]},
    ]
    _, _ = thread_anchors(shots)
    assert shots[0]["subjects"][0]["anchor"] == "花园外"
    assert shots[1]["subjects"][0].get("anchor") is None
    assert shots[2]["subjects"][0].get("anchor") is None


def test_english_departure_clears_too():
    from app.services.stage_map import thread_anchors
    shots = [
        {"action": "Mary stands by the gate.", "subjects": [{"character": "Mary"}]},
        {"action": "Mary storms off angrily.", "subjects": [{"character": "Mary"}]},
    ]
    _, _ = thread_anchors(shots)
    assert "gate" in shots[0]["subjects"][0]["anchor"]
    assert shots[1]["subjects"][0].get("anchor") is None


# ── framing visibility: who can PHYSICALLY be in this framing ────────────────

def test_far_side_character_dropped_from_tight_framings():
    # 雪球 staged beyond the fence was listed in an MCU of 安吉琳 — its plate
    # rode and the model pasted it in close. Out of the framing's field: drop.
    from app.services.stage_map import filter_frame_by_framing
    shots = [{
        "shot_type": "MCU", "dialogue": None,
        "characters_in_frame": ["安吉琳", "雪球"],
        "subjects": [
            {"character": "安吉琳", "frame_position": "MG"},
            {"character": "雪球",
             "frame_position": "far background, on the far side of the 栅栏, seen through it"},
        ]}]
    _, notes = filter_frame_by_framing(shots)
    assert shots[0]["characters_in_frame"] == ["安吉琳"]
    assert [s["character"] for s in shots[0]["subjects"]] == ["安吉琳"]
    assert notes


def test_bg_dropped_from_cu_but_kept_in_mcu():
    from app.services.stage_map import filter_frame_by_framing
    cu = [{"shot_type": "CU", "dialogue": None,
           "characters_in_frame": ["A", "B"],
           "subjects": [{"character": "A", "frame_position": "FG"},
                        {"character": "B", "frame_position": "BG"}]}]
    _, _ = filter_frame_by_framing(cu)
    assert cu[0]["characters_in_frame"] == ["A"]
    mcu = [{"shot_type": "MCU", "dialogue": None,
            "characters_in_frame": ["A", "B"],
            "subjects": [{"character": "A", "frame_position": "FG"},
                         {"character": "B", "frame_position": "BG"}]}]
    _, _ = filter_frame_by_framing(mcu)
    assert mcu[0]["characters_in_frame"] == ["A", "B"]   # plain BG reads in an MCU


def test_speaker_and_foreground_are_never_dropped():
    from app.services.stage_map import filter_frame_by_framing
    shots = [{
        "shot_type": "CU", "dialogue": "那是雪球！",
        "characters_in_frame": ["安吉琳", "玛丽"],
        "foreground_characters": ["玛丽"],
        "subjects": [{"character": "安吉琳", "frame_position": "BG"},
                     {"character": "玛丽", "frame_position": "FG"}]}]
    lines = [{"character": "安吉琳", "line": "那是雪球！"}]
    _, _ = filter_frame_by_framing(shots, dialogue_lines=lines)
    assert "安吉琳" in shots[0]["characters_in_frame"]   # the speaker stays
    assert "玛丽" in shots[0]["characters_in_frame"]     # the OTS shoulder stays


def test_insert_narrows_to_action_named_cast():
    # the scene-2 INSERT carried three cast for a two-hand detail shot
    from app.services.stage_map import filter_frame_by_framing
    shots = [{
        "shot_type": "INSERT", "dialogue": None,
        "action": "安吉琳抱起雪球，眼中满是失望。",
        "characters_in_frame": ["安吉琳", "雪球", "玛丽"],
        "subjects": [{"character": "安吉琳"}, {"character": "雪球"},
                     {"character": "玛丽"}]}]
    _, notes = filter_frame_by_framing(shots)
    assert shots[0]["characters_in_frame"] == ["安吉琳", "雪球"]
    assert notes


def test_wide_framings_untouched():
    from app.services.stage_map import filter_frame_by_framing
    shots = [{"shot_type": "MS", "dialogue": None,
              "characters_in_frame": ["A", "B"],
              "subjects": [{"character": "A", "frame_position": "FG"},
                           {"character": "B", "frame_position": "BG"}]}]
    _, notes = filter_frame_by_framing(shots)
    assert shots[0]["characters_in_frame"] == ["A", "B"]
    assert notes == []


# ── absence: a name mentioned because the character is GONE is not on screen ─

def test_absent_mention_is_not_a_visible_presence():
    from app.services.stage_map import mention_is_absent
    a = "安吉琳坐在地板上，抱着空兔笼，哽咽着告诉母亲雪球不见了。"
    assert mention_is_absent("雪球", a) is True
    assert mention_is_absent("安吉琳", a) is False          # she IS on screen
    assert mention_is_absent("雪球", "安吉琳紧紧抱着雪球。") is False
    # one visible mention outweighs an absent one in the same action
    assert mention_is_absent(
        "雪球", "她说雪球不见了，此时雪球从灌木丛里钻了出来。") is False
    assert mention_is_absent("Snowy", "she tells her mother Snowy is gone.") is True
    assert mention_is_absent("Snowy", "Angeline holds Snowy close.") is False


def test_zh_where_did_it_go_and_in_a_photo_are_absent():
    from app.services.stage_map import mention_is_absent
    # "asks where Snowy went" — 雪球 named because it is gone
    assert mention_is_absent(
        "雪球", "安吉丽娜震惊地问他是否知道雪球去哪儿了，李明沉默不语。") is True
    # 雪球 only appears IN A PHOTO the character is holding, not on screen
    assert mention_is_absent(
        "雪球", "李明惊讶抬头，手中握着一张他与雪球的合影。") is True
    # controls: 雪球 is actually present, must NOT read as absent
    assert mention_is_absent("雪球", "雪球看着一张旧照片。") is False   # looking at a photo
    assert mention_is_absent("雪球", "雪球去公园玩耍。") is False        # goes somewhere named


def test_zh_missing_pet_qualifier_and_longing_are_absent():
    from app.services.stage_map import mention_is_absent
    # the deployed drama's exact line: longing for the MISSING pet
    assert mention_is_absent(
        "雪球", "她低声哭泣，表达对失踪宠物雪球的思念。") is True
    assert mention_is_absent("雪球", "安吉丽娜寻找走失的雪球。") is True
    # control: the pet returns on screen
    assert mention_is_absent("雪球", "失踪多日的雪球突然从灌木丛里跑了出来。") is False


def test_zh_name_written_on_a_document_is_absent():
    from app.services.stage_map import mention_is_absent
    # 雪球 appears only as a NAME written on a vet bill, not the live rabbit
    assert mention_is_absent(
        "雪球", "安吉丽娜抽出一张写着'雪球'名字的兽医账单。") is True
    assert mention_is_absent("雪球", "账单上印着雪球的名字。") is True
    # control: the real rabbit is present
    assert mention_is_absent("雪球", "雪球在院子里蹦跳。") is False


def test_english_absence_cues_missing_pet_drama():
    # Snowy's Silence: the rabbit is SOLD/MISSING the whole drama, yet every
    # action mentions it and the named-in-action rule cast the pet into shots
    # of an empty hutch and a search. These phrasings must all read as absent.
    from app.services.stage_map import mention_is_absent
    assert mention_is_absent("Snowy", "the camera reveals Snowy's empty hutch in the background") is True
    assert mention_is_absent("Snowy", "Angeline frantically searches the backyard, calling out for Snowy.") is True
    assert mention_is_absent("Snowy", "Angeline, desperate, calls out for Snowy, her eyes scanning the yard.") is True
    assert mention_is_absent("Snowy", "she asks if he sold Snowy.") is True
    assert mention_is_absent("Snowy", "Angeline searches for Snowy behind the shed.") is True
    # a real reveal still beats absence: the pet is actually there
    assert mention_is_absent("Snowy", "she calls out for Snowy, and Snowy hops into frame.") is False


def test_drop_absent_cast_removes_the_missing_pet():
    # the "pet is gone" shot listed 雪球 as cast — its plate would render the
    # rabbit into a scene about the EMPTY cage
    from app.services.stage_map import drop_absent_cast
    shots = [{
        "shot_type": "MS", "dialogue": "妈妈，雪球不见了。",
        "action": "安吉琳坐在地板上，抱着空兔笼，哽咽着告诉母亲雪球不见了。",
        "characters_in_frame": ["安吉琳", "雪球"],
        "subjects": [{"character": "安吉琳"}, {"character": "雪球"}]}]
    lines = [{"character": "安吉琳", "line": "妈妈，雪球不见了。"}]
    _, notes = drop_absent_cast(shots, dialogue_lines=lines)
    assert shots[0]["characters_in_frame"] == ["安吉琳"]
    assert [s["character"] for s in shots[0]["subjects"]] == ["安吉琳"]
    assert notes


def test_drop_absent_cast_scene_level_reorient_wide():
    # shot 1: 雪球 only as a name on a bill -> absent. shot 2: a re-orient wide
    # that inherited 雪球 in its cast but whose generic action never mentions it.
    # 雪球 is present NOWHERE, so it must leave BOTH shots, not just shot 1.
    from app.services.stage_map import drop_absent_cast
    shots = [
        {"shot_type": "INSERT",
         "action": "安吉丽娜抽出一张写着'雪球'名字的兽医账单。",
         "characters_in_frame": ["安吉丽娜", "雪球", "杰克"],
         "subjects": [{"character": "安吉丽娜"}, {"character": "雪球"}, {"character": "杰克"}]},
        {"shot_type": "LS",
         "action": "全景，众人保持原位，气氛凝固。",
         "characters_in_frame": ["安吉丽娜", "雪球", "杰克"],
         "subjects": [{"character": "安吉丽娜"}, {"character": "雪球"}, {"character": "杰克"}]},
    ]
    _, notes = drop_absent_cast(shots)
    assert shots[0]["characters_in_frame"] == ["安吉丽娜", "杰克"]
    assert shots[1]["characters_in_frame"] == ["安吉丽娜", "杰克"]   # scene-level drop
    assert notes


def test_drop_absent_cast_never_drops_the_speaker_or_present_cast():
    from app.services.stage_map import drop_absent_cast
    shots = [{
        "shot_type": "MS", "dialogue": "我在这里。",
        "action": "雪球不见了……安吉琳这样以为，但雪球其实就在她脚边。",
        "characters_in_frame": ["安吉琳", "雪球"],
        "subjects": [{"character": "安吉琳"}, {"character": "雪球"}]}]
    _, notes = drop_absent_cast(shots)
    assert shots[0]["characters_in_frame"] == ["安吉琳", "雪球"]
    assert notes == []
