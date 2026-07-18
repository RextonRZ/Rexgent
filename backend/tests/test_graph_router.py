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


def test_relationship_build_crash_still_emits_terminal_event():
    # the stuck-spinner bug: "Mapping character relationships" emitted started,
    # but the DB region (delete/build/commit/sync) sat outside the try/except -
    # a commit failure propagated with NO terminal stage event and the strip
    # (which has no self-heal) spun forever. Any crash must emit failed.
    import uuid as _uuid
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.database import get_db

    pid = _uuid.UUID(ZERO)
    script = SimpleNamespace(id=pid, project_id=pid,
                             structured_json={"scenes": []})
    char = SimpleNamespace(id=pid, project_id=pid, name="ANNA", role="LEAD")
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value.first.return_value = script
    q.filter.return_value.all.return_value = [char]
    q.filter.return_value.delete.return_value = 0
    db.commit.side_effect = RuntimeError("db exploded")
    app.dependency_overrides[get_db] = lambda: db

    events = []
    try:
        with patch("app.websocket.emitter.emit",
                   side_effect=lambda name, payload, pid=None:
                   events.append((name, payload))), \
             patch("app.routers.graph.RelationshipBuilder") as rb:
            rb.return_value.extract = AsyncMock(return_value=[])
            local = TestClient(app, raise_server_exceptions=False)
            r = local.post("/api/graph/relationship", json={"script_id": ZERO})
            assert r.status_code == 500
    finally:
        app.dependency_overrides.pop(get_db, None)

    stage = [p for (n, p) in events
             if n == "stage:progress" and p.get("stage") == "relationships"]
    assert stage and stage[0]["status"] == "started"
    assert stage[-1]["status"] == "failed", (
        "a crash after 'started' must still emit a terminal relationships event")
