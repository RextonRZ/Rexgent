from types import SimpleNamespace
from app.workers.export_worker import (
    build_cut_plan, build_dialogue_segments, characters_needing_resynthesis,
    voice_captions_incomplete,
)


def test_voice_captions_incomplete_when_a_line_was_dropped():
    # 4 dialogue shots on screen, only 2 voiced (2 TTS drops) -> captions must
    # NOT follow the shrunken voice set; fall back to shot dialogue.
    entries = [
        {"scene_number": 1, "text": "A", "duration": 5.0},
        {"scene_number": 2, "text": "B", "duration": 5.0},
        {"scene_number": 3, "text": "C", "duration": 5.0},
        {"scene_number": 4, "text": "D", "duration": 5.0},
    ]
    spoken = [{"text": "A"}, {"text": "B"}]
    assert voice_captions_incomplete(spoken, entries) is True


def test_voice_captions_complete_when_every_shot_is_voiced():
    entries = [
        {"scene_number": 1, "text": "A", "duration": 5.0},
        {"scene_number": 2, "text": "B", "duration": 5.0},
    ]
    spoken = [{"text": "A"}, {"text": "B"}]
    assert voice_captions_incomplete(spoken, entries) is False


def test_voice_captions_complete_when_a_shot_folds_two_lines():
    # one dialogue shot carrying two voiced lines is NOT incomplete
    entries = [{"scene_number": 1, "text": "A B", "duration": 8.0}]
    spoken = [{"text": "A"}, {"text": "B"}]
    assert voice_captions_incomplete(spoken, entries) is False


def test_voice_captions_ignore_silent_shots():
    # scenery shots (no dialogue) don't count toward the coverage requirement
    entries = [
        {"scene_number": 1, "text": "", "duration": 5.0},
        {"scene_number": 1, "text": "A", "duration": 5.0},
    ]
    spoken = [{"text": "A"}]
    assert voice_captions_incomplete(spoken, entries) is False


def test_cut_plan_groups_consecutive_scene_chunks():
    entries = [
        {"scene_number": 1, "duration": 5.0, "has_dialogue": False},
        {"scene_number": 1, "duration": 10.0, "has_dialogue": True},
        {"scene_number": 2, "duration": 4.8, "has_dialogue": True},
    ]
    plan = build_cut_plan(entries)
    assert [p["scene_number"] for p in plan] == [1, 2]
    assert plan[0]["shots"] == [
        {"duration": 5.0, "has_dialogue": False, "speech_onset": None, "mouth_dur": None},
        {"duration": 10.0, "has_dialogue": True, "speech_onset": None, "mouth_dur": None},
    ]


def test_cut_plan_keeps_imported_media_as_silent_time():
    entries = [
        {"scene_number": None, "duration": 3.0, "has_dialogue": False},
        {"scene_number": 1, "duration": 5.0, "has_dialogue": True},
    ]
    plan = build_cut_plan(entries)
    assert plan[0]["scene_number"] is None
    assert plan[0]["shots"][0]["duration"] == 3.0
    assert plan[1]["scene_number"] == 1


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


def test_rows_without_recorded_voice_count_as_stale():
    # lines synthesized before voice tracking have voice_id=None — once the
    # character has a chosen voice, those must re-synthesize
    rows = [_row("Mei", None), _row("Rex", "Eric")]
    current = {"Mei": "cloned-voice-xyz", "Rex": "Eric"}
    assert characters_needing_resynthesis(rows, current, {"Mei", "Rex"}) == {"Mei"}


def test_partially_missing_lines_detected_per_slot():
    # Mei HAS one line, but her scene-2 line failed to synthesize (flaky clone
    # websocket) — slot-level detection must still flag her
    r1 = SimpleNamespace(character_name="Mei", voice_id="v1", scene_number=1, line_index=0)
    r2 = SimpleNamespace(character_name="Rex", voice_id="Eric", scene_number=1, line_index=1)
    current = {"Mei": "v1", "Rex": "Eric"}
    line_keys = {(1, 0, "Mei"), (1, 1, "Rex"), (2, 0, "Mei")}
    redo = characters_needing_resynthesis([r1, r2], current, {"Mei", "Rex"}, line_keys)
    assert redo == {"Mei"}


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


def test_recast_detection_sees_through_stage_qualifiers():
    """CATHERINE (V.O.) lines synthesized with a preset must be flagged stale
    when CATHERINE's current voice is a designed one."""
    from types import SimpleNamespace
    from app.workers.export_worker import characters_needing_resynthesis
    rows = [
        SimpleNamespace(character_name="CATHERINE (V.O.)", voice_id="Cherry",
                        scene_number=1, line_index=1),
        SimpleNamespace(character_name="LINDA", voice_id="qwen-tts-vd-linda",
                        scene_number=1, line_index=0),
    ]
    current = {"CATHERINE": "qwen-tts-vd-catherine", "LINDA": "qwen-tts-vd-linda"}
    redo = characters_needing_resynthesis(
        rows, current, {"CATHERINE (V.O.)", "LINDA"},
        {(1, 0, "LINDA"), (1, 1, "CATHERINE (V.O.)")})
    assert "CATHERINE (V.O.)" in redo   # raw name, so the line filter matches
    assert "LINDA" not in redo
