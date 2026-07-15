"""Guaranteeing a Wan visual: when a drama's first scene doesn't already open on
a people-free shot, boarding prepends a scenery establishing shot (empty cast +
no dialogue) that the router sends to Wan. These cover the pure helpers."""
from app.services.storyboard_generator import (
    scene_opens_on_scenery, make_establishing_shot,
    insert_silent_holds, insert_atmosphere, make_atmosphere_shot,
)


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
        out = insert_atmosphere(shots, 1, "a cliff", "waves", "NIGHT", "COOL")
        assert len(out) == 5
        cut = next(s for s in out if not s["characters_in_frame"])
        assert cut["dialogue"] is None
        assert cut["notes"].startswith("atmosphere cutaway")
        # not stacked on the opener
        assert out[0]["characters_in_frame"] == ["A", "B"]

    def test_zero_count_is_noop(self):
        shots = [_talk(["A"])]
        assert insert_atmosphere(shots, 0, "x", "y", "NIGHT", "COOL") == shots

    def test_multiple_cutaways_are_spaced(self):
        shots = [_talk(["A", "B"]) for _ in range(6)]
        out = insert_atmosphere(shots, 3, "a cliff", "waves", "NIGHT", "COOL")
        cuts = [i for i, s in enumerate(out) if not s["characters_in_frame"]]
        assert len(cuts) == 3
        # spaced, not bunched together
        assert all(b - a >= 2 for a, b in zip(cuts, cuts[1:]))

    def test_count_capped_by_available_slots(self):
        # only 2 dialogue slots (index >= 1) -> at most 2 cutaways even if asked 3
        shots = [_talk(["A", "B"]), _talk(["A", "B"]), _talk(["A", "B"])]
        out = insert_atmosphere(shots, 3, "x", "y", "NIGHT", "COOL")
        cuts = [s for s in out if not s["characters_in_frame"]]
        assert len(cuts) == 2

    def test_atmosphere_shot_is_faceless_silent(self):
        a = make_atmosphere_shot("a harbour", "boats knock together", "OVERCAST", "DESATURATED")
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
    est = make_establishing_shot("a remote cliff", "waves crash below",
                                 "GOLDEN_HOUR", "WARM")
    assert est["characters_in_frame"] == []
    assert est["subjects"] == []
    assert est["dialogue"] is None
    assert est["shot_type"] == "EWS"
    assert est["shot_number"] == 1
    # inherits the scene's look so it cuts with the rest
    assert est["lighting"] == "GOLDEN_HOUR"
    assert est["colour_mood"] == "WARM"
    # the location and description ride into the action, no people
    assert "remote cliff" in est["action"]
    assert "waves crash below" in est["action"]
    assert "No people" in est["action"]


def test_establishing_shot_handles_missing_location_and_description():
    est = make_establishing_shot(None, None, None, None)
    assert est["characters_in_frame"] == []
    assert "the location" in est["action"]
    assert est["dialogue"] is None
