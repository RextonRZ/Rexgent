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


class TestBoardOverTarget:
    def test_within_tolerance_is_fine(self):
        assert board_over_target(38, 30) is False    # 30% over is tolerated

    def test_the_shattered_tides_case_warns(self):
        assert board_over_target(97, 30) is True
        assert board_over_target(141, 70) is True

    def test_no_target_never_warns(self):
        assert board_over_target(500, 0) is False
        assert board_over_target(500, None) is False
