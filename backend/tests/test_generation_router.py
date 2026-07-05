import uuid
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db

client = TestClient(app)


def _clip(cid, shot_id, model):
    return SimpleNamespace(
        id=cid, shot_id=shot_id, model_used=model, url="http://x/clip.mp4",
        consistency_score=0.8, status="APPROVED", retries=0,
    )


def _shot(sid, duration):
    return SimpleNamespace(id=sid, estimated_duration_seconds=duration)


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    def __init__(self, clips, shots):
        self._clips = clips
        self._shots = shots

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "GeneratedClip":
            return FakeQuery(self._clips)
        if name == "Shot":
            return FakeQuery(self._shots)
        return FakeQuery([])


def test_url_expired_detects_dead_signed_links():
    import time
    from app.routers.generation import _url_expired
    past = int(time.time()) - 100
    future = int(time.time()) + 3600
    assert _url_expired(f"http://dash/x.mp4?Expires={past}") is True
    assert _url_expired(f"http://dash/x.mp4?Expires={future}") is False
    # our OSS re-hosted clips have no Expires param -> never treated as expired
    assert _url_expired("https://rexgent-assets.oss/x.mp4") is False
    assert _url_expired(None) is False


def test_job_clips_include_cost_usd_for_wan_clip():
    job_id = uuid.uuid4()
    shot_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    clips = [_clip(clip_id, shot_id, "wan")]
    clips[0].job_id = job_id
    shots = [_shot(shot_id, 5)]

    def _fake_get_db():
        yield FakeDB(clips, shots)

    app.dependency_overrides[get_db] = _fake_get_db
    try:
        r = client.get(f"/api/generate/{job_id}/clips")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    body = r.json()["clips"][0]
    assert body["cost_usd"] == 0.75
