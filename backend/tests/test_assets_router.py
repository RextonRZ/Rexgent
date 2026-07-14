"""Router tests for the read-only Asset Library API (/api/assets).

Auth is faked globally by conftest's autouse _signed_in_user fixture. The
AssetManager + its OSS bridge are mocked here so no real filesystem asset or
OSS upload is ever touched: only routing + response shape are under test.
"""
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.assets.schema import MusicMeta

client = TestClient(app)


def _fake_music(asset_id="m1", title="Sad Theme", mood="sadness"):
    """A real MusicMeta so .model_dump() behaves exactly like production."""
    return MusicMeta(id=asset_id, title=title, filename=f"{asset_id}.mp3",
                     type="music", mood=mood)


# --- Fake DB, mirroring test_projects_router.py -----------------------------
class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


def _entity_name(entity):
    name = getattr(entity, "__name__", None)
    if name:
        return name
    cls = getattr(entity, "class_", None)
    return getattr(cls, "__name__", "")


class FakeDB:
    def __init__(self, projects=(), scripts=(), scenes=()):
        self.projects = list(projects)
        self.scripts = list(scripts)
        self.scenes = list(scenes)

    def query(self, *entities):
        name = _entity_name(entities[0])
        if name == "Project":
            return FakeQuery(self.projects)
        if name == "Script":
            return FakeQuery(self.scripts)
        if name == "Scene":
            return FakeQuery(self.scenes)
        return FakeQuery([])


def _mock_manager(monkeypatch, find_result=None, music_result=None):
    """Point the router's module-level manager at fakes — never hits OSS."""
    import app.routers.assets as assets
    if find_result is not None:
        monkeypatch.setattr(assets._manager, "find",
                            lambda *a, **k: list(find_result))
    if music_result is not None:
        monkeypatch.setattr(assets._manager, "find_music",
                            lambda **k: list(music_result))
    monkeypatch.setattr(assets._manager, "resolve_url",
                        lambda asset, oss=None: f"https://cdn.test/{asset.filename}")


# --- Test A: GET /api/assets/music ------------------------------------------
def test_search_music_returns_resolved_results(monkeypatch):
    _mock_manager(monkeypatch, find_result=[_fake_music()])
    r = client.get("/api/assets/music")
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    item = body["results"][0]
    assert item["id"] == "m1"
    assert item["title"] == "Sad Theme"
    assert item["url"] == "https://cdn.test/m1.mp3"


# --- Test B: GET /api/assets/music/suggest?project_id=... --------------------
def test_suggest_music_returns_mood_and_results(monkeypatch):
    project = SimpleNamespace(id=uuid.uuid4(), genre="romance")
    db = FakeDB(projects=[project])

    def _fake_get_db():
        yield db

    app.dependency_overrides[get_db] = _fake_get_db
    _mock_manager(monkeypatch, music_result=[_fake_music(title="Love Theme",
                                                         mood="romance")])
    try:
        r = client.get(f"/api/assets/music/suggest?project_id={project.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    body = r.json()
    # genre "romance" derives the "romance" music mood
    assert body["mood"] == "romance"
    assert isinstance(body["results"], list)
    assert body["results"][0]["url"] == "https://cdn.test/m1.mp3"
