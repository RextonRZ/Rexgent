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


# --- wan_primary silent-mode grouping ---------------------------------------

def _silent(n, chars=None, stype="WS", action="holds", dur=5):
    """A SILENT shot (no dialogue) — the Wan-eligible kind under wan_primary."""
    return _shot(n, chars if chars is not None else [], dialogue="",
                 stype=stype, action=action, dur=dur)


def test_wan_primary_silent_same_cast_run_becomes_one_beat():
    # cast already established (prev_cast) so the whole run continues one face
    shots = [_silent(1, ["A"]), _silent(2, ["A"]), _silent(3, ["A"])]
    groups = group_beats(shots, max_shots=3, wan_primary=True, prev_cast={"A"})
    assert len(groups) == 1 and len(groups[0]) == 3


def test_wan_primary_silent_scenery_run_becomes_one_beat():
    # no-character scenery introduces no face, so it groups from a clean cut
    shots = [_silent(1, []), _silent(2, []), _silent(3, [])]
    groups = group_beats(shots, max_shots=3, wan_primary=True)
    assert len(groups) == 1 and len(groups[0]) == 3


def test_wan_primary_talking_shot_inside_silent_run_breaks_the_beat():
    shots = [_silent(1, ["A"]), _silent(2, ["A"]),
             _shot(3, ["A"], dialogue="hello"),          # talking -> singleton
             _silent(4, ["A"]), _silent(5, ["A"])]
    groups = group_beats(shots, max_shots=3, wan_primary=True, prev_cast={"A"})
    assert [len(g) for g in groups] == [2, 1, 2]
    assert groups[1][0].number == 3


def test_wan_primary_new_face_breaks_the_run():
    # A is established; B is a NEW face -> B cannot join or seed a silent beat
    shots = [_silent(1, ["A"]), _silent(2, ["A"]), _silent(3, ["B"])]
    groups = group_beats(shots, max_shots=3, wan_primary=True, prev_cast={"A"})
    assert [len(g) for g in groups] == [2, 1]
    assert groups[1][0].number == 3


def test_wan_primary_lone_silent_shot_is_a_singleton():
    shots = [_silent(1, [])]
    groups = group_beats(shots, max_shots=3, wan_primary=True)
    assert len(groups) == 1 and len(groups[0]) == 1


def test_multishot_prompt_is_timecoded():
    shots = [_shot(1, ["A"], stype="MS", action="A speaks"),
             _shot(2, ["B"], stype="CU", action="B replies")]
    p = multishot_prompt(shots)
    assert "Shot 1" in p and "[0.0-" in p
    assert "MS" in p and "A speaks" in p
