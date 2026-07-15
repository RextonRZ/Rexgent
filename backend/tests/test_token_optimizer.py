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
    assert result["full_shots"] + result["fast_shots"] == 2


def test_allocate_assigns_tiers():
    optimizer = TokenOptimizer()
    shots = [
        {"shot_id": "hero", "shot_type": "CU", "emotional_beat": "betrayal climax", "characters_in_frame": ["A", "B"], "dialogue": "x", "estimated_duration_seconds": 10},
        {"shot_id": "filler", "shot_type": "EWS", "emotional_beat": "transition", "characters_in_frame": [], "dialogue": None, "estimated_duration_seconds": 3},
    ]
    result = optimizer.allocate(shots)
    tiers = {s["shot_id"]: s["quality_tier"] for s in result["scored_shots"]}
    assert tiers["hero"] == "happyhorse"
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
    shots = [_hero(f"s{i}") for i in range(10)]  # 10 full shots x 10s x $0.108 = $10.80
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
    assert by_id["hook1"]["quality_tier"] == "happyhorse"
    assert by_id["hook2"]["quality_tier"] == "happyhorse"
    assert result["hook_shots"] == 2


def test_single_scene_drama_still_fits_the_cap():
    # a one-scene drama: EVERY shot is scene 1. Only the opening beats are
    # the hook — the rest must stay downgradable or the cap is unfittable.
    optimizer = TokenOptimizer()
    shots = [{**_hero(f"s{i}", scene=1), "shot_number": i + 1} for i in range(7)]
    result = optimizer.allocate(shots, budget_usd=5.0)  # available $4.25
    assert result["hook_shots"] == 2
    assert result["fits_budget"] is True
    assert result["video_cost_usd"] <= result["budget_available"]
    by_number = {s["shot_id"]: s for s in result["scored_shots"]}
    # the first two shots keep full quality
    assert by_number["s0"]["quality_tier"] == "happyhorse"
    assert by_number["s1"]["quality_tier"] == "happyhorse"


def test_hook_follows_shot_number_not_list_order():
    optimizer = TokenOptimizer()
    shots = [{**_hero("late", scene=1), "shot_number": 3},
             {**_hero("first", scene=1), "shot_number": 1},
             {**_hero("second", scene=1), "shot_number": 2}]
    result = optimizer.allocate(shots, budget_usd=40.0)
    by_id = {s["shot_id"]: s for s in result["scored_shots"]}
    assert by_id["first"]["is_hook"] and by_id["second"]["is_hook"]
    assert not by_id["late"]["is_hook"]


def test_tight_cap_recommends_a_budget_that_actually_fits():
    optimizer = TokenOptimizer()
    shots = [_hero(f"s{i}", scene=2) for i in range(12)]
    squeezed = optimizer.allocate(shots, budget_usd=5.0)
    assert squeezed["deferred_shots"] > 0
    rec = squeezed["recommended_budget_usd"]
    assert isinstance(rec, int) and rec > 5
    # re-planning at the recommended cap renders every shot at full tier
    healed = optimizer.allocate(shots, budget_usd=float(rec))
    assert healed["deferred_shots"] == 0
    assert healed["downgraded_shots"] == 0
    assert healed["recommended_budget_usd"] is None


def test_generous_budget_changes_nothing():
    optimizer = TokenOptimizer()
    shots = [_hero(f"s{i}") for i in range(3)]
    result = optimizer.allocate(shots, budget_usd=40.0)
    assert result["downgraded_shots"] == 0
    assert result["deferred_shots"] == 0
    assert result["fits_budget"] is True


def test_allocator_model_matches_dispatched_model():
    # the runner dispatches happyhorse-1.1-*; the plan must not claim another model
    optimizer = TokenOptimizer()
    result = optimizer.allocate([_hero("s1")], budget_usd=40.0)
    assert result["scored_shots"][0]["model"] == "happyhorse-1.1-t2v"


def _silent(shot_id, scene=2, dur=5):
    return {"shot_id": shot_id, "shot_type": "EWS", "scene_number": scene,
            "emotional_beat": "establishing", "characters_in_frame": [],
            "dialogue": None, "estimated_duration_seconds": dur}


def _talker(shot_id, scene=2, dur=5):
    return {"shot_id": shot_id, "shot_type": "CU", "scene_number": scene,
            "emotional_beat": "confrontation", "characters_in_frame": ["A"],
            "dialogue": "who are you?", "estimated_duration_seconds": dur}


def test_wan_primary_dialogue_shot_is_happyhorse_at_hh_rate():
    optimizer = TokenOptimizer()
    result = optimizer.allocate([_talker("talk", dur=5)], budget_usd=40.0, wan_primary=True)
    s = result["scored_shots"][0]
    assert s["quality_tier"] == "happyhorse"
    assert s["estimated_cost_usd"] == round(0.108 * 5, 3)


def test_wan_primary_silent_shot_is_wan_at_wan_rate():
    optimizer = TokenOptimizer()
    result = optimizer.allocate([_silent("scenery", dur=5)], budget_usd=40.0, wan_primary=True)
    s = result["scored_shots"][0]
    assert s["quality_tier"] == "wan"
    assert s["estimated_cost_usd"] == round(0.15 * 5, 3)


def test_wan_primary_emits_model_split_counts():
    optimizer = TokenOptimizer()
    shots = [_talker("t1"), _silent("s1"), _silent("s2")]
    result = optimizer.allocate(shots, budget_usd=40.0, wan_primary=True)
    assert result["wan_shots"] == 2
    assert result["happyhorse_shots"] == 1
    # legacy quality counts still present, and the frontend ignores them here
    assert "full_shots" in result and "fast_shots" in result
    assert "on Wan (visuals)" in result["optimisation_summary"]


def test_wan_primary_never_downgrades_to_fast():
    # a tight cap defers, but never eases a Wan/HappyHorse shot to happyhorse_fast
    optimizer = TokenOptimizer()
    shots = [_talker(f"t{i}", dur=10) for i in range(10)]
    result = optimizer.allocate(shots, budget_usd=5.0, wan_primary=True)
    assert result["downgraded_shots"] == 0
    assert result["fits_budget"] is True
    tiers = {s["quality_tier"] for s in result["scored_shots"]}
    assert "happyhorse_fast" not in tiers


def test_legacy_allocate_reports_zero_model_split():
    # wan_primary OFF: the model-split counts are 0 so the frontend falls back
    optimizer = TokenOptimizer()
    result = optimizer.allocate([_hero("s1"), _hero("s2")], budget_usd=40.0)
    assert result["wan_shots"] == 0
    assert result["happyhorse_shots"] == 0
