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


def test_line_tempo_clamps_to_natural_range():
    from app.services.audio_timeline import line_tempo
    assert line_tempo(2.0, 2.97) == 0.85      # big stretch clamps to the ~15% floor
    assert line_tempo(3.0, 3.1) is None       # close enough already
    assert line_tempo(4.0, 2.0) == 1.3        # big compress clamps
    assert line_tempo(2.0, None) is None      # unmeasured mouth: leave alone
    # a hallucinated over-long mouth is capped, never dragging the voice further
    assert line_tempo(2.0, 12.0) == 0.85


def test_placement_paces_the_line_across_the_mouth():
    from app.services.audio_timeline import place_dialogue
    plan = [{"scene_number": 1, "shots": [
        {"duration": 5.0, "has_dialogue": True,
         "speech_onset": 2.17, "mouth_dur": 2.97}]}]
    segs = place_dialogue([{"scene_number": 1, "line_index": 0,
                            "audio_path": "l.wav", "duration": 2.0}], plan)
    assert segs[0]["start"] == 2.17
    assert segs[0]["tempo"] == 0.85
    assert abs(segs[0]["duration"] - 2.0 / 0.85) < 0.01


def test_paced_text_inserts_pauses_at_word_boundaries():
    from app.services.audio_timeline import paced_text
    assert paced_text("I can't do this anymore.", 0) == "I can't do this anymore."
    one = paced_text("I can't do this anymore.", 1)
    assert one.count("...") == 1 and one.replace("...", "").replace("  ", " ")
    three = paced_text("I can't do this anymore.", 3)
    assert three.count("...") == 3
    # a one-word line cannot be paced
    assert paced_text("No.", 3) == "No."
    # level beyond word boundaries caps instead of crashing
    assert paced_text("Stop it.", 5).count("...") == 1


def test_pacing_retakes_targets_only_unbridgeable_gaps():
    from app.services.audio_timeline import pacing_retakes
    plan = [{"scene_number": 1, "shots": [
        {"duration": 5.0, "has_dialogue": True, "mouth_dur": 3.0},
        {"duration": 5.0, "has_dialogue": True, "mouth_dur": 2.0},
        {"duration": 5.0, "has_dialogue": True, "mouth_dur": None},
    ]}]
    rows = [
        # 1.6s voice vs 3.0s mouth -> retake; the 3.0s mouth is >1.5x the line,
        # so it is capped to 1.6*1.5 = 2.4 and only that span is chased
        {"scene_number": 1, "line_index": 0, "duration_seconds": 1.6, "text": "a"},
        # 1.8s vs 2.0s: 0.9, clamp bridges it -> untouched
        {"scene_number": 1, "line_index": 1, "duration_seconds": 1.8, "text": "b"},
        # unmeasured mouth -> untouched
        {"scene_number": 1, "line_index": 2, "duration_seconds": 1.0, "text": "c"},
        # line from a scene not in this cut -> untouched
        {"scene_number": 9, "line_index": 0, "duration_seconds": 0.5, "text": "d"},
    ]
    targets = pacing_retakes(rows, plan)
    assert len(targets) == 1
    ln, mouth = targets[0]
    assert ln["line_index"] == 0 and mouth == 2.4


def test_word_warp_plan_paces_each_word_to_the_native_grid():
    # the TTS said it evenly; the on-screen mouth paused mid-sentence.
    # Each inter-word segment gets its own tempo so the voice tracks the lips.
    from app.services.audio_timeline import word_warp_plan
    tts = [(0.10, 0.50), (0.60, 1.00), (1.10, 1.50), (1.60, 2.20)]
    mouth = [(3.00, 3.40), (3.50, 4.30), (4.90, 5.30), (5.40, 6.40)]
    plan = word_warp_plan(tts, mouth)
    assert plan is not None
    # word 2 -> word 3: tts gap 0.5s vs native gap 1.4s -> stretched, clamped
    assert {"start": 0.6, "end": 1.1, "tempo": 0.6} in plan
    # the tail past the last word passes through untouched
    assert plan[-1]["end"] is None and plan[-1]["tempo"] == 1.0
    assert all(0.6 <= p["tempo"] <= 1.6 for p in plan)


