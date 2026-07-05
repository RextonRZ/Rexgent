import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.deps import get_current_user

client = TestClient(app)

USER_ID = uuid.uuid4()


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    def __init__(self, projects):
        self._projects = projects
        self.deleted = []
        self.committed = False

    def query(self, model):
        return FakeQuery(self._projects)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.committed = True


def _project(owner_id):
    return SimpleNamespace(
        id=uuid.uuid4(), user_id=str(owner_id), title="My Drama"
    )


def _override(db):
    def _fake_get_db():
        yield db

    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID)


def _clear():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_delete_project_removes_it():
    project = _project(USER_ID)
    db = FakeDB([project])
    _override(db)
    try:
        r = client.delete(f"/api/projects/{project.id}")
    finally:
        _clear()
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert db.deleted == [project]
    assert db.committed is True


def test_delete_rejects_non_owner():
    project = _project(uuid.uuid4())  # someone else's drama
    db = FakeDB([project])
    _override(db)
    try:
        r = client.delete(f"/api/projects/{project.id}")
    finally:
        _clear()
    assert r.status_code == 403
    assert db.deleted == []


def test_delete_missing_project_is_404():
    db = FakeDB([])
    _override(db)
    try:
        r = client.delete(f"/api/projects/{uuid.uuid4()}")
    finally:
        _clear()
    assert r.status_code == 404
    assert db.deleted == []
