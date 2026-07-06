import uuid
from datetime import datetime
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

    def order_by(self, *a, **k):
        return self

    def group_by(self, *a, **k):
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
    def __init__(self, projects=(), jobs=(), clips=(), costs=(), reports=()):
        self.projects = list(projects)
        self.jobs = list(jobs)
        self.clips = list(clips)
        self.costs = list(costs)
        self.reports = list(reports)
        self.added = []
        self.deleted = []
        self.committed = False

    def query(self, *entities):
        name = _entity_name(entities[0])
        if name == "Project":
            return FakeQuery(self.projects)
        if name == "GenerationJob":
            return FakeQuery(self.jobs)
        if name == "GeneratedClip":
            return FakeQuery(self.clips)
        if name == "CostEvent":
            return FakeQuery(self.costs)
        if name == "AgentReport":
            return FakeQuery(self.reports)
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        # stand in for flush-time column defaults
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "status", None) is None:
            obj.status = "draft"
        now = datetime.utcnow()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def _project(owner_id, title="My Drama"):
    now = datetime.utcnow()
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=str(owner_id),
        title=title,
        genre="romance",
        premise="a premise",
        status="draft",
        poster_url=None,
        created_at=now,
        updated_at=now,
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


def test_rename_project():
    project = _project(USER_ID, title="Old Title")
    db = FakeDB([project])
    _override(db)
    try:
        r = client.patch(f"/api/projects/{project.id}", json={"title": "New Title"})
    finally:
        _clear()
    assert r.status_code == 200
    assert project.title == "New Title"
    assert r.json()["title"] == "New Title"


def test_patch_sets_poster_url():
    project = _project(USER_ID)
    db = FakeDB([project])
    _override(db)
    try:
        r = client.patch(
            f"/api/projects/{project.id}",
            json={"poster_url": "https://oss/poster.jpg"},
        )
    finally:
        _clear()
    assert r.status_code == 200
    assert project.poster_url == "https://oss/poster.jpg"


def test_patch_rejects_non_owner():
    project = _project(uuid.uuid4())
    db = FakeDB([project])
    _override(db)
    try:
        r = client.patch(f"/api/projects/{project.id}", json={"title": "Stolen"})
    finally:
        _clear()
    assert r.status_code == 403
    assert project.title == "My Drama"


def test_duplicate_creates_shallow_copy():
    project = _project(USER_ID, title="EMBERWAKE")
    db = FakeDB([project])
    _override(db)
    try:
        r = client.post(f"/api/projects/{project.id}/duplicate")
    finally:
        _clear()
    assert r.status_code == 200
    assert r.json()["title"] == "EMBERWAKE (copy)"
    assert len(db.added) == 1
    assert db.added[0].premise == "a premise"


def test_overview_empty_studio():
    db = FakeDB([])
    _override(db)
    try:
        r = client.get("/api/projects/overview")
    finally:
        _clear()
    assert r.status_code == 200
    body = r.json()
    assert body["totals"] == {
        "dramas": 0,
        "clips": 0,
        "film_seconds": 0,
        "spent_usd": 0.0,
    }
    assert body["projects"] == []
    assert body["recent_clips"] == []


def test_overview_counts_clips_and_spend():
    project = _project(USER_ID)
    job = SimpleNamespace(id=uuid.uuid4(), project_id=project.id, status="COMPLETE")
    clips = [
        SimpleNamespace(job_id=job.id, url=f"https://oss/clip{i}.mp4")
        for i in range(3)
    ]
    costs = [(project.id, 1.25)]
    db = FakeDB([project], jobs=[job], clips=clips, costs=costs)
    _override(db)
    try:
        r = client.get("/api/projects/overview")
    finally:
        _clear()
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["clips"] == 3
    assert body["totals"]["film_seconds"] == 15
    assert body["totals"]["spent_usd"] == 1.25
    p = body["projects"][0]
    assert p["clip_count"] == 3
    assert p["preview_clip_url"] == "https://oss/clip0.mp4"
    assert p["is_generating"] is False
    assert p["spent_usd"] == 1.25
    # shelf montage caps at 2 clips per drama
    assert len(body["recent_clips"]) == 2


def test_stats_empty_studio():
    db = FakeDB([])
    _override(db)
    try:
        r = client.get("/api/projects/stats")
    finally:
        _clear()
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == []
    assert body["agents"] == []
    assert body["totals"]["dramas"] == 0
    assert body["cost_split"] == {"llm": 0.0, "image": 0.0, "video": 0.0, "tts": 0.0}


def test_stats_aggregates_activity_agents_and_costs():
    project = _project(USER_ID)
    job = SimpleNamespace(id=uuid.uuid4(), project_id=project.id, status="COMPLETE")
    now = datetime.utcnow()
    clips = [
        SimpleNamespace(job_id=job.id, url=f"https://oss/c{i}.mp4", created_at=now)
        for i in range(2)
    ]
    costs = [
        SimpleNamespace(
            project_id=project.id, category="video", amount_usd=1.5, created_at=now
        ),
        SimpleNamespace(
            project_id=project.id, category="llm", amount_usd=0.25, created_at=now
        ),
    ]
    reports = [
        SimpleNamespace(agent="continuity", confidence=0.9),
        SimpleNamespace(agent="continuity", confidence=0.7),
        SimpleNamespace(agent="budget_allocator", confidence=None),
    ]
    db = FakeDB([project], jobs=[job], clips=clips, costs=costs, reports=reports)
    _override(db)
    try:
        r = client.get("/api/projects/stats")
    finally:
        _clear()
    assert r.status_code == 200
    body = r.json()
    today = now.date().isoformat()
    assert body["days"] == [{"date": today, "clips": 2, "spent": 1.75}]
    agents = {a["agent"]: a for a in body["agents"]}
    assert agents["continuity"]["runs"] == 2
    assert agents["continuity"]["avg_confidence"] == 0.8
    assert agents["budget_allocator"]["avg_confidence"] is None
    assert body["cost_split"]["video"] == 1.5
    assert body["cost_split"]["llm"] == 0.25
    assert body["totals"]["clips"] == 2
    assert body["totals"]["spent_usd"] == 1.75


def test_overview_flags_generating_projects():
    project = _project(USER_ID)
    job = SimpleNamespace(id=uuid.uuid4(), project_id=project.id, status="RUNNING")
    db = FakeDB([project], jobs=[job])
    _override(db)
    try:
        r = client.get("/api/projects/overview")
    finally:
        _clear()
    assert r.status_code == 200
    assert r.json()["projects"][0]["is_generating"] is True
