from types import SimpleNamespace
from app.workers.export_worker import (
    build_dialogue_segments, characters_needing_resynthesis,
)


def _scene(n, shots):
    return {"scene_number": n, "shots": shots}


def _row(name, voice):
    return SimpleNamespace(character_name=name, voice_id=voice)


def test_recast_character_lines_detected_as_stale():
    # Mei's lines were synthesized with Cherry, but she was recast to a clone
    rows = [_row("Mei", "Cherry"), _row("Rex", "Eric")]
    current = {"Mei": "cloned-voice-xyz", "Rex": "Eric"}
    redo = characters_needing_resynthesis(rows, current, {"Mei", "Rex"})
    assert redo == {"Mei"}  # only the recast character, not Rex


def test_speaker_with_no_lines_detected_as_missing():
    # Mei's lines were wiped (or never made) — she speaks but has no audio
    rows = [_row("Rex", "Eric")]
    current = {"Mei": "Jada", "Rex": "Eric"}
    redo = characters_needing_resynthesis(rows, current, {"Mei", "Rex"})
    assert redo == {"Mei"}


def test_unchanged_voices_need_nothing():
    rows = [_row("Mei", "Jada"), _row("Rex", "Eric")]
    current = {"Mei": "Jada", "Rex": "Eric"}
    assert characters_needing_resynthesis(rows, current, {"Mei", "Rex"}) == set()


def test_unknown_speaker_rows_never_trigger_resynthesis():
    # narrator/one-off names with no Character entry must not loop forever
    rows = [_row("旁白", "Cherry"), _row("Rex", "Eric")]
    current = {"Rex": "Eric"}
    assert characters_needing_resynthesis(rows, current, {"Rex"}) == set()


def test_lines_land_on_their_dialogue_shots():
    # scene 1: shot0 silent (5s), shot1 speaks (5s) -> line starts at 5.0
    line_rows = [{"scene_number": 1, "line_index": 0, "audio_local": "a", "duration_seconds": 2.0}]
    scene_plan = [_scene(1, [
        {"duration": 5.0, "has_dialogue": False},
        {"duration": 5.0, "has_dialogue": True},
    ])]
    segs = build_dialogue_segments(line_rows, scene_plan)
    assert segs == [{"audio_path": "a", "start": 5.0, "duration": 2.0}]


def test_segments_carry_text_for_burned_captions():
    line_rows = [{"scene_number": 1, "line_index": 0, "audio_local": "a",
                  "duration_seconds": 2.0, "text": "Run.", "character_name": "MEI"}]
    scene_plan = [_scene(1, [{"duration": 5.0, "has_dialogue": True}])]
    segs = build_dialogue_segments(line_rows, scene_plan)
    assert segs[0]["text"] == "Run."
    assert segs[0]["character"] == "MEI"


def test_lines_align_across_scenes():
    line_rows = [
        {"scene_number": 1, "line_index": 0, "audio_local": "a", "duration_seconds": 2.0},
        {"scene_number": 2, "line_index": 0, "audio_local": "b", "duration_seconds": 1.0},
    ]
    scene_plan = [
        _scene(1, [{"duration": 5.0, "has_dialogue": True}]),
        _scene(2, [{"duration": 5.0, "has_dialogue": True}]),
    ]
    segs = build_dialogue_segments(line_rows, scene_plan)
    starts = {s["audio_path"]: s["start"] for s in segs}
    assert starts["a"] == 0.0
    assert starts["b"] == 5.0  # scene 2's speaking shot starts after scene 1's 5s


def test_each_line_maps_to_its_own_shot_in_order():
    # two speaking shots -> two lines land on shot starts, not crammed back-to-back
    line_rows = [
        {"scene_number": 1, "line_index": 0, "audio_local": "first", "duration_seconds": 2.0},
        {"scene_number": 1, "line_index": 1, "audio_local": "second", "duration_seconds": 1.0},
    ]
    scene_plan = [_scene(1, [
        {"duration": 5.0, "has_dialogue": True},
        {"duration": 5.0, "has_dialogue": True},
    ])]
    segs = build_dialogue_segments(line_rows, scene_plan)
    starts = {s["audio_path"]: s["start"] for s in segs}
    assert starts["first"] == 0.0
    assert starts["second"] == 5.0  # its own shot, not 2.2s back-to-back


def test_extra_lines_fall_back_back_to_back():
    # a shot folded two lines: 2 lines, 1 dialogue shot -> second continues after first
    line_rows = [
        {"scene_number": 1, "line_index": 0, "audio_local": "one", "duration_seconds": 2.0},
        {"scene_number": 1, "line_index": 1, "audio_local": "two", "duration_seconds": 1.0},
    ]
    scene_plan = [_scene(1, [{"duration": 5.0, "has_dialogue": True}])]
    segs = build_dialogue_segments(line_rows, scene_plan)
    starts = {s["audio_path"]: s["start"] for s in segs}
    assert starts["one"] == 0.0
    assert starts["two"] == 2.2  # 0 + 2.0 + 0.2 gap
