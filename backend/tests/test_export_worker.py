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
