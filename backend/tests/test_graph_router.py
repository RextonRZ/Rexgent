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


# The LLM mis-transcribes uncommon CJK characters: 秦唳行 comes back as 秦斩行.
XIN, QIN, MERCHANT = _C("辛云歌"), _C("秦唳行"), _C("商人")
CJK_CAST = {"辛云歌": XIN, "秦唳行": QIN, "商人": MERCHANT}


def test_resolve_fuzzy_recovers_mistranscribed_name():
    # one wrong character out of three must still find the cast member
    assert _resolve_character(CJK_CAST, "秦斩行") is QIN


def test_resolve_fuzzy_rejects_non_cast_name():
    # a plot concept mentioned in dialogue is not a character — stays dropped
    assert _resolve_character(CJK_CAST, "敌国细作") is None


def test_resolve_fuzzy_rejects_ambiguous_near_miss():
    # two cast names equally close to the input: never guess
    twins = {"秦唳行": QIN, "秦斩行": _C("秦斩行")}
    assert _resolve_character(twins, "秦飒行") is None


def test_scene_cue_names_canonicalized_for_story_map():
    from app.routers.graph import _canonical_names
    # story map links match by exact name: cues must become cast names
    assert _canonical_names(CAST, ["REN", "KAITO"]) == ["Ren Ishida", "Kaito"]
    # unknown names pass through; duplicates collapse
    assert _canonical_names(CAST, ["REN", "Ren Ishida", "GHOST"]) == ["Ren Ishida", "GHOST"]
    assert _canonical_names(CAST, None) == []
