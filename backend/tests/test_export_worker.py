from app.workers.export_worker import build_cut_plan


def test_cut_plan_groups_consecutive_scene_chunks():
    entries = [
        {"scene_number": 1, "duration": 5.0, "has_dialogue": False},
        {"scene_number": 1, "duration": 10.0, "has_dialogue": True},
        {"scene_number": 2, "duration": 4.8, "has_dialogue": True},
    ]
    plan = build_cut_plan(entries)
    assert [p["scene_number"] for p in plan] == [1, 2]
    assert plan[0]["shots"] == [
        {"duration": 5.0, "has_dialogue": False, "speech_onset": None,
         "mouth_dur": None, "mouth_words": None},
        {"duration": 10.0, "has_dialogue": True, "speech_onset": None,
         "mouth_dur": None, "mouth_words": None},
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


def test_overlay_enabled_respects_per_export_voice_choice(monkeypatch):
    # the flag gates the capability; the per-export choice picks the track —
    # "original" ships the clips' own native audio even with the flag on
    from types import SimpleNamespace
    import app.workers.export_worker as ew
    monkeypatch.setattr(ew, "get_settings", lambda: SimpleNamespace(tts_overlay=True))
    assert ew.overlay_enabled(None) is True
    assert ew.overlay_enabled("designed") is True
    assert ew.overlay_enabled("original") is False
    assert ew.overlay_enabled("ORIGINAL") is False
    monkeypatch.setattr(ew, "get_settings", lambda: SimpleNamespace(tts_overlay=False))
    assert ew.overlay_enabled(None) is False
    assert ew.overlay_enabled("designed") is False


# ── scene breathing: a short held-frame breath at every scene boundary ──────

def test_scene_breath_pads_outgoing_scene_chunks():
    # scene changes landed instantly (tight cuts trim the trailing air): the
    # cut's last chunk of each scene gains a held-frame breath, mirrored in
    # its entry duration so caption/dialogue placement stays consistent.
    from app.workers.export_worker import apply_scene_breath
    entries = [
        {"scene_number": 1, "duration": 5.0, "has_dialogue": True},
        {"scene_number": 1, "duration": 4.0, "has_dialogue": True},
        {"scene_number": 2, "duration": 6.0, "has_dialogue": True},
        {"scene_number": 3, "duration": 3.0, "has_dialogue": False},
    ]
    inputs = [{"path": f"c{i}.mp4"} for i in range(4)]
    n = apply_scene_breath(entries, inputs, 0.5)
    assert n == 2                                  # s1->s2 and s2->s3
    assert entries[1]["duration"] == 4.5 and inputs[1]["tail_hold"] == 0.5
    assert entries[2]["duration"] == 6.5 and inputs[2]["tail_hold"] == 0.5
    assert entries[0]["duration"] == 5.0 and "tail_hold" not in inputs[0]
    # the very last chunk is the episode end — its held-ending machinery owns it
    assert entries[3]["duration"] == 3.0 and "tail_hold" not in inputs[3]


def test_scene_breath_skips_unknown_scenes_and_zero_hold():
    from app.workers.export_worker import apply_scene_breath
    entries = [{"scene_number": None, "duration": 3.0},
               {"scene_number": 1, "duration": 5.0},
               {"scene_number": 2, "duration": 5.0}]
    inputs = [{}, {}, {}]
    # imported media (scene None) never takes a breath; zero hold is a no-op
    assert apply_scene_breath(entries, inputs, 0.0) == 0
    n = apply_scene_breath(entries, inputs, 0.4)
    assert n == 1 and inputs[1]["tail_hold"] == 0.4
    assert "tail_hold" not in inputs[0]
