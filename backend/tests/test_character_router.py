"""The Characters page splits humans from creatures at FIRST paint using the
characters list itself — the creature flag must ride this response, not only
the casting bible (which resolves later and made the pet visibly jump from
the humans grid into the Animals section)."""
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

client = TestClient(app)


def _char(name, desc):
    return SimpleNamespace(
        id=uuid.uuid4(), project_id=uuid.uuid4(), name=name,
        role="SUPPORTING", gender=None, estimated_age=None,
        physical_description=desc, personality_summary=None, mbti=None,
        mbti_confidence=None, speech_pattern=None, emotional_arc=None,
        reference_image_url=None, visual_description=None,
        video_prompt_fragment=None, face_keywords=None, plate_status=None,
        created_at=datetime(2026, 7, 19),
    )


def test_list_characters_carries_the_creature_flag():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        _char("安吉琳", "一位十岁的女孩，扎着马尾辫"),
        _char("雪球", "一只蓬松的白色小狗，戴着红色项圈"),
    ]
    app.dependency_overrides[get_db] = lambda: db
    try:
        r = client.get(f"/api/characters/project/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200
    by = {c["name"]: c for c in r.json()["characters"]}
    assert by["雪球"]["creature"] is True
    assert by["安吉琳"]["creature"] is False
