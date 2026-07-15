"""Guaranteeing a Wan visual: when a drama's first scene doesn't already open on
a people-free shot, boarding prepends a scenery establishing shot (empty cast +
no dialogue) that the router sends to Wan. These cover the pure helpers."""
from app.services.storyboard_generator import (
    scene_opens_on_scenery, make_establishing_shot,
    insert_silent_holds, insert_atmosphere, make_atmosphere_shot,
    widen_faceless_framings,
)


class TestWidenFaceless:
    def test_person_framing_on_empty_shot_is_widened(self):
        shots = [{"characters_in_frame": [], "shot_type": "MS"},
                 {"characters_in_frame": [], "shot_type": "CU"}]
        widen_faceless_framings(shots)
        assert shots[0]["shot_type"] == "LS"
        assert shots[1]["shot_type"] == "LS"

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
        out = insert_silent_holds(shots, max_holds=2)
        assert len(out) == 3
        held = out[1]
        assert held["dialogue"] is None
        assert held["characters_in_frame"] == ["Anna", "Deok"]   # same cast
        assert held["shot_type"] == "MS"                          # same framing -> continue_hold
        assert held["notes"].startswith("silent held beat")

    def test_no_hold_when_cast_not_shared(self):
        shots = [_talk(["Anna", "Deok"]), _talk(["Mara", "Elara"])]
        assert insert_silent_holds(shots, max_holds=2) == shots

    def test_no_hold_for_single_person_shots(self):
        shots = [_talk(["Anna"]), _talk(["Anna"])]
        assert insert_silent_holds(shots, max_holds=2) == shots

    def test_respects_max_holds_and_spaces_them(self):
        shots = [_talk(["A", "B"]) for _ in range(5)]
        out = insert_silent_holds(shots, max_holds=1)
        # exactly one held beat added
        assert sum(1 for s in out if s.get("dialogue") is None) == 1

    def test_silent_shot_is_not_a_hold_anchor(self):
        # a shot with no dialogue can't seed a held beat (needs two talking shots)
        shots = [{"characters_in_frame": ["A", "B"], "dialogue": None, "shot_type": "MS"},
                 _talk(["A", "B"])]
        assert insert_silent_holds(shots, max_holds=2) == shots


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
