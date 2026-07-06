from app.services.budget_estimator import estimate_scope, estimate_budget


def test_scope_scales_with_episodes_and_length():
    small = estimate_scope(1, 30)
    big = estimate_scope(4, 60)
    assert big["video_seconds"] > small["video_seconds"]
    assert big["shots"] > small["shots"]
    assert small["scenes"] >= 1


def test_budget_has_credit_and_tokens():
    est = estimate_budget(1, 30, characters=4)
    assert est["credit_usd"] > 0
    assert est["llm_tokens"] > 0
    # credit breakdown adds up to the headline (within rounding)
    parts = est["credit_breakdown"]
    assert abs(sum(parts.values()) - est["credit_usd"]) < 0.05


def test_bigger_drama_costs_more_credit_and_tokens():
    small = estimate_budget(1, 30)
    big = estimate_budget(3, 60)
    assert big["credit_usd"] > small["credit_usd"]
    assert big["llm_tokens"] > small["llm_tokens"]


def test_more_characters_raise_image_spend():
    few = estimate_budget(1, 30, characters=2)
    many = estimate_budget(1, 30, characters=8)
    assert many["credit_breakdown"]["image"] > few["credit_breakdown"]["image"]


def test_zero_or_negative_scope_is_clamped():
    est = estimate_budget(0, 0, characters=0)
    assert est["scope"]["episodes"] == 1
    assert est["credit_usd"] > 0
