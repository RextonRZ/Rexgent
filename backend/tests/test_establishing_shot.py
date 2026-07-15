"""Guaranteeing a Wan visual: when a drama's first scene doesn't already open on
a people-free shot, boarding prepends a scenery establishing shot (empty cast +
no dialogue) that the router sends to Wan. These cover the pure helpers."""
from app.services.storyboard_generator import (
    scene_opens_on_scenery, make_establishing_shot,
)


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
