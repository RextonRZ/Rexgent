"""Guaranteeing a Wan visual: when a drama's first scene doesn't already open on
a people-free shot, boarding prepends a scenery establishing shot (empty cast +
no dialogue) that the router sends to Wan. These cover the pure helpers."""
from app.services.storyboard_generator import (
    scene_opens_on_scenery, make_establishing_shot,
    insert_silent_holds, insert_atmosphere, make_atmosphere_shot,
    widen_faceless_framings, plan_hold_budget, _HELD_BEAT_LOOKS,
    hook_first_scenery,
)


def _look_by_tag(tag: str) -> tuple:
    return next(l for l in _HELD_BEAT_LOOKS if l[2] == tag)


class TestWidenFaceless:
    def test_person_framing_on_empty_shot_is_widened(self):
        shots = [{"characters_in_frame": [], "shot_type": "MS"},
                 {"characters_in_frame": [], "shot_type": "OTS"},
                 {"characters_in_frame": [], "shot_type": "MCU"}]
        widen_faceless_framings(shots)
        assert [s["shot_type"] for s in shots] == ["LS", "LS", "LS"]

    def test_faceless_close_framings_become_detail_inserts(self):
        # a faceless CU/ECU is a deliberate DETAIL shot (a hand, an object) —
        # widening it to LS destroys the Director's intent. It becomes INSERT.
        shots = [{"characters_in_frame": [], "shot_type": "CU"},
                 {"characters_in_frame": [], "shot_type": "ECU"}]
        widen_faceless_framings(shots)
        assert [s["shot_type"] for s in shots] == ["INSERT", "INSERT"]

    def test_wide_and_insert_faceless_are_left_alone(self):
        shots = [{"characters_in_frame": [], "shot_type": "EWS"},
                 {"characters_in_frame": [], "shot_type": "WS"},
                 {"characters_in_frame": [], "shot_type": "INSERT"}]
        widen_faceless_framings(shots)
        assert [s["shot_type"] for s in shots] == ["EWS", "WS", "INSERT"]

    def test_peopled_shots_keep_their_framing(self):
        # a real MS with a person in frame must NOT be widened
        shots = [{"characters_in_frame": ["Anna"], "shot_type": "MS"},
                 {"characters_in_frame": ["Anna", "Deok"], "shot_type": "CU"}]
        widen_faceless_framings(shots)
        assert shots[0]["shot_type"] == "MS"
        assert shots[1]["shot_type"] == "CU"


def _talk(cast, stype="MS", line="Hi."):
    return {"characters_in_frame": list(cast), "dialogue": line,
            "shot_type": stype, "subjects": [{"character": c} for c in cast]}


class TestSilentHolds:
    def test_inserts_held_beat_between_stable_two_person_dialogue(self):
        shots = [_talk(["Anna", "Deok"]), _talk(["Anna", "Deok"])]
        out, _ = insert_silent_holds(shots, max_holds=2)
        assert len(out) == 3
        held = out[1]
        assert held["dialogue"] is None
        assert held["characters_in_frame"] == ["Anna", "Deok"]   # same cast
        assert held["shot_type"] == "MS"                          # same framing -> continue_hold
        assert held["notes"].startswith("silent held beat")

    def test_no_hold_when_cast_not_shared(self):
        shots = [_talk(["Anna", "Deok"]), _talk(["Mara", "Elara"])]
        assert insert_silent_holds(shots, max_holds=2)[0] == shots

    def test_no_hold_for_single_person_shots(self):
        shots = [_talk(["Anna"]), _talk(["Anna"])]
        assert insert_silent_holds(shots, max_holds=2)[0] == shots

    def test_respects_max_holds_and_spaces_them(self):
        shots = [_talk(["A", "B"]) for _ in range(5)]
        out, _ = insert_silent_holds(shots, max_holds=1)
        # exactly one held beat added
        assert sum(1 for s in out if s.get("dialogue") is None) == 1

    def test_silent_shot_is_not_a_hold_anchor(self):
        # a shot with no dialogue can't seed a held beat (needs two talking shots)
        shots = [{"characters_in_frame": ["A", "B"], "dialogue": None, "shot_type": "MS"},
                 _talk(["A", "B"])]
        assert insert_silent_holds(shots, max_holds=2)[0] == shots


