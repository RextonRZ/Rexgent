"""Duration discipline: the screenwriter gets an explicit dialogue-line budget
(the 30s ask that boarded 97s had 11 unbudgeted lines), and the boarding op
warns when the boarded runtime overshoots the target."""
from app.services.script_generator import plan_dialogue_budget
from app.services.storyboard_generator import board_over_target


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
