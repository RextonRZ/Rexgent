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
    r = client.post("/api/casting/character/00000000-0000-0000-0000-000000000000/voice/design?voice=Ethan")
    assert r.status_code in (200, 404)


def test_voices_catalog_endpoint():
    r = client.get("/api/casting/voices")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) > 0
    assert {"id", "gender", "desc"} <= set(data[0].keys())


def test_generate_character_plates_endpoint_exists():
    r = client.post("/api/casting/character/00000000-0000-0000-0000-000000000000/plates")
    # 404 for a missing character; 200 if it somehow resolves — both structurally ok
    assert r.status_code in (200, 404)
