# backend/tests/test_director_integration.py
import pytest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import app.agent.pipeline_ops as ops
from app.models.shot import Shot


class _FakeQuery:
    def __init__(self, rows): self._rows = rows
    def filter(self, *a, **k): return self
    def order_by(self, *a, **k): return self
    def delete(self, *a, **k): return 0
    def first(self): return self._rows[0] if self._rows else None
    def all(self): return self._rows


class _FakeDB:
    def __init__(self, script, scenes, chars):
        self._m = {"Script": [script], "Scene": scenes, "Character": chars}
        self.added = []
        self.committed = False
    def query(self, model): return _FakeQuery(self._m.get(getattr(model, "__name__", ""), []))
    def add(self, obj): self.added.append(obj)
    def commit(self): self.committed = True


def _fixture_db():
    pid = uuid.uuid4()
    script = SimpleNamespace(id=uuid.uuid4(), project_id=pid)
    scene = SimpleNamespace(id=uuid.uuid4(), number=1, heading="INT. ROOM", description="a standoff",
                            emotional_beat="tension", characters_json=["A", "B"],
                            location="a room", stage_directions=[], set_json=None,
                            dialogue_json=[{"character": "A", "line": "Stop."},
                                           {"character": "B", "line": "No."}])
    chars = [SimpleNamespace(name="A", role="lead", visual_description=""),
             SimpleNamespace(name="B", role="rival", visual_description="")]
    return _FakeDB(script, [scene], chars), script


@pytest.mark.asyncio
async def test_director_on_produces_varied_shot_types(monkeypatch):
    monkeypatch.setattr(ops.get_settings(), "director_engine", True, raising=False)
    db, script = _fixture_db()
    # stub the Director plan + the Stager so the test is deterministic
    from app.director.types import ShotPlan, PlannedShot
    plan = ShotPlan(shots=[
        PlannedShot("establishing", "EWS", "PAN_LEFT", "24mm", "leading_lines", 3.0, [], "dust drifts"),
        PlannedShot("dialogue", "MS", "STATIC", "50mm", "rule_of_thirds", 4.0, [0], "a step in"),
        PlannedShot("reaction", "CU", "DOLLY_IN", "85mm", "rule_of_thirds", 2.0, [], "eyes narrow"),
        PlannedShot("dialogue", "OTS", "STATIC", "50mm", "over_the_shoulder", 4.0, [1], "a head shake"),
    ])
    staged = [
        {"shot_type": "EWS", "camera_movement": "PAN_LEFT", "action": "wide", "dialogue": None,
         "characters_in_frame": [], "director_json": {"purpose": "establishing"}},
        {"shot_type": "MS", "camera_movement": "STATIC", "action": "a", "dialogue": "Stop.",
         "characters_in_frame": ["A"], "director_json": {"purpose": "dialogue"}},
        {"shot_type": "CU", "camera_movement": "DOLLY_IN", "action": "r", "dialogue": None,
         "characters_in_frame": ["B"], "director_json": {"purpose": "reaction"}},
        {"shot_type": "OTS", "camera_movement": "STATIC", "action": "o", "dialogue": "No.",
         "characters_in_frame": ["B"], "director_json": {"purpose": "dialogue"}},
    ]
    with patch.object(ops, "plan_scene", AsyncMock(return_value=plan)), \
         patch("app.services.storyboard_generator.StoryboardGenerator.stage_plan",
               AsyncMock(return_value=staged)), \
         patch("app.services.set_dresser.SetDresser.dress", AsyncMock(return_value={})):
        await ops.generate_storyboard_op(db, str(script.id), target_length=20)

    added_shots = [s for s in db.added if isinstance(s, Shot)]
    shot_types = {s.shot_type for s in added_shots}
    assert len(shot_types) >= 3          # the anti-"all-MS" assertion
    assert any(getattr(s, "director_json", None) for s in added_shots)
