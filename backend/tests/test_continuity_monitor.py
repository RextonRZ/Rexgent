"""Deterministic continuity checks on a boarded scene — WARNINGS only, like
extras_monitor: surface the break, never block or auto-fix. Catches the
reliable subset of script-to-storyboard continuity errors: a question split
from its answer by scenery, the same instant re-staged twice, and an
emotional beat frozen across consecutive shots."""
from app.services.continuity_monitor import detect_continuity_breaks


def _shot(n, action="", dialogue=None, cast=("A", "B"), beat="tension"):
    return {"shot_number": n, "action": action, "dialogue": dialogue,
            "characters_in_frame": list(cast), "emotional_beat": beat}


class TestHangingQuestion:
    def test_question_followed_by_scenery_is_flagged(self):
        shots = [_shot(1, dialogue="What happened here?", beat="dread"),
                 _shot(2, action="A wide of the empty cliffs.", cast=(), beat="awe"),
                 _shot(3, dialogue="I made a mistake.", beat="guilt")]
        found = detect_continuity_breaks(shots)
        assert any(f["type"] == "hanging_question" and f["shot_number"] == 2
                   for f in found)

    def test_question_answered_directly_is_fine(self):
        shots = [_shot(1, dialogue="What happened here?", beat="dread"),
                 _shot(2, dialogue="I made a mistake.", beat="guilt")]
        assert detect_continuity_breaks(shots) == []

    def test_statement_before_scenery_is_fine(self):
        shots = [_shot(1, dialogue="We should rest.", beat="calm"),
                 _shot(2, action="The tide rolls in.", cast=(), beat="stillness")]
        assert detect_continuity_breaks(shots) == []


class TestRepeatedAction:
    def test_identical_action_text_is_flagged(self):
        shots = [_shot(1, action="Anna reaches for the doorknob.", beat="fear"),
                 _shot(2, action="Deok waits outside.", beat="unease"),
                 _shot(3, action="Anna reaches for the doorknob.", beat="fear again")]
        found = detect_continuity_breaks(shots)
        assert any(f["type"] == "repeated_action" and f["shot_number"] == 3
                   for f in found)

    def test_case_and_spacing_do_not_hide_the_repeat(self):
        shots = [_shot(1, action="Anna reaches  for the doorknob.", beat="fear"),
                 _shot(2, action="anna reaches for the doorknob. ", beat="dread")]
        assert any(f["type"] == "repeated_action"
                   for f in detect_continuity_breaks(shots))

    def test_distinct_actions_are_fine(self):
        shots = [_shot(1, action="Anna stands.", beat="resolve"),
                 _shot(2, action="Anna opens the door.", beat="fear")]
        assert detect_continuity_breaks(shots) == []

    def test_empty_actions_are_not_a_repeat(self):
        shots = [_shot(1, action="", beat="a"), _shot(2, action="", beat="b")]
        assert detect_continuity_breaks(shots) == []


class TestFrozenBeat:
    def test_identical_consecutive_beats_are_flagged(self):
        shots = [_shot(1, action="x", beat="quiet tension"),
                 _shot(2, action="y", beat="quiet tension")]
        found = detect_continuity_breaks(shots)
        assert any(f["type"] == "frozen_beat" and f["shot_number"] == 2
                   for f in found)

    def test_progressing_beats_are_fine(self):
        shots = [_shot(1, action="x", beat="confusion"),
                 _shot(2, action="y", beat="understanding"),
                 _shot(3, action="z", beat="shock")]
        assert detect_continuity_breaks(shots) == []

    def test_missing_beats_are_not_frozen(self):
        shots = [_shot(1, action="x", beat=""), _shot(2, action="y", beat="")]
        assert detect_continuity_breaks(shots) == []


def test_findings_carry_readable_warnings():
    shots = [_shot(1, dialogue="Who are you?", beat="fear"),
             _shot(2, action="Empty shoreline.", cast=(), beat="stillness")]
    f = detect_continuity_breaks(shots)[0]
    assert "shot 2" in f["warning"] or "question" in f["warning"].lower()
