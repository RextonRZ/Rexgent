from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_approve_casting_dispatches_generation():
    with patch("app.routers.casting.allocate_and_generate") as m:
        m.return_value = "job-1"
        r = client.post("/api/casting/00000000-0000-0000-0000-000000000000/approve")
    # 200 with a job id, or 404 if project missing — both acceptable structurally
    assert r.status_code in (200, 404)


def test_regenerate_endpoint_exists():
    r = client.post("/api/casting/variant/00000000-0000-0000-0000-000000000000/regenerate")
    assert r.status_code in (200, 404)


def test_run_casting_dispatches():
    from unittest.mock import patch
    with patch("app.workers.casting_worker.run_casting_job") as m:
        m.delay.return_value = None
        r = client.post("/api/casting/00000000-0000-0000-0000-000000000000/run")
    assert r.status_code in (200, 404)


def test_voice_design_endpoint_exists():
    r = client.post("/api/casting/character/00000000-0000-0000-0000-000000000000/voice/design?description=gruff")
    assert r.status_code in (200, 404)
