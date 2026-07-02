from unittest.mock import patch, MagicMock

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


def test_record_usage_writes_llm_event_when_project_set():
    from app.services.usage_tracker import record_usage, current_project
    usage = MagicMock(prompt_tokens=1000, completion_tokens=1000)
    token = current_project.set(("p1", MagicMock()))  # (project_id, db)
    try:
        with patch("app.services.cost_ledger.record_llm") as m:
            record_usage(usage)
            m.assert_called_once()
    finally:
        current_project.reset(token)
