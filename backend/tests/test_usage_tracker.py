from app.services.usage_tracker import UsageTracker


def test_accumulates_tokens_and_cost():
    t = UsageTracker(input_per_1k=0.0016, output_per_1k=0.0064)
    t.add(prompt_tokens=1000, completion_tokens=500)
    t.add(prompt_tokens=2000, completion_tokens=1000)
    assert t.total_input == 3000
    assert t.total_output == 1500
    assert round(t.cost_usd, 6) == round(3 * 0.0016 + 1.5 * 0.0064, 6)


def test_snapshot_shape():
    t = UsageTracker(input_per_1k=0.0016, output_per_1k=0.0064)
    t.add(prompt_tokens=1000, completion_tokens=1000)
    snap = t.snapshot()
    assert snap["input_tokens"] == 1000
    assert snap["output_tokens"] == 1000
    assert "cost_usd" in snap


def test_handles_none():
    t = UsageTracker(input_per_1k=0.0016, output_per_1k=0.0064)
    t.add(prompt_tokens=None, completion_tokens=None)
    assert t.total_input == 0
    assert t.total_output == 0
