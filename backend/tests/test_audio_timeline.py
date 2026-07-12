from app.services.audio_timeline import (
    scene_offsets,
    scene_global_offsets,
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


def test_scene_global_offsets_accumulate_all_shot_durations():
    plan = [
        {"scene_number": 1, "shots": [{"duration": 5.0}, {"duration": 5.0}]},
        {"scene_number": 2, "shots": [{"duration": 5.0}, {"duration": 5.0}]},
        {"scene_number": 3, "shots": [{"duration": 5.0}, {"duration": 5.0}]},
    ]
    assert scene_global_offsets(plan) == {1: 0.0, 2: 10.0, 3: 20.0}


def test_untagged_shots_dont_collapse_dialogue_to_zero():
    # the real bug: with no shot tagged has_dialogue, every scene's line landed
    # at t=0 and all voices overlapped. Each scene must start at its own offset.
    plan = [
        {"scene_number": s, "shots": [
            {"duration": 5.0, "has_dialogue": False},
            {"duration": 5.0, "has_dialogue": False},
        ]}
        for s in (1, 2, 3)
    ]
    rows = [
        {"scene_number": 1, "line_index": 0, "audio_path": "s1l0", "duration": 2.0},
        {"scene_number": 2, "line_index": 0, "audio_path": "s2l0", "duration": 2.0},
        {"scene_number": 2, "line_index": 1, "audio_path": "s2l1", "duration": 2.0},
        {"scene_number": 3, "line_index": 0, "audio_path": "s3l0", "duration": 2.0},
    ]
    start = {p["audio_path"]: p["start"] for p in place_dialogue(rows, plan, gap=0.2)}
    assert start["s1l0"] == 0.0          # scene 1 at the top
    assert start["s2l0"] == 10.0         # scene 2 at its own offset, not 0
    assert start["s2l1"] == 12.2         # back-to-back within scene 2
    assert start["s3l0"] == 20.0         # scene 3 at its offset, not 0
    # the three scenes' opening lines never share a start (no pile-up)
    assert len({start["s1l0"], start["s2l0"], start["s3l0"]}) == 3


def test_long_line_never_overlaps_the_next_line():
    # the two-person conversation bug: line 0 runs 7s but its shot is only 5s,
    # so line 1 (pinned to the next shot's start at 5s) used to talk over it.
    plan = [{"scene_number": 1, "shots": [
        {"duration": 5.0, "has_dialogue": True},
        {"duration": 5.0, "has_dialogue": True},
    ]}]
    rows = [
        {"scene_number": 1, "line_index": 0, "audio_path": "long", "duration": 7.0},
        {"scene_number": 1, "line_index": 1, "audio_path": "reply", "duration": 2.0},
    ]
    start = {p["audio_path"]: p["start"] for p in place_dialogue(rows, plan, gap=0.2)}
    assert start["long"] == 0.0
    assert start["reply"] == 7.2  # waits for the long line + gap, not 5.0


def test_deferred_shot_missing_from_cut_does_not_shift_voices():
    # storyboard had 3 shots but shot 2 was deferred (never rendered): the cut
    # plan simply doesn't contain it, so the scene-2 line anchors to the REAL
    # video time (5s), not the storyboard's phantom 10s
    cut_plan = [
        {"scene_number": 1, "shots": [{"duration": 5.0, "has_dialogue": False}]},
        # deferred 5s shot absent
        {"scene_number": 2, "shots": [{"duration": 5.0, "has_dialogue": True}]},
    ]
    rows = [{"scene_number": 2, "line_index": 0, "audio_path": "a", "duration": 2.0}]
    segs = place_dialogue(rows, cut_plan)
    assert segs[0]["start"] == 5.0


def test_imported_media_pushes_dialogue_by_real_screen_time():
    # an imported intro (no scene) plays first — the voice waits for it
    cut_plan = [
        {"scene_number": None, "shots": [{"duration": 3.5, "has_dialogue": False}]},
        {"scene_number": 1, "shots": [{"duration": 5.0, "has_dialogue": True}]},
    ]
    rows = [{"scene_number": 1, "line_index": 0, "audio_path": "a", "duration": 2.0}]
    assert place_dialogue(rows, cut_plan)[0]["start"] == 3.5


def test_scene_split_across_cut_groups_merges_not_overwrites():
    # editor re-ordered the cut so scene 1 appears twice around scene 2: its
    # speaking shots merge into one offsets list and lines place exactly once
    cut_plan = [
        {"scene_number": 1, "shots": [{"duration": 5.0, "has_dialogue": True}]},
        {"scene_number": 2, "shots": [{"duration": 5.0, "has_dialogue": False}]},
        {"scene_number": 1, "shots": [{"duration": 5.0, "has_dialogue": True}]},
    ]
    rows = [
        {"scene_number": 1, "line_index": 0, "audio_path": "l0", "duration": 2.0},
        {"scene_number": 1, "line_index": 1, "audio_path": "l1", "duration": 2.0},
    ]
    segs = place_dialogue(rows, cut_plan)
    assert len(segs) == 2  # placed once, not once per group
    start = {p["audio_path"]: p["start"] for p in segs}
    assert start["l0"] == 0.0
    assert start["l1"] == 10.0  # the second scene-1 group, at its real time


def test_scene_overflow_never_overlaps_the_next_scenes_line():
    # a 10s drama: two 5s scenes, one speaking shot each. Scene 1 holds TWO
    # 4s lines — the second runs past scene 1's footage into scene 2's time.
    # Scene 2's line must WAIT for it, not talk over it (the old per-scene
    # guard reset at the boundary and let them collide).
    plan = [
        {"scene_number": 1, "shots": [{"duration": 5.0, "has_dialogue": True}]},
        {"scene_number": 2, "shots": [{"duration": 5.0, "has_dialogue": True}]},
    ]
    rows = [
        {"scene_number": 1, "line_index": 0, "audio_path": "a", "duration": 4.0},
        {"scene_number": 1, "line_index": 1, "audio_path": "b", "duration": 4.0},
        {"scene_number": 2, "line_index": 0, "audio_path": "c", "duration": 2.0},
    ]
    segs = place_dialogue(rows, plan)
    by_path = {s["audio_path"]: s for s in segs}
    # line b folds onto scene 1's only speaking shot, back-to-back after a
    assert by_path["b"]["start"] == 4.2
    # scene 2's line would anchor at 5.0 — but b plays until 8.2 (+gap)
    assert by_path["c"]["start"] >= 8.4
    # and the output is globally sorted with zero overlaps
    ends = None
    for s in sorted(segs, key=lambda x: x["start"]):
        assert ends is None or s["start"] >= ends
        ends = s["start"] + s["duration"]


def test_fitting_shots_restores_picture_sync():
    # once the shot is fitted to 10s (audio-first), the reply lands back on its
    # own shot's start — no waiting, no overlap.
    plan = [{"scene_number": 1, "shots": [
        {"duration": 10.0, "has_dialogue": True},
        {"duration": 5.0, "has_dialogue": True},
    ]}]
    rows = [
        {"scene_number": 1, "line_index": 0, "audio_path": "long", "duration": 7.0},
        {"scene_number": 1, "line_index": 1, "audio_path": "reply", "duration": 2.0},
    ]
    start = {p["audio_path"]: p["start"] for p in place_dialogue(rows, plan, gap=0.2)}
    assert start["long"] == 0.0
    assert start["reply"] == 10.0  # exactly its own shot


def test_speech_onset_shifts_the_line_to_the_mouth():
    # a chunk whose fake speech starts 1.4s in: the real TTS line lands there
    from app.services.audio_timeline import dialogue_shot_offsets
    plan = [{"scene_number": 1, "shots": [
        {"duration": 5.0, "has_dialogue": True, "speech_onset": 1.4},
        {"duration": 5.0, "has_dialogue": True, "speech_onset": None},
    ]}]
    assert dialogue_shot_offsets(plan) == {1: [1.4, 5.0]}
