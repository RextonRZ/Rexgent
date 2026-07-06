import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.casting_director import distinct_locations, style_from_request


def test_distinct_locations_groups_by_key():
    scenes = [{"number": 1, "location": "Coffee Shop"},
              {"number": 2, "location": "coffee shop"},
              {"number": 3, "location": "Rooftop"}]
    locs = distinct_locations(scenes)
    keys = {l["location_key"]: l["scene_numbers"] for l in locs}
    assert keys["coffee_shop"] == [1, 2]
    assert keys["rooftop"] == [3]


@pytest.mark.asyncio
async def test_style_from_request_reframes_ip():
    qwen = MagicMock()
    qwen.chat_json = AsyncMock(return_value={
        "style_tags": ["stop-motion", "warm pastel"],
        "prompt": "stop-motion toy aesthetic, warm pastel palette",
        "negative_prompt": "photorealistic"})
    out = await style_from_request(qwen, "template", "make it like Toy Story")
    assert "stop-motion" in out["style_tags"]
    assert "prompt" in out


def test_assign_voice_matches_gender():
    from app.services.casting_director import assign_voice
    from app.services.voice_catalog import FEMALE_DEFAULTS, MALE_DEFAULTS
    from unittest.mock import MagicMock
    # female character gets a female preset
    fem = MagicMock(); fem.voice_id = None; fem.gender = "Female"
    assign_voice(fem, 0)
    assert fem.voice_id in FEMALE_DEFAULTS
    assert fem.voice_source == "preset"
    # male character gets a male preset
    male = MagicMock(); male.voice_id = None; male.gender = "male"
    assign_voice(male, 0)
    assert male.voice_id in MALE_DEFAULTS
    # two same-gender characters get distinct presets (rotated by index)
    f2 = MagicMock(); f2.voice_id = None; f2.gender = "woman"
    assign_voice(f2, 1)
    assert f2.voice_id in FEMALE_DEFAULTS and f2.voice_id != fem.voice_id


def test_default_voice_unknown_gender_falls_back():
    from app.services.voice_catalog import default_voice, FEMALE_DEFAULTS, MALE_DEFAULTS
    v = default_voice(None, 0)
    assert v in FEMALE_DEFAULTS + MALE_DEFAULTS


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, script=None, scenes=(), plates=(), style=None):
        self._script = script
        self._scenes = list(scenes)
        self._plates = list(plates)
        self._style = style
        self.added = []
        self.committed = False

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "Script":
            return _FakeQuery([self._script] if self._script else [])
        if name == "Scene":
            return _FakeQuery(self._scenes)
        if name == "LocationPlate":
            return _FakeQuery(self._plates)
        if name == "StylePreset":
            return _FakeQuery([self._style] if self._style else [])
        return _FakeQuery([])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_ensure_location_plates_fills_only_missing(monkeypatch):
    import uuid
    from types import SimpleNamespace
    import app.services.casting_director as cd

    script = SimpleNamespace(id=uuid.uuid4())
    scenes = [
        SimpleNamespace(number=1, location="Coffee Shop"),
        SimpleNamespace(number=2, location="Rooftop"),
        SimpleNamespace(number=3, location="coffee shop"),
    ]
    existing = [SimpleNamespace(location_key="rooftop")]
    db = _FakeDB(script=script, scenes=scenes, plates=existing)

    fake_plates = MagicMock()
    fake_plates.generate_and_store_plate = AsyncMock(
        return_value=("https://oss/plate.jpg", "key")
    )
    monkeypatch.setattr(cd, "PlateGenerator", lambda _db: fake_plates)

    made = await cd.ensure_location_plates(db, uuid.uuid4())

    # rooftop already had a plate — only the coffee shop is generated
    assert made == 1
    assert fake_plates.generate_and_store_plate.await_count == 1
    assert len(db.added) == 1
    assert db.added[0].location_key == "coffee_shop"
    assert db.added[0].scene_numbers == [1, 3]
    assert db.committed is True


@pytest.mark.asyncio
async def test_ensure_location_plates_noop_when_covered(monkeypatch):
    import uuid
    from types import SimpleNamespace
    import app.services.casting_director as cd

    script = SimpleNamespace(id=uuid.uuid4())
    scenes = [SimpleNamespace(number=1, location="Lab")]
    db = _FakeDB(script=script, scenes=scenes,
                 plates=[SimpleNamespace(location_key="lab")])

    fake_plates = MagicMock()
    fake_plates.generate_and_store_plate = AsyncMock()
    monkeypatch.setattr(cd, "PlateGenerator", lambda _db: fake_plates)

    made = await cd.ensure_location_plates(db, uuid.uuid4())

    assert made == 0
    fake_plates.generate_and_store_plate.assert_not_awaited()
    assert db.added == []
