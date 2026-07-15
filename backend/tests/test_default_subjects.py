"""The Director Stager's LLM often omits blocking `subjects`, so every shot ended
up with null blocking and the interactive top-down camera plan drew nothing.
_default_subjects backfills deterministic geometry so the plan always renders."""
from app.services.storyboard_generator import _default_subjects


def test_two_hander_faces_each_other():
    subs = _default_subjects(["Anna", "Deok-hyun"])
    assert len(subs) == 2
    by = {s["character"]: s for s in subs}
    assert by["Anna"]["screen_side"] == "left" and by["Anna"]["facing"] == "right"
    assert by["Deok-hyun"]["screen_side"] == "right" and by["Deok-hyun"]["facing"] == "left"
    assert all({"frame_position", "eyeline", "posture"} <= set(s) for s in subs)


def test_solo_faces_camera():
    subs = _default_subjects(["Deok-hyun"])
    assert len(subs) == 1
    assert subs[0]["screen_side"] == "center" and subs[0]["facing"] == "camera"


def test_empty_and_blank_names():
    assert _default_subjects([]) == []
    assert _default_subjects(["", "  "]) == []