class TestHeldBeatVariety:
    """The 'Shattered Tides' bug: 3 held beats all read the identical canned
    line. Wording must vary, follow the tone of the line it holds after, and
    never repeat between consecutive holds — even across scenes."""

    def test_consecutive_holds_never_share_wording(self):
        shots = [_talk(["A", "B"]) for _ in range(6)]
        out, _ = insert_silent_holds(shots, max_holds=3)
        holds = [s for s in out if s.get("dialogue") is None]
        assert len(holds) >= 2
        for a, b in zip(holds, holds[1:]):
            assert a["action"] != b["action"]
            assert a["emotional_beat"] != b["emotional_beat"]

    def test_question_line_holds_as_anticipation(self):
        shots = [_talk(["A", "B"], line="Where were you last night?"),
                 _talk(["A", "B"])]
        out, _ = insert_silent_holds(shots, max_holds=1)
        assert out[1]["action"] == _look_by_tag("anticipation")[0]

    def test_exclamation_line_holds_as_tension(self):
        shots = [_talk(["A", "B"], line="Get out!"), _talk(["A", "B"])]
        out, _ = insert_silent_holds(shots, max_holds=1)
        assert out[1]["action"] == _look_by_tag("tension")[0]

    def test_context_pick_never_repeats_the_previous_hold(self):
        # two question anchors would both want 'anticipation'; the second
        # must fall through to a different look
        shots = [_talk(["A", "B"], line="Who told you?"), _talk(["A", "B"]),
                 _talk(["A", "B"], line="Why does it matter?"), _talk(["A", "B"])]
        out, _ = insert_silent_holds(shots, max_holds=2)
        holds = [s for s in out if s.get("dialogue") is None]
        assert len(holds) == 2
        assert holds[0]["action"] != holds[1]["action"]

    def test_wording_rotation_threads_across_scenes(self):
        s1 = [_talk(["A", "B"]) for _ in range(2)]
        s2 = [_talk(["A", "B"]) for _ in range(2)]
        out1, last = insert_silent_holds(s1, max_holds=1)
        out2, _ = insert_silent_holds(s2, max_holds=1, last_variant=last)
        h1 = next(s for s in out1 if s.get("dialogue") is None)
        h2 = next(s for s in out2 if s.get("dialogue") is None)
        assert h1["action"] != h2["action"]

    def test_no_holds_passes_variant_through(self):
        shots = [_talk(["A"])]
        out, last = insert_silent_holds(shots, max_holds=2, last_variant=3)
        assert out == shots
        assert last == 3

    def test_held_beat_keeps_geometry_but_drops_completed_actions(self):
        # continuity = same positions/facings; NOT re-performing the gesture
        # that already finished in the previous shot
        prev = _talk(["A", "B"])
        prev["subjects"] = [{"character": "A", "screen_side": "left",
                             "facing": "right", "action": "slams the table"},
                            {"character": "B", "screen_side": "right"}]
        shots = [prev, _talk(["A", "B"])]
        out, _ = insert_silent_holds(shots, max_holds=1)
        held = out[1]
        subj = held["subjects"][0]
        assert subj["screen_side"] == "left"
        assert subj["facing"] == "right"
        assert "action" not in subj


class TestHoldBudget:
    """Held beats are budgeted per DRAMA (~1 per 45s, cap 2), not 2 per scene —
    a 30s two-scene drama was getting 3 of them."""

    def test_short_drama_gets_one(self):
        assert plan_hold_budget(30) == 1

    def test_scales_to_two(self):
        assert plan_hold_budget(90) == 2

    def test_capped_at_two_for_long_dramas(self):
        assert plan_hold_budget(300) == 2

    def test_floor_of_one_even_when_length_missing(self):
        assert plan_hold_budget(0) == 1
        assert plan_hold_budget(None) == 1


