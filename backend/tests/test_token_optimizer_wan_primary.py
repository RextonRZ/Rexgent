"""The budget projection must match render_plan / the storyboard badge. A silent
scene-OPENING shot with faces is an identity anchor and renders on HappyHorse,
not Wan; only a silent NON-anchor visual goes to Wan. Keying on dialogue alone
under-counted HappyHorse (the "2 Wan / 4 HappyHorse vs 6 HappyHorse" mismatch)."""
from app.mcp_tools.token_optimizer import TokenOptimizer


def _shot(sid, scene, shot, dialogue="", faces=("X",), stype=None):
    return {"shot_id": sid, "scene_number": scene, "shot_number": shot,
            "dialogue": dialogue, "characters_in_frame": list(faces),
            "shot_type": stype, "estimated_duration_seconds": 5}


def test_silent_scene_anchor_with_faces_is_happyhorse_not_wan():
    # mirrors the real drama: 2 scenes, each a silent opener + two talking shots
    shots = [
        _shot("s1a", 1, 1),                 # silent anchor, faces -> HH
        _shot("s1b", 1, 2, dialogue="Hi"),  # talking -> HH
        _shot("s1c", 1, 3, dialogue="Bye"), # talking -> HH
        _shot("s2a", 2, 1),                 # silent anchor, faces -> HH
        _shot("s2b", 2, 2, dialogue="Wait"),
        _shot("s2c", 2, 3, dialogue="No"),
    ]
    res = TokenOptimizer().allocate(shots, budget_usd=40.0, wan_primary=True)
    by_id = {s["shot_id"]: s["quality_tier"] for s in res["scored_shots"]}
    assert all(v == "happyhorse" for v in by_id.values()), by_id
    assert res["wan_shots"] == 0
    assert res["happyhorse_shots"] == 6


def test_silent_reentering_character_is_newcomer_happyhorse():
    # the real drama: shot1 both, shot2 Deok only, shot3 Anna re-enters SILENT.
    # Anna was absent in shot2 -> newcomer -> HappyHorse (matches the storyboard).
    shots = [
        _shot("s1", 1, 1, faces=("Deok", "Anna")),          # anchor
        _shot("s2", 1, 2, dialogue="hi", faces=("Deok",)),  # talking
        _shot("s3", 1, 3, faces=("Anna",)),                 # silent, Anna re-enters
    ]
    res = TokenOptimizer().allocate(shots, budget_usd=40.0, wan_primary=True)
    by = {s["shot_id"]: s["quality_tier"] for s in res["scored_shots"]}
    assert by["s3"] == "happyhorse"
    assert res["wan_shots"] == 0 and res["happyhorse_shots"] == 3


def test_true_silent_continuation_of_same_face_is_wan():
    shots = [
        _shot("a", 1, 1, faces=("Deok",)),   # anchor with face -> HH
        _shot("b", 1, 2, faces=("Deok",)),   # silent, same face continues -> Wan
    ]
    res = TokenOptimizer().allocate(shots, budget_usd=40.0, wan_primary=True)
    by = {s["shot_id"]: s["quality_tier"] for s in res["scored_shots"]}
    assert by["a"] == "happyhorse" and by["b"] == "wan"


def test_silent_reangle_is_happyhorse_same_framing_stays_wan():
    # doctrine mirror: an angle change never rides Wan continuation, so the
    # budget must price a silent REANGLE as HappyHorse; only the same-framing
    # silent continuation stays a Wan visual
    shots = [
        _shot("a", 1, 1, stype="MS"),     # anchor with faces -> HH
        _shot("b", 1, 2, stype="MS"),     # silent, same framing -> Wan
        _shot("c", 1, 3, stype="OTS"),    # silent, framing CHANGE -> HH
    ]
    res = TokenOptimizer().allocate(shots, budget_usd=40.0, wan_primary=True)
    by = {s["shot_id"]: s["quality_tier"] for s in res["scored_shots"]}
    assert by["a"] == "happyhorse"
    assert by["b"] == "wan"
    assert by["c"] == "happyhorse"


def test_faceless_reangle_is_wan():
    # a faceless cutaway (empty cast) has no identity to lock, so it routes to
    # Wan even though its framing differs from the previous shot (a reangle)
    shots = [
        _shot("a", 1, 1, stype="MS"),               # anchor with faces -> HH
        _shot("cut", 1, 2, faces=(), stype="EWS"),  # faceless, framing change -> Wan
    ]
    res = TokenOptimizer().allocate(shots, budget_usd=40.0, wan_primary=True)
    by = {s["shot_id"]: s["quality_tier"] for s in res["scored_shots"]}
    assert by["cut"] == "wan"


def test_silent_non_anchor_goes_to_wan_and_faceless_anchor_too():
    shots = [
        _shot("anchor", 1, 1),                       # silent anchor + faces -> HH
        _shot("hold", 1, 2),                         # silent NON-anchor -> Wan
        _shot("empty", 2, 1, faces=()),              # silent anchor, NO faces -> Wan
    ]
    res = TokenOptimizer().allocate(shots, budget_usd=40.0, wan_primary=True)
    by_id = {s["shot_id"]: s["quality_tier"] for s in res["scored_shots"]}
    assert by_id["anchor"] == "happyhorse"
    assert by_id["hold"] == "wan"
    assert by_id["empty"] == "wan"
    assert res["wan_shots"] == 2 and res["happyhorse_shots"] == 1


def test_multishot_silent_beat_prices_as_wan():
    # Five Minutes Back scene 1: a dialogue MCU, then a silent re-orient LS and
    # a silent MS. Role routing alone says HappyHorse for both reangles, but
    # the runner merges the silent pair into ONE wan multi-shot beat — the plan
    # must price and count them as Wan, or the chip reads "9 HappyHorse" while
    # the ledger records 2 Wan clips.
    shots = [
        _shot("s1", 1, 1, dialogue="I have to save him.", stype="MCU"),
        _shot("s2", 1, 2, stype="LS"),
        _shot("s3", 1, 3, stype="MS"),
    ]
    res = TokenOptimizer().allocate(shots, budget_usd=40.0, wan_primary=True,
                                    multishot=True, multishot_max_shots=3)
    by = {s["shot_id"]: s["quality_tier"] for s in res["scored_shots"]}
    assert by == {"s1": "happyhorse", "s2": "wan", "s3": "wan"}
    assert res["wan_shots"] == 2 and res["happyhorse_shots"] == 1


def test_multishot_off_keeps_reangles_on_happyhorse():
    # same scene without multishot: the beat override must not fire
    shots = [
        _shot("s1", 1, 1, dialogue="line", stype="MCU"),
        _shot("s2", 1, 2, stype="LS"),
        _shot("s3", 1, 3, stype="MS"),
    ]
    res = TokenOptimizer().allocate(shots, budget_usd=40.0, wan_primary=True)
    assert res["wan_shots"] == 0 and res["happyhorse_shots"] == 3
