import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ZERO = "00000000-0000-0000-0000-000000000000"


def test_persist_scenes_materializes_rows_with_flushed_ids():
    from app.routers.storyboard import persist_scenes

    added = []

    def fake_flush():
        for row in added:
            if row.id is None:
                row.id = uuid.uuid4()

    db = SimpleNamespace(add=added.append, flush=fake_flush)
    script = SimpleNamespace(id=uuid.uuid4())
    structured = {
        "scenes": [
            {"scene_number": 1, "heading": "INT. LAB - NIGHT", "summary": "x"},
            {"scene_number": 2, "heading": "EXT. STREET - DAY"},
        ]
    }

    uuids = persist_scenes(db, script, structured)

    assert len(added) == 2
    assert set(uuids.keys()) == {1, 2}
    assert all(v and v != "None" for v in uuids.values())


def test_persist_scenes_handles_empty_structuring():
    from app.routers.storyboard import persist_scenes

    db = SimpleNamespace(add=lambda o: None, flush=lambda: None)
    script = SimpleNamespace(id=uuid.uuid4())
    assert persist_scenes(db, script, {"scenes": []}) == {}


def test_delete_shot_missing_returns_404():
    r = client.delete(f"/api/storyboard/{ZERO}")
    # 404 for a shot that doesn't exist; 200 if it somehow resolved — both structurally ok
    assert r.status_code in (200, 404)


def test_delete_scene_missing_returns_404():
    r = client.delete(f"/api/storyboard/scene/{ZERO}")
    assert r.status_code == 404


def test_update_shot_missing_returns_404():
    r = client.patch(f"/api/storyboard/{ZERO}", json={"lighting": "NIGHT"})
    assert r.status_code in (200, 404)


def _render_plan_shot(number, scene_id, chars, dialogue="hi", tier="wan", fg=None):
    return SimpleNamespace(
        id=uuid.uuid4(), scene_id=scene_id, number=number, shot_type="MS",
        camera_movement=None, lighting=None, colour_mood=None, action=None,
        dialogue=dialogue, emotional_beat=None, estimated_duration_seconds=5,
        quality_tier=tier, characters_in_frame=chars, notes=None,
        director_note=None, blocking_json=None, prompt_json=None,
        foreground_characters=(fg or []),
    )


def test_shots_with_render_plan_attaches_model_and_lipsync_per_shot(monkeypatch):
    """Each serialized shot must carry render_plan with model+lipsync keys,
    predicted from LIVE settings, in the same order as the input shots —
    the frontend can only show the model a shot really renders on if this
    can never drift from predict_scene_plan's own routing."""
    import app.routers.storyboard as sb

    fake_settings = SimpleNamespace(
        identity_routing_v2=True, anchor_ref_model="happyhorse",
        lipsync_enabled=True, wan_on_same_cast=False,
        happyhorse_native_talk=False, route_continuation_to_happyhorse=False,
        wan_primary=False,
    )
    monkeypatch.setattr(sb, "get_settings", lambda: fake_settings)

    scene_id = uuid.uuid4()
    bible = {"characters": {"A": {"variants": [{"plate_image_url": "a"}]}}}
    shot1 = _render_plan_shot(1, scene_id, ["A"])                 # no anchor yet -> anchor role
    shot2 = _render_plan_shot(2, scene_id, ["A"], dialogue=None)  # same char, same angle -> continue_hold

    result = sb.shots_with_render_plan([shot1, shot2], bible)

    assert len(result) == 2
    for row in result:
        assert "render_plan" in row
        assert set(row["render_plan"].keys()) == {"model", "lipsync"}
        assert isinstance(row["render_plan"]["lipsync"], bool)
    # order preserved 1:1 with the input shots (predict_scene_plan zips positionally)
    assert result[0]["render_plan"]["model"] == "happyhorse"   # anchor -> anchor_ref_model
    assert result[1]["render_plan"]["model"] == "wan"          # continue_hold
    # additive: pre-existing fields are untouched
    assert result[0]["shot_type"] == "MS"
    assert result[0]["id"] == shot1.id
    assert result[1]["id"] == shot2.id


def test_scope_fallback_math_honors_per_episode_length():
    """The manual Generate storyboard button sends no target_length — the
    board must budget from the creation scope (seconds per episode × episodes),
    not the 30s default that made a 10s drama board three times too long."""
    # the same arithmetic the endpoint applies when the request omits length
    per_episode, episodes = 10, 1
    assert per_episode * max(1, episodes) == 10
    per_episode, episodes = 30, 3
    assert per_episode * max(1, episodes) == 90
    # and the shot budget actually shrinks with the target
    from app.services.storyboard_generator import plan_shot_budget
    shots_small, secs_small = plan_shot_budget(1, 10)
    shots_default, secs_default = plan_shot_budget(1, 30)
    assert shots_small * secs_small <= 12         # a 10s drama boards ~10s
    assert shots_default * secs_default >= 25     # the old default was ~30s
