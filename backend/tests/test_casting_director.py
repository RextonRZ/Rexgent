import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.casting_director import (distinct_locations, style_from_request,
                                           resolve_outfit, _strip_face_obscuring_eyewear,
                                           location_plate_prompt)


def test_strips_face_obscuring_eyewear():
    assert _strip_face_obscuring_eyewear("black dress, heels, lab glasses") == "black dress, heels"
    assert _strip_face_obscuring_eyewear("grey suit, sunglasses, dark tie") == "grey suit, dark tie"
    assert _strip_face_obscuring_eyewear("hoodie, ski mask, jeans") == "hoodie, jeans"
    # ordinary prescription glasses are kept
    assert "reading glasses" in _strip_face_obscuring_eyewear("cardigan, reading glasses")


def test_resolve_outfit_drops_eyewear():
    assert resolve_outfit("navy blazer, safety glasses, slacks", None) == "navy blazer, slacks"


def test_assign_voice_defaults_to_preset_without_overlay():
    # TTS_OVERLAY off: no paid design — a gender-matched preset is assigned
    from types import SimpleNamespace
    from app.services.casting_director import assign_voice
    c = SimpleNamespace(voice_id=None, voice_model=None, voice_source=None,
                        gender="female", name="Anna")
    assign_voice(c, 0)
    assert c.voice_id
    assert c.voice_source == "preset"


def test_voice_design_prompt_folds_the_character_sheet():
    from types import SimpleNamespace
    from app.services.casting_director import voice_design_prompt
    c = SimpleNamespace(estimated_age="20s", gender="female",
                        personality_summary="guarded, warm underneath")
    p = voice_design_prompt(c)
    assert "female" in p and "20s" in p and "guarded" in p


def test_distinct_locations_groups_by_key():
    scenes = [{"number": 1, "location": "Coffee Shop"},
              {"number": 2, "location": "coffee shop"},
              {"number": 3, "location": "Rooftop"}]
    locs = distinct_locations(scenes)
    keys = {l["location_key"]: l["scene_numbers"] for l in locs}
    assert keys["coffee_shop"] == [1, 2]
    assert keys["rooftop"] == [3]


def test_same_place_same_view_shares_a_plate_but_views_split():
    # the 'Shattered Tides' bug, refined: same-view scenes of one place must
    # share a plate (no two unrelated paintings of the cabin), but the plate
    # is RENDERED on screen as the set, so interior and exterior views must
    # NOT merge — an exterior shot anchored to an interior room is wrong.
    scenes = [{"number": 1, "location": "Anna's Cabin",
               "heading": "INT. ANNA'S CABIN - NIGHT"},
              {"number": 2, "location": "Front of Anna's Cabin",
               "heading": "INT. ANNA'S CABIN - NIGHT"},
              {"number": 3, "location": "Anna's Cabin",
               "heading": "INT. ANNA'S CABIN - NIGHT"}]
    locs = distinct_locations(scenes)
    by_key = {l["location_key"]: l for l in locs}
    assert set(by_key) == {"anna_s_cabin__int", "anna_s_cabin__ext"}
    assert by_key["anna_s_cabin__int"]["scene_numbers"] == [1, 3]
    assert by_key["anna_s_cabin__ext"]["scene_numbers"] == [2]
    # the 'front of' qualifier outranks the mislabeled INT heading
    assert by_key["anna_s_cabin__ext"]["view"] == "ext"
    assert by_key["anna_s_cabin__int"]["description"] == "Anna's Cabin"


def test_inside_qualifier_joins_the_interior_plate():
    scenes = [{"number": 1, "location": "the courtroom",
               "heading": "INT. COURTROOM - DAY"},
              {"number": 2, "location": "Inside the Courtroom",
               "heading": "INT. COURTROOM - DAY"},
              {"number": 3, "location": "outside the courtroom",
               "heading": "EXT. COURTHOUSE STEPS - DAY"}]
    locs = distinct_locations(scenes)
    by_key = {l["location_key"]: l for l in locs}
    assert by_key["courtroom__int"]["scene_numbers"] == [1, 2]
    assert by_key["courtroom__ext"]["scene_numbers"] == [3]


