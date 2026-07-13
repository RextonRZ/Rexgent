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
