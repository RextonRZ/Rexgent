"""The budget projection must match render_plan / the storyboard badge. A silent
scene-OPENING shot with faces is an identity anchor and renders on HappyHorse,
not Wan; only a silent NON-anchor visual goes to Wan. Keying on dialogue alone
under-counted HappyHorse (the "2 Wan / 4 HappyHorse vs 6 HappyHorse" mismatch)."""
from app.mcp_tools.token_optimizer import TokenOptimizer


def _shot(sid, scene, shot, dialogue="", faces=("X",)):
    return {"shot_id": sid, "scene_number": scene, "shot_number": shot,
            "dialogue": dialogue, "characters_in_frame": list(faces),
            "estimated_duration_seconds": 5}


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
