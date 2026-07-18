"""A parser rejection (legacy .doc, scanned PDF) must surface as a 400 with
the parser's own message — it used to bubble up as an opaque 500."""
import io
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

client = TestClient(app)


def test_parse_maps_parser_valueerror_to_400():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (
        SimpleNamespace(id=uuid.uuid4()))  # the project exists
    app.dependency_overrides[get_db] = lambda: db
    try:
        r = client.post(
            "/api/script/parse",
            data={"project_id": str(uuid.uuid4())},
            files={"file": ("old.doc", io.BytesIO(b"\xd0\xcf\x11\xe0"),
                            "application/msword")},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 400
    assert "docx or PDF" in r.json()["detail"]
