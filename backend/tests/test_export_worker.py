from app.workers.export_worker import build_dialogue_segments


def _scene(n, shots):
    return {"scene_number": n, "shots": shots}


def test_lines_land_on_their_dialogue_shots():
    # scene 1: shot0 silent (5s), shot1 speaks (5s) -> line starts at 5.0
    line_rows = [{"scene_number": 1, "line_index": 0, "audio_local": "a", "duration_seconds": 2.0}]
    scene_plan = [_scene(1, [
        {"duration": 5.0, "has_dialogue": False},
        {"duration": 5.0, "has_dialogue": True},
    ])]
    segs = build_dialogue_segments(line_rows, scene_plan)
    assert segs == [{"audio_path": "a", "start": 5.0}]


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
