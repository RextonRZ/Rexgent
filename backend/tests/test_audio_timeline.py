from app.services.audio_timeline import (
    scene_offsets,
    assemble_scene_segment,
    dialogue_shot_offsets,
    place_dialogue,
)


def test_scene_offsets_sums_prior_shot_durations():
    durations = {1: [5, 5], 2: [5], 3: [5, 5, 5]}
    offs = scene_offsets([1, 2, 3], durations)
    assert offs == {1: 0.0, 2: 10.0, 3: 15.0}


def test_dialogue_shot_offsets_only_counts_speaking_shots():
    scene_plan = [
        {"scene_number": 1, "shots": [
            {"duration": 5.0, "has_dialogue": False},
            {"duration": 5.0, "has_dialogue": True},
            {"duration": 5.0, "has_dialogue": True},
        ]},
        {"scene_number": 2, "shots": [
            {"duration": 4.0, "has_dialogue": True},
        ]},
    ]
    offs = dialogue_shot_offsets(scene_plan)
    assert offs == {1: [5.0, 10.0], 2: [15.0]}


def test_place_dialogue_aligns_lines_to_shots():
    scene_plan = [
        {"scene_number": 1, "shots": [
            {"duration": 5.0, "has_dialogue": False},
            {"duration": 5.0, "has_dialogue": True},
        ]},
    ]
    rows = [{"scene_number": 1, "line_index": 0, "audio_path": "a", "duration": 2.0}]
    segs = place_dialogue(rows, scene_plan)
    assert segs == [{"audio_path": "a", "start": 5.0, "duration": 2.0}]


def test_place_dialogue_carries_text_for_burned_captions():
    scene_plan = [{"scene_number": 1, "shots": [{"duration": 5.0, "has_dialogue": True}]}]
    rows = [{"scene_number": 1, "line_index": 0, "audio_path": "a", "duration": 2.0,
             "text": "We need to move.", "character": "YUKI"}]
    segs = place_dialogue(rows, scene_plan)
    assert segs[0]["text"] == "We need to move."
    assert segs[0]["character"] == "YUKI"
    assert segs[0]["start"] == 0.0


def test_assemble_scene_segment_places_lines_back_to_back():
    lines = [{"audio_path": "a", "duration": 2.0}, {"audio_path": "b", "duration": 1.5}]
    seg = assemble_scene_segment(lines, scene_offset=10.0, gap=0.2)
    assert seg[0] == {"audio_path": "a", "start": 10.0}
    assert seg[1] == {"audio_path": "b", "start": 12.2}  # 10 + 2.0 + 0.2