def test_word_warp_plan_refuses_mismatched_word_counts():
    # ASR misheard (different word counts): warping would misalign every
    # word after the mismatch, so the plan declines and single-tempo pacing
    # takes over
    from app.services.audio_timeline import word_warp_plan
    tts = [(0.1, 0.5), (0.6, 1.0), (1.1, 1.5), (1.6, 2.2)]
    mouth = [(3.0, 3.4), (3.5, 4.3), (4.9, 5.3)]
    assert word_warp_plan(tts, mouth) is None
    # too few words to be worth slicing
    assert word_warp_plan(tts[:2], mouth[:2]) is None


def test_word_warp_plan_skips_already_matched_pacing():
    from app.services.audio_timeline import word_warp_plan
    tts = [(0.1, 0.5), (0.6, 1.0), (1.1, 1.7)]
    mouth = [(2.1, 2.5), (2.6, 3.0), (3.1, 3.7)]  # same rhythm, just offset
    assert word_warp_plan(tts, mouth) is None


def test_warp_output_duration_sums_warped_segments():
    from app.services.audio_timeline import warp_output_duration
    plan = [{"start": 0.0, "end": 0.6, "tempo": 1.0},
            {"start": 0.6, "end": 1.1, "tempo": 0.6},
            {"start": 1.1, "end": 1.6, "tempo": 1.0},
            {"start": 1.6, "end": 2.2, "tempo": 0.6},
            {"start": 2.2, "end": None, "tempo": 1.0}]
    assert abs(warp_output_duration(plan, 2.4) - 3.133) < 0.01


def test_speech_windows_gates_only_measured_speech():
    # global (start, end) spans of the clips'\'' own fake speech: the mix
    # silences the bed exactly there, keeping ambience everywhere else
    from app.services.audio_timeline import speech_windows
    entries = [
        {"duration": 6.0, "has_dialogue": True, "speech_onset": 1.0, "mouth_dur": 3.0},
        {"duration": 4.0, "has_dialogue": False},
        {"duration": 5.0, "has_dialogue": True, "speech_onset": 0.5, "mouth_dur": 2.0},
    ]
    w = speech_windows(entries)
    assert w == [(0.85, 4.15), (10.35, 12.65)]


def test_place_dialogue_attaches_word_warp():
    from app.services.audio_timeline import place_dialogue
    line_rows = [{"scene_number": 1, "line_index": 0, "audio_path": "l0.wav",
                  "duration": 2.4, "text": "hey", "character": "MIA",
                  "words": [(0.10, 0.50), (0.60, 1.00), (1.10, 1.50), (1.60, 2.20)]}]
    scene_plan = [{"scene_number": 1, "shots": [
        {"duration": 8.0, "has_dialogue": True, "speech_onset": 3.0,
         "mouth_dur": 3.4,
         "mouth_words": [(3.00, 3.40), (3.50, 4.30), (4.90, 5.30), (5.40, 6.40)]}]}]
    seg = place_dialogue(line_rows, scene_plan)[0]
    assert seg["start"] == 3.0
    assert "warp" in seg and "tempo" not in seg
    assert abs(seg["duration"] - 3.133) < 0.01


def test_tight_cut_trims_dead_air_around_the_line():
    # a 2s line inside a 5s clip left 3s of silent holding before every cut
    # (the scores never see rhythm) — trim to 0.5s lead + line + 0.4s breath
    from app.services.audio_timeline import tight_cut_bounds
    b = tight_cut_bounds(tin=0.0, eff=5.0, onset_abs=1.0, mouth=2.0)
    assert b == (0.5, 3.4, 0.5, 2.9)  # (new_in, new_out, new_onset, new_eff)


def test_tight_cut_respects_floor_and_unmeasured():
    from app.services.audio_timeline import tight_cut_bounds
    # unmeasured speech: never touch the chunk
    assert tight_cut_bounds(0.0, 5.0, None, None) is None
    # a tiny line still keeps at least 2s of footage on screen
    b = tight_cut_bounds(0.0, 5.0, 0.2, 0.5)
    assert b is not None and b[3] >= 2.0
    # a user trim already tighter than the speech is never widened
    b2 = tight_cut_bounds(1.0, 2.0, 1.2, 3.5)
    assert b2 is None or b2[1] <= 3.0
