from app.workers.export_worker import build_dialogue_segments


def test_build_dialogue_segments_places_by_scene_offset():
    line_rows = [{"scene_number": 1, "line_index": 0, "audio_local": "a", "duration_seconds": 2.0},
                 {"scene_number": 2, "line_index": 0, "audio_local": "b", "duration_seconds": 1.0}]
    shot_durations = {1: [5.0], 2: [5.0]}
    segs = build_dialogue_segments(line_rows, [1, 2], shot_durations)
    starts = {s["audio_path"]: s["start"] for s in segs}
    assert starts["a"] == 0.0
    assert starts["b"] == 5.0   # scene 2 starts after scene 1's 5s of shots


def test_build_dialogue_segments_orders_lines_within_scene():
    line_rows = [{"scene_number": 1, "line_index": 1, "audio_local": "second", "duration_seconds": 1.0},
                 {"scene_number": 1, "line_index": 0, "audio_local": "first", "duration_seconds": 2.0}]
    shot_durations = {1: [10.0]}
    segs = build_dialogue_segments(line_rows, [1], shot_durations)
    # sorted by line_index: first at scene offset 0, second after first (2.0 + 0.2 gap)
    assert segs[0] == {"audio_path": "first", "start": 0.0}
    assert segs[1] == {"audio_path": "second", "start": 2.2}
