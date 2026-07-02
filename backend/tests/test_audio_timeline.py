from app.services.audio_timeline import scene_offsets, assemble_scene_segment


def test_scene_offsets_sums_prior_shot_durations():
    durations = {1: [5, 5], 2: [5], 3: [5, 5, 5]}
    offs = scene_offsets([1, 2, 3], durations)
    assert offs == {1: 0.0, 2: 10.0, 3: 15.0}


def test_assemble_scene_segment_places_lines_back_to_back():
    lines = [{"audio_path": "a", "duration": 2.0}, {"audio_path": "b", "duration": 1.5}]
    seg = assemble_scene_segment(lines, scene_offset=10.0, gap=0.2)
    assert seg[0] == {"audio_path": "a", "start": 10.0}
    assert seg[1] == {"audio_path": "b", "start": 12.2}  # 10 + 2.0 + 0.2
