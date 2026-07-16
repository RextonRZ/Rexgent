"""Duration discipline: the screenwriter gets an explicit dialogue-line budget
(the 30s ask that boarded 97s had 11 unbudgeted lines), an over-budget draft
triggers ONE trim rewrite (the LLM ignores the budget instruction otherwise),
and the boarding op warns when the boarded runtime overshoots the target."""
from app.services.script_generator import (plan_dialogue_budget,
                                           count_dialogue_lines,
                                           over_line_budget, trim_note)
from app.services.storyboard_generator import board_over_target


def _structured(*line_counts):
    return {"scenes": [{"scene_number": i + 1,
                        "dialogue_lines": [{"character": "A", "line": "hi"}] * n}
                       for i, n in enumerate(line_counts)]}


class TestLineBudgetEnforcement:
    def test_counts_lines_across_scenes(self):
        assert count_dialogue_lines(_structured(4, 7)) == 11
        assert count_dialogue_lines(_structured()) == 0
        assert count_dialogue_lines(None) == 0

    def test_the_shattered_tides_draft_is_over(self):
        # 11 lines against a 30s budget of 5 -> needs the trim pass
        assert over_line_budget(_structured(4, 7), 30) == 5

    def test_one_line_of_grace(self):
        assert over_line_budget(_structured(6), 30) is None    # 5 + 1 tolerated
        assert over_line_budget(_structured(7), 30) == 5

    def test_within_budget_needs_no_trim(self):
        assert over_line_budget(_structured(3, 2), 30) is None

    def test_trim_note_names_the_numbers(self):
        note = trim_note(11, 5, 30)
        assert "11" in note and "5" in note and "30" in note


class TestDialogueBudget:
    def test_thirty_seconds_is_a_handful_of_lines(self):
        assert plan_dialogue_budget(30) == 5

    def test_seventy_seconds(self):
        assert plan_dialogue_budget(70) == 12

    def test_never_below_three_lines(self):
        assert plan_dialogue_budget(10) == 3
        assert plan_dialogue_budget(0) == 3
        assert plan_dialogue_budget(None) == 3

    def test_scales_with_long_episodes(self):
        assert plan_dialogue_budget(300) == 50


class TestSceneShotBudget:
    """The Director's per-scene budget was a flat +2 non-verbal beats: a 30s
    drama boarded 8 silent shots (37s of the 62s total). Extra beats must come
    from the TIME budget, keeping at least one non-verbal beat per scene."""

    def test_short_scene_gets_one_extra_beat(self):
        from app.services.storyboard_generator import plan_scene_shot_budget
        assert plan_scene_shot_budget(shots_per_scene=3, n_lines=3, hard_cap=12) == 4

    def test_time_budget_grants_room_when_available(self):
        from app.services.storyboard_generator import plan_scene_shot_budget
        assert plan_scene_shot_budget(shots_per_scene=6, n_lines=3, hard_cap=12) == 6

    def test_hard_cap_wins(self):
        from app.services.storyboard_generator import plan_scene_shot_budget
        assert plan_scene_shot_budget(shots_per_scene=3, n_lines=20, hard_cap=12) == 12


class TestFitSilentBeats:
    """Silent beats defaulted to 5s: 8 of them cost 37s on a 30s drama. When
    the board overshoots, silent shots clamp to 3s; dialogue keeps the time
    its lines need."""

    def _board(self):
        return [{"estimated_duration_seconds": 5, "dialogue": "Who is it?"},
                {"estimated_duration_seconds": 5, "dialogue": None},
                {"estimated_duration_seconds": 5, "dialogue": ""},
                {"estimated_duration_seconds": 3, "dialogue": None},
                {"estimated_duration_seconds": 10, "dialogue": "I can explain everything now."}]

    def test_clamps_silent_shots_when_over_target(self):
        from app.services.storyboard_generator import fit_silent_beats_to_target
        shots = self._board()   # 28s against a 20s target
        assert fit_silent_beats_to_target(shots, 20) is True
        assert [s["estimated_duration_seconds"] for s in shots] == [5, 3, 3, 3, 10]

    def test_noop_when_board_fits(self):
        from app.services.storyboard_generator import fit_silent_beats_to_target
        shots = self._board()   # 28s against a 30s target: fine
        assert fit_silent_beats_to_target(shots, 30) is False
        assert shots[1]["estimated_duration_seconds"] == 5

    def test_dialogue_durations_are_never_touched(self):
        from app.services.storyboard_generator import fit_silent_beats_to_target
        shots = self._board()
        fit_silent_beats_to_target(shots, 10)
        assert shots[0]["estimated_duration_seconds"] == 5
        assert shots[4]["estimated_duration_seconds"] == 10


class TestBoardOverTarget:
    def test_within_tolerance_is_fine(self):
        assert board_over_target(38, 30) is False    # 30% over is tolerated

    def test_the_shattered_tides_case_warns(self):
        assert board_over_target(97, 30) is True
        assert board_over_target(141, 70) is True

    def test_no_target_never_warns(self):
        assert board_over_target(500, 0) is False
        assert board_over_target(500, None) is False
