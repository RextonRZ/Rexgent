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
