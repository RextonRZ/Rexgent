from app.mcp_tools.token_optimizer import TokenOptimizer


def test_score_climax_shot_high():
    optimizer = TokenOptimizer()
    score = optimizer.score_shot({
        "shot_type": "CU",
        "emotional_beat": "climax confrontation",
        "characters_in_frame": ["YUKI", "ARIA"],
        "dialogue": "I know what you are.",
        "estimated_duration_seconds": 8,
    })
    assert score >= 7


def test_score_establishing_shot_low():
    optimizer = TokenOptimizer()
    score = optimizer.score_shot({
        "shot_type": "EWS",
        "emotional_beat": "establishing dread",
        "characters_in_frame": [],
        "dialogue": None,
        "estimated_duration_seconds": 4,
    })
    assert score <= 3


def test_allocate_within_budget():
    optimizer = TokenOptimizer()
    shots = [
        {"shot_id": "s1", "shot_type": "EWS", "emotional_beat": "setup", "characters_in_frame": [], "dialogue": None, "estimated_duration_seconds": 4},
        {"shot_id": "s2", "shot_type": "CU", "emotional_beat": "climax", "characters_in_frame": ["YUKI", "ARIA"], "dialogue": "I know.", "estimated_duration_seconds": 5},
    ]
    result = optimizer.allocate(shots, budget_usd=40.0)
    assert result["total_estimated_cost"] <= 40.0 * 0.85
    assert result["wan_shots"] + result["happyhorse_shots"] == 2


def test_allocate_assigns_tiers():
    optimizer = TokenOptimizer()
    shots = [
        {"shot_id": "hero", "shot_type": "CU", "emotional_beat": "betrayal climax", "characters_in_frame": ["A", "B"], "dialogue": "x", "estimated_duration_seconds": 10},
        {"shot_id": "filler", "shot_type": "EWS", "emotional_beat": "transition", "characters_in_frame": [], "dialogue": None, "estimated_duration_seconds": 3},
    ]
    result = optimizer.allocate(shots)
    tiers = {s["shot_id"]: s["quality_tier"] for s in result["scored_shots"]}
    assert tiers["hero"] == "wan"
    assert tiers["filler"] == "happyhorse_fast"


def test_allocate_empty():
    optimizer = TokenOptimizer()
    result = optimizer.allocate([], budget_usd=40.0)
    assert result["total_shots"] == 0
    assert result["total_estimated_cost"] == 0


def _hero(shot_id, scene=2):
    return {"shot_id": shot_id, "shot_type": "CU", "scene_number": scene,
            "emotional_beat": "betrayal climax", "characters_in_frame": ["A", "B"],
            "dialogue": "x", "estimated_duration_seconds": 10}


def test_hook_scene_boosts_score():
    optimizer = TokenOptimizer()
    base = {"shot_type": "MS", "emotional_beat": "setup",
            "characters_in_frame": ["A"], "dialogue": None,
            "estimated_duration_seconds": 5}
    plain = optimizer.score_shot({**base, "scene_number": 3})
    hook = optimizer.score_shot({**base, "scene_number": 1})
    assert hook == plain + 2


def test_tiny_budget_downgrades_then_defers_to_fit():
    optimizer = TokenOptimizer()
    shots = [_hero(f"s{i}") for i in range(10)]  # 10 wan shots x 10s = $15
    result = optimizer.allocate(shots, budget_usd=5.0)  # available $4.25
    assert result["fits_budget"] is True
    assert result["video_cost_usd"] <= result["budget_available"]
    assert result["downgraded_shots"] > 0
    assert result["deferred_shots"] > 0
    tiers = {s["quality_tier"] for s in result["scored_shots"]}
    assert "deferred" in tiers


def test_hook_shots_never_downgraded_or_deferred():
    optimizer = TokenOptimizer()
    shots = [_hero("hook1", scene=1), _hero("hook2", scene=1)] + \
            [_hero(f"s{i}") for i in range(10)]
    result = optimizer.allocate(shots, budget_usd=5.0)
    by_id = {s["shot_id"]: s for s in result["scored_shots"]}
    assert by_id["hook1"]["quality_tier"] == "wan"
    assert by_id["hook2"]["quality_tier"] == "wan"
    assert result["hook_shots"] == 2


def test_generous_budget_changes_nothing():
    optimizer = TokenOptimizer()
    shots = [_hero(f"s{i}") for i in range(3)]
    result = optimizer.allocate(shots, budget_usd=40.0)
    assert result["downgraded_shots"] == 0
    assert result["deferred_shots"] == 0
    assert result["fits_budget"] is True


def test_allocator_model_matches_dispatched_wan():
    # the runner dispatches wan2.7-*; the plan must not claim a different model
    optimizer = TokenOptimizer()
    result = optimizer.allocate([_hero("s1")], budget_usd=40.0)
    assert result["scored_shots"][0]["model"] == "wan2.7-t2v"
