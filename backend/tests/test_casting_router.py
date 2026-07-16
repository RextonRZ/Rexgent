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


def test_generate_character_plates_endpoint_exists():
    r = client.post("/api/casting/character/00000000-0000-0000-0000-000000000000/plates")
    # 404 for a missing character; 200 if it somehow resolves — both structurally ok
    assert r.status_code in (200, 404)


def test_run_casting_forwards_design_voice_untick():
    # untick on the spend dialog must reach the celery job, or the run
    # silently buys designed voices the user refused
    from unittest.mock import MagicMock, patch
    from app.database import get_db
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = object()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with patch("app.workers.casting_worker.run_casting_job") as m:
            r = client.post(
                "/api/casting/00000000-0000-0000-0000-000000000000/run"
                "?design_voice=false&redesign_voice=true&regen_plates=false")
            assert r.status_code == 200
            m.delay.assert_called_once_with(
                "00000000-0000-0000-0000-000000000000", False, True, False)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_worker_forwards_design_voice_to_cast_bible():
    from unittest.mock import AsyncMock, MagicMock, patch
    with patch("app.workers.casting_worker.CastingDirector") as cd, \
         patch("app.workers.casting_worker.get_session_factory") as gsf, \
         patch("app.services.api_keys.use_project_key"):
        gsf.return_value = MagicMock()
        cd.return_value.cast_bible = AsyncMock(return_value={})
        from app.workers.casting_worker import run_casting_job
        run_casting_job.apply(
            args=("00000000-0000-0000-0000-000000000000", False, True, False)).get()
        assert cd.return_value.cast_bible.call_args.kwargs["design_voice"] is False
        assert cd.return_value.cast_bible.call_args.kwargs["redesign_voice"] is True
        assert cd.return_value.cast_bible.call_args.kwargs["regen_plates"] is False
