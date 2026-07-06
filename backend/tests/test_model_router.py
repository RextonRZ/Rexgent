from app.services.model_router import (
    resolve_model, llm_cost_for, tier_label, TASK_MODELS,
)


def test_creative_tasks_stay_on_max():
    assert resolve_model("script") == "qwen-max"
    assert resolve_model("storyboard") == "qwen-max"


def test_structuring_tasks_route_to_flash():
    for task in ("structure", "characters", "wardrobe", "mbti", "clarify", "title"):
        assert resolve_model(task) == "qwen-flash", task


def test_analysis_tasks_route_to_plus():
    for task in ("judge", "plot_gap", "ending", "prompt_craft"):
        assert resolve_model(task) == "qwen-plus", task


def test_explicit_model_wins_over_task_route():
    assert resolve_model("structure", explicit="qwen3-max") == "qwen3-max"


def test_unknown_task_defaults_to_max():
    assert resolve_model(None) == "qwen-max"
    assert resolve_model("no_such_task") == "qwen-max"


def test_flash_is_cheaper_than_max_for_same_tokens():
    flash = llm_cost_for("qwen-flash", 10_000, 2_000)
    max_ = llm_cost_for("qwen-max", 10_000, 2_000)
    assert flash < max_ / 5


def test_unknown_model_falls_back_to_max_rates():
    assert llm_cost_for("mystery-model", 1000, 1000) == llm_cost_for("qwen-max", 1000, 1000)


def test_tier_labels():
    assert tier_label("qwen-flash") == "flash"
    assert tier_label("qwen-plus") == "plus"
    assert tier_label("qwen-max") == "max"
    assert tier_label(None) == "max"


def test_every_routed_model_has_rates():
    from app.services.model_router import MODEL_RATES
    for model in set(TASK_MODELS.values()):
        assert model in MODEL_RATES
