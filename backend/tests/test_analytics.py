from types import SimpleNamespace
from app.routers.analytics import summarize_events, summarize_clips


def _ev(category, usd, qty=0, model=None, tin=0, tout=0):
    return SimpleNamespace(category=category, amount_usd=usd, quantity=qty,
                           model=model, input_tokens=tin, output_tokens=tout)


def test_savings_reprice_every_call_at_premium_rates():
    # 10k in / 2k out on flash costs cents; on qwen-max it would cost dollars
    events = [_ev("llm", 0.0013, 12000, "qwen-flash", 10000, 2000)]
    llm = summarize_events(events)["llm"]
    assert llm["total_usd"] == 0.0013
    assert llm["all_premium_usd"] == round(10 * 0.0016 + 2 * 0.0064, 4)
    assert llm["saved_usd"] == round(llm["all_premium_usd"] - 0.0013, 4)
    assert llm["cheap_share"] == 1.0


def test_premium_models_do_not_count_as_cheap():
    events = [
        _ev("llm", 0.5, 5000, "qwen-max", 4000, 1000),
        _ev("llm", 0.01, 5000, "qwen-flash", 4000, 1000),
        _ev("llm", 0.4, 5000, "qwen-vl-max", 4000, 1000),
    ]
    llm = summarize_events(events)["llm"]
    assert llm["cheap_share"] == round(5000 / 15000, 4)
    # by_model sorted by tokens, stable content
    assert {r["model"] for r in llm["by_model"]} == {"qwen-max", "qwen-flash", "qwen-vl-max"}


def test_categories_accumulate_usd_and_native_units():
    events = [
        _ev("video", 0.75, 5), _ev("video", 1.5, 10),
        _ev("image", 0.05, 1), _ev("tts", 0.02, 800),
    ]
    cats = summarize_events(events)["categories"]
    assert cats["video"]["usd"] == 2.25 and cats["video"]["quantity"] == 15.0
    assert cats["image"]["quantity"] == 1.0
    assert cats["tts"]["quantity"] == 800.0


def test_media_categories_break_down_by_model():
    events = [
        _ev("video", 0.75, 5, model="wan2.7"),
        _ev("video", 1.08, 10, model="happyhorse-1.1"),
        _ev("video", 0.54, 5),  # old row, no model recorded
        _ev("image", 0.05, 1, model="wan2.6-t2i"),
        _ev("tts", 0.02, 800, model="qwen3-tts-flash"),
    ]
    cats = summarize_events(events)["categories"]
    vm = cats["video"]["by_model"]
    assert vm["wan2.7"] == {"usd": 0.75, "quantity": 5.0}
    assert vm["happyhorse-1.1"]["quantity"] == 10.0
    assert vm["untracked"]["usd"] == 0.54  # never fabricated onto a model
    assert cats["image"]["by_model"]["wan2.6-t2i"]["quantity"] == 1.0
    assert cats["tts"]["by_model"]["qwen3-tts-flash"]["quantity"] == 800.0


def _clip(status="APPROVED", model="wan", retries=0, face=0.9):
    # face_score is persisted as a 0–1 cosine similarity (see continuity_agent)
    return SimpleNamespace(status=status, model_used=model, retries=retries,
                           face_score=face)


def test_reliability_rates():
    clips = [
        _clip("APPROVED", "wan", 0, 0.92),
        _clip("NEEDS_REVIEW", "happyhorse", 1, 0.60),
        _clip("APPROVED", "happyhorse", 0, 0.88),
        _clip("PENDING", "happyhorse", 0, None),  # not judged yet
    ]
    r = summarize_clips(clips)
    assert r["clips_total"] == 4
    assert r["continuity_pass_rate"] == round(2 / 3, 4)
    assert r["flagged"] == 1
    assert r["avg_face_score"] == 80.0  # scaled to 0–100 for the dashboard
    assert r["by_tier"]["wan"]["retry_rate"] == 0.0
    assert r["by_tier"]["happyhorse"]["retry_rate"] == round(1 / 3, 4)


def test_empty_inputs_are_safe():
    llm = summarize_events([])["llm"]
    assert llm["saved_usd"] == 0.0 and llm["cheap_share"] == 0.0
    r = summarize_clips([])
    assert r["continuity_pass_rate"] is None and r["avg_face_score"] is None