def test_genuinely_different_places_stay_separate():
    scenes = [{"number": 1, "location": "beach"},
              {"number": 2, "location": "Anna's Cabin"}]
    assert len(distinct_locations(scenes)) == 2


def test_location_plate_prompt_carries_scene_hints():
    p = location_plate_prompt("Anna's Cabin",
                              heading="INT. ANNA'S CABIN - NIGHT", tags=["moody"])
    assert "Anna's Cabin" in p
    assert "interior" in p
    assert "night" in p
    assert "no people" in p.lower()
    assert "moody" in p


def test_location_plate_prompt_survives_missing_heading():
    p = location_plate_prompt("beach", heading=None, tags=[])
    assert "beach" in p
    assert "no people" in p.lower()


def test_heading_time_words_like_later_are_not_lighting():
    p = location_plate_prompt("beach", heading="EXT. BEACH - LATER", tags=[])
    assert "exterior" in p
    assert "later" not in p.lower()


def test_prompt_view_overrides_mislabeled_heading():
    p = location_plate_prompt("Front of Anna's Cabin",
                              heading="INT. ANNA'S CABIN - NIGHT",
                              tags=[], view="ext")
    assert "exterior" in p
    assert "interior" not in p
    assert "night" in p    # the time still comes from the heading


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
        SimpleNamespace(number=1, location="Coffee Shop", heading="INT. COFFEE SHOP - DAY"),
        SimpleNamespace(number=2, location="Rooftop", heading="EXT. ROOFTOP - NIGHT"),
        SimpleNamespace(number=3, location="coffee shop", heading="INT. COFFEE SHOP - DAY"),
    ]
    existing = [SimpleNamespace(location_key="rooftop__ext")]
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
    assert db.added[0].location_key == "coffee_shop__int"
    assert db.added[0].scene_numbers == [1, 3]
    assert db.committed is True


@pytest.mark.asyncio
async def test_ensure_location_plates_noop_when_covered(monkeypatch):
    import uuid
    from types import SimpleNamespace
    import app.services.casting_director as cd

    script = SimpleNamespace(id=uuid.uuid4())
    scenes = [SimpleNamespace(number=1, location="Lab", heading="INT. LAB - NIGHT")]
    db = _FakeDB(script=script, scenes=scenes,
                 plates=[SimpleNamespace(location_key="lab__int")])

    fake_plates = MagicMock()
    fake_plates.generate_and_store_plate = AsyncMock()
    monkeypatch.setattr(cd, "PlateGenerator", lambda _db: fake_plates)

    made = await cd.ensure_location_plates(db, uuid.uuid4())

    assert made == 0
    fake_plates.generate_and_store_plate.assert_not_awaited()
    assert db.added == []


def test_resolve_outfit_wardrobe_wins_clothing_backfills():
    """Clothing ownership: the scene's wardrobe outfit wins; an empty scene
    outfit falls back to the character's default clothing (appearance's
    clothing_keywords) so a shot never renders them naked now that the
    appearance fragment carries no clothing."""
    from app.services.casting_director import resolve_outfit
    # wardrobe present -> wardrobe wins
    assert resolve_outfit("black hoodie, sneakers", "grey tee") == "black hoodie, sneakers"
    # wardrobe empty -> default clothing backfills (KERRY's empty-outfit case)
    assert resolve_outfit("", "school uniform") == "school uniform"
    assert resolve_outfit(None, "school uniform") == "school uniform"
    assert resolve_outfit("   ", "school uniform") == "school uniform"
    # neither -> empty (the prompt simply omits an outfit line)
    assert resolve_outfit(None, None) == ""
