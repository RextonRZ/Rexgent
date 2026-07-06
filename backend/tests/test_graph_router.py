from fastapi.testclient import TestClient
from app.main import app
from app.routers.graph import _resolve_character

client = TestClient(app)
ZERO = "00000000-0000-0000-0000-000000000000"


def test_graph_endpoint_returns_characters_list():
    r = client.get(f"/api/graph/{ZERO}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("characters"), list)
    assert "relationships" in data and "scenes" in data


class _C:
    def __init__(self, name):
        self.name = name


REN, KAITO = _C("Ren Ishida"), _C("Kaito")
CAST = {"REN ISHIDA": REN, "KAITO": KAITO}


def test_resolve_exact_full_name():
    assert _resolve_character(CAST, "Ren Ishida") is REN
    assert _resolve_character(CAST, "KAITO") is KAITO


def test_resolve_screenplay_cue_name():
    # dialogue cues are short: REN must still find Ren Ishida
    assert _resolve_character(CAST, "REN") is REN
    assert _resolve_character(CAST, "Ren") is REN


def test_resolve_full_name_when_cast_stores_cue():
    cast = {"KAITO": KAITO}
    assert _resolve_character(cast, "Kaito Mori") is KAITO


def test_resolve_ambiguous_or_unknown_is_none():
    cast = {"REN ISHIDA": REN, "REN TANAKA": _C("Ren Tanaka")}
    assert _resolve_character(cast, "REN") is None  # ambiguous — never guess
    assert _resolve_character(CAST, "AKIRA") is None
    assert _resolve_character(CAST, "") is None


def test_scene_cue_names_canonicalized_for_story_map():
    from app.routers.graph import _canonical_names
    # story map links match by exact name: cues must become cast names
    assert _canonical_names(CAST, ["REN", "KAITO"]) == ["Ren Ishida", "Kaito"]
    # unknown names pass through; duplicates collapse
    assert _canonical_names(CAST, ["REN", "Ren Ishida", "GHOST"]) == ["Ren Ishida", "GHOST"]
    assert _canonical_names(CAST, None) == []
