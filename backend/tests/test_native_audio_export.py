from app.services.caption_generator import CaptionGenerator


def test_captions_come_from_shot_dialogue_without_tts():
    cut = [{"dialogue": "Stop right there.", "duration": 4.0},
           {"dialogue": None, "duration": 2.0},
           {"dialogue": "You lied to me.", "duration": 5.0}]
    srt = CaptionGenerator().generate_srt(cut)
    assert "Stop right there." in srt and "You lied to me." in srt
    assert srt.count("-->") == 2


def test_native_audio_never_muted():
    from app.workers import export_worker as ew
    mute, vol = ew.native_audio_policy()
    assert mute is False and (vol is None or vol == 1.0)


def test_preview_plan_builds_caption_segments_from_dialogue():
    # the editor preview shows captions again (rebuilt from shot dialogue, not TTS)
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/export/preview_plan", json={
        "project_id": "00000000-0000-0000-0000-000000000000",
        "entries": [
            {"scene_number": 1, "duration": 4.0, "has_dialogue": True, "text": "Stop right there."},
            {"scene_number": 1, "duration": 2.0, "has_dialogue": False, "text": None},
            {"scene_number": 2, "duration": 5.0, "has_dialogue": True, "text": "You lied to me."},
        ],
    })
    assert resp.status_code == 200
    segs = resp.json()["segments"]
    assert len(segs) == 2  # only the two dialogue chunks are captioned
    assert segs[0] == {"start": 0.0, "duration": 4.0, "text": "Stop right there."}
    # the second caption starts after chunk 1 (4.0s) + the silent chunk 2 (2.0s)
    assert segs[1]["start"] == 6.0 and segs[1]["text"] == "You lied to me."