class TestAtmosphere:
    def test_inserts_a_faceless_cutaway_in_the_middle(self):
        shots = [_talk(["A", "B"]) for _ in range(4)]
        out = insert_atmosphere(shots, 1, "a cliff", "NIGHT", "COOL")
        assert len(out) == 5
        cut = next(s for s in out if not s["characters_in_frame"])
        assert cut["dialogue"] is None
        assert cut["notes"].startswith("atmosphere cutaway")
        # not stacked on the opener
        assert out[0]["characters_in_frame"] == ["A", "B"]

    def test_zero_count_is_noop(self):
        shots = [_talk(["A"])]
        assert insert_atmosphere(shots, 0, "x", "NIGHT", "COOL") == shots

    def test_multiple_cutaways_are_spaced(self):
        shots = [_talk(["A", "B"]) for _ in range(6)]
        out = insert_atmosphere(shots, 3, "a cliff", "NIGHT", "COOL")
        cuts = [i for i, s in enumerate(out) if not s["characters_in_frame"]]
        assert len(cuts) == 3
        # spaced, not bunched together
        assert all(b - a >= 2 for a, b in zip(cuts, cuts[1:]))

    def test_not_placed_next_to_an_existing_scenery_shot(self):
        # the S1 bug: an establishing wide already at index 0 plus a cutaway two
        # shots later read as repeating. A cutaway must stay >2 shots from any
        # people-free shot, so scenery never bunches up.
        est = make_establishing_shot("a cliff", "NIGHT", "COOL")
        shots = [est] + [_talk(["A", "B"]) for _ in range(5)]
        out = insert_atmosphere(shots, 2, "a cliff", "NIGHT", "COOL")
        empties = [i for i, s in enumerate(out) if not s["characters_in_frame"]]
        assert all(b - a > 2 for a, b in zip(empties, empties[1:]))

    def test_cutaways_have_distinct_looks(self):
        shots = [_talk(["A", "B"]) for _ in range(6)]
        out = insert_atmosphere(shots, 3, "a cliff", "NIGHT", "COOL")
        cuts = [s for s in out if not s["characters_in_frame"]]
        actions = {c["action"] for c in cuts}
        types = {c["shot_type"] for c in cuts}
        assert len(actions) == len(cuts)   # every cutaway reads differently
        assert len(types) > 1

    def test_count_capped_by_available_slots(self):
        # only 2 dialogue slots (index >= 1) -> at most 2 cutaways even if asked 3
        shots = [_talk(["A", "B"]), _talk(["A", "B"]), _talk(["A", "B"])]
        out = insert_atmosphere(shots, 3, "x", "NIGHT", "COOL")
        cuts = [s for s in out if not s["characters_in_frame"]]
        assert len(cuts) == 2

    def test_atmosphere_shot_is_faceless_silent(self):
        a = make_atmosphere_shot("a harbour", "OVERCAST", "DESATURATED")
        assert a["characters_in_frame"] == []
        assert a["dialogue"] is None
        assert "harbour" in a["action"]

    def test_cutaway_never_splits_a_question_from_its_answer(self):
        # conversation continuity: a scenery cutaway between "What happened?"
        # and the answer breaks the exchange. Only a completed statement may
        # precede a cutaway — never a question or a trailing, unfinished line.
        shots = [_talk(["A", "B"], line="I found the place."),
                 _talk(["A", "B"], line="What happened here?"),
                 _talk(["A", "B"], line="I made a mistake..."),
                 _talk(["A", "B"], line="Tell me everything."),
                 _talk(["A", "B"], line="It started last winter."),
                 _talk(["A", "B"], line="Go on.")]
        out = insert_atmosphere(shots, 3, "a cliff", "NIGHT", "COOL")
        for j, s in enumerate(out):
            if not s["characters_in_frame"]:
                prev_line = str(out[j - 1].get("dialogue") or "").rstrip()
                assert not prev_line.endswith(("?", "...", "…"))

    def test_cutaway_still_lands_after_a_completed_statement(self):
        shots = [_talk(["A", "B"], line="I found the place."),
                 _talk(["A", "B"], line="We should go inside."),
                 _talk(["A", "B"], line="After you."),
                 _talk(["A", "B"], line="Fine.")]
        out = insert_atmosphere(shots, 1, "a cliff", "NIGHT", "COOL")
        assert any(not s["characters_in_frame"] for s in out)


def test_scene_with_only_peopled_or_talking_shots_needs_one():
    shots = [
        {"characters_in_frame": ["Anna"], "dialogue": None},          # has cast
        {"characters_in_frame": [], "dialogue": "Hello."},            # talks
    ]
    assert scene_opens_on_scenery(shots) is False


def test_scene_already_opening_on_scenery_is_detected():
    shots = [
        {"characters_in_frame": [], "dialogue": None},                # people-free, silent
        {"characters_in_frame": ["Anna"], "dialogue": "Hi."},
    ]
    assert scene_opens_on_scenery(shots) is True


def test_empty_shot_list_needs_one():
    assert scene_opens_on_scenery([]) is False


def test_establishing_shot_is_faceless_and_silent():
    est = make_establishing_shot("a remote cliff", "GOLDEN_HOUR", "WARM")
    assert est["characters_in_frame"] == []
    assert est["subjects"] == []
    assert est["dialogue"] is None
    assert est["shot_type"] == "EWS"
    assert est["shot_number"] == 1
    # inherits the scene's look so it cuts with the rest
    assert est["lighting"] == "GOLDEN_HOUR"
    assert est["colour_mood"] == "WARM"
    # ONLY the location + no-people clause — never the scene's character action
    assert "remote cliff" in est["action"]
    assert "No people" in est["action"]


def test_establishing_action_carries_no_character_prose():
    # regression: the action must NOT paste the scene's character description
    # (which names the cast and made the 'people-free' shot render them)
    est = make_establishing_shot("Anna's cabin", "NIGHT", "COOL")
    # the only sentence besides the location line is the 'no people' clause
    assert est["action"].strip().endswith("light and atmosphere.")
    assert "sits" not in est["action"] and "crying" not in est["action"]


