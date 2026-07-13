from types import SimpleNamespace
from app.services.multishot import group_beats, slice_ranges, multishot_prompt


def _shot(n, chars, dialogue="hi", stype="CU", action="talks", dur=5):
    return SimpleNamespace(number=n, characters_in_frame=chars, dialogue=dialogue,
                           shot_type=stype, action=action, estimated_duration_seconds=dur)


def test_two_char_dialogue_run_becomes_one_beat():
    shots = [_shot(1, ["A"]), _shot(2, ["B"]), _shot(3, ["A"])]
    groups = group_beats(shots, max_shots=3)
    assert len(groups) == 1 and len(groups[0]) == 3


def test_run_capped_at_max_shots():
    shots = [_shot(i, ["A", "B"]) for i in range(1, 6)]
    groups = group_beats(shots, max_shots=3)
    assert [len(g) for g in groups] == [3, 2]


def test_more_than_two_characters_breaks_the_beat():
    shots = [_shot(1, ["A"]), _shot(2, ["B"]), _shot(3, ["C"])]
    groups = group_beats(shots, max_shots=4)
    assert [len(g) for g in groups] == [2, 1]


def test_silent_shot_is_a_singleton():
    shots = [_shot(1, ["A"], dialogue=""), _shot(2, ["A"]), _shot(3, ["B"])]
    groups = group_beats(shots, max_shots=3)
    assert len(groups[0]) == 1
    assert len(groups[1]) == 2


def test_lone_dialogue_shot_is_a_singleton():
    shots = [_shot(1, ["A"]), _shot(2, ["A"], dialogue="")]
    groups = group_beats(shots, max_shots=3)
    assert [len(g) for g in groups] == [1, 1]


def test_slice_ranges_are_cumulative_and_cover_total():
    r = slice_ranges([5, 5, 5], total=12.0)
    assert r[0][0] == 0.0
    assert r[-1][1] == 12.0
    assert r[0][1] == r[1][0] and r[1][1] == r[2][0]


def test_slice_ranges_proportional():
    r = slice_ranges([2, 6], total=8.0)
    assert r[0] == (0.0, 2.0) and r[1] == (2.0, 8.0)


def test_multishot_prompt_lists_each_angle():
    shots = [_shot(1, ["A"], stype="MS", action="A speaks"),
             _shot(2, ["B"], stype="CU", action="B replies")]
    p = multishot_prompt(shots)
    assert "MS" in p and "CU" in p
    assert "A speaks" in p and "B replies" in p