def test_establishing_shot_handles_missing_location():
    est = make_establishing_shot(None, None, None)
    assert est["characters_in_frame"] == []
    assert "the location" in est["action"]
    assert est["dialogue"] is None


def _scenery():
    return {"characters_in_frame": [], "dialogue": None, "shot_type": "LS",
            "action": "The stormy sea and the cabin."}


class TestDropSceneryShots:
    """Scenery is disallowed now: empty Wan scenes render square and read as
    disconnected — even Director-authored people-free shots are dropped."""

    def test_drops_faceless_silent_shots(self):
        from app.services.storyboard_generator import drop_scenery_shots
        shots = [_talk(["A", "B"]), _scenery(), _talk(["A", "B"]), _scenery()]
        kept, dropped = drop_scenery_shots(shots)
        assert dropped == 2
        assert all(s.get("characters_in_frame") for s in kept)

    def test_peopled_and_talking_shots_survive(self):
        from app.services.storyboard_generator import drop_scenery_shots
        shots = [_talk(["A"]),
                 {"characters_in_frame": ["A"], "dialogue": None, "shot_type": "MS"},
                 {"characters_in_frame": [], "dialogue": "Hello?", "shot_type": "MS"}]
        kept, dropped = drop_scenery_shots(shots)
        assert dropped == 0
        assert kept == shots


class TestDropSilentShots:
    """DIALOGUE_ONLY: every shot carries a line — silent beats teleported
    postures (stand -> sit -> stand) and read as filler, so the drama is
    all speech now."""

    def test_drops_every_silent_shot(self):
        from app.services.storyboard_generator import drop_silent_shots
        shots = [_talk(["A", "B"]),
                 {"characters_in_frame": ["A"], "dialogue": None, "shot_type": "CU"},
                 _talk(["A", "B"]),
                 {"characters_in_frame": [], "dialogue": "", "shot_type": "LS"}]
        kept, dropped = drop_silent_shots(shots)
        assert dropped == 2
        assert all(str(s.get("dialogue") or "").strip() for s in kept)

    def test_all_speech_board_is_untouched(self):
        from app.services.storyboard_generator import drop_silent_shots
        shots = [_talk(["A", "B"]), _talk(["A"])]
        kept, dropped = drop_silent_shots(shots)
        assert dropped == 0
        assert kept == shots


class TestHookFirstScenery:
    """THE HOOK owns the first 3 seconds: scenery never plays first. The
    guaranteed Wan visual slots in at the first safe boundary AFTER the hook,
    and never between a question and its answer."""

    def test_inserts_establishing_after_the_hook(self):
        shots = [_talk(["A", "B"], line="Anna, we need to talk."),
                 _talk(["A", "B"], line="What is it?")]
        out, action = hook_first_scenery(shots, "a cabin", "NIGHT", "COOL")
        assert action == "inserted"
        assert out[0]["dialogue"] == "Anna, we need to talk."   # hook stays first
        assert out[1]["characters_in_frame"] == []              # scenery second
        assert out[1]["shot_type"] == "EWS"

    def test_never_splits_a_question_from_its_answer(self):
        shots = [_talk(["A", "B"], line="Why did you lie to me?"),
                 _talk(["A", "B"], line="I had no choice."),
                 _talk(["A", "B"], line="Tell me now.")]
        out, action = hook_first_scenery(shots, "a cabin", "NIGHT", "COOL")
        assert action == "inserted"
        empties = [i for i, s in enumerate(out) if not s["characters_in_frame"]]
        assert empties == [2]     # after the answer, not between Q and A

    def test_relocates_an_llm_scenery_opener_behind_the_hook(self):
        # the 'Shattered Tides' case: the Director opened scene 1 on a mood
        # wide; the hook must play first and the scenery slides to slot 2
        shots = [_scenery(),
                 _talk(["A", "B"], line="Anna, we need to talk."),
                 _talk(["A", "B"], line="What is it, Deok-hyun?")]
        out, action = hook_first_scenery(shots, "a cabin", "NIGHT", "COOL")
        assert action == "moved"
        assert out[0]["dialogue"] == "Anna, we need to talk."
        assert out[1]["characters_in_frame"] == []
        assert len(out) == 3      # moved, not duplicated

    def test_scenery_already_mid_scene_is_left_alone(self):
        shots = [_talk(["A", "B"]), _scenery(), _talk(["A", "B"])]
        out, action = hook_first_scenery(shots, "a cabin", "NIGHT", "COOL")
        assert action is None
        assert out == shots

    def test_tiny_scene_with_scenery_opener_is_left_alone(self):
        shots = [_scenery(), _talk(["A", "B"])]
        out, action = hook_first_scenery(shots, "a cabin", "NIGHT", "COOL")
        assert action is None

    def test_empty_scene_is_a_noop(self):
        assert hook_first_scenery([], "x", None, None) == ([], None)
