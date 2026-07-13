from unittest.mock import MagicMock, patch
from app.services import cost_ledger


def test_aggregate_sums_by_category():
    rows = [MagicMock(category="video", amount_usd=5.4, stage="generation"),
            MagicMock(category="image", amount_usd=0.9, stage="casting"),
            MagicMock(category="video", amount_usd=0.6, stage="generation")]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    out = cost_ledger.aggregate(db, "p1", budget=40.0)
    assert out["by_category"]["video"] == 6.0
    assert out["grand_total"] == 6.9
    assert out["within_budget"] is True
    assert out["remaining"] == 33.1


def _llm_row(stage, model, tin, tout, usd):
    return MagicMock(category="llm", stage=stage, model=model,
                     input_tokens=tin, output_tokens=tout,
                     quantity=tin + tout, amount_usd=usd)


def test_aggregate_llm_tokens_by_model_and_stage():
    rows = [_llm_row("script", "qwen-max", 3000, 1500, 0.0144),
            _llm_row("structure", "qwen-flash", 4000, 1000, 0.0006),
            _llm_row("structure", "qwen-flash", 2000, 500, 0.0003)]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    out = cost_ledger.aggregate(db, "p1", budget=40.0)
    llm = out["llm"]
    assert llm["input_tokens"] == 9000
    assert llm["output_tokens"] == 3000
    assert llm["total_tokens"] == 12000
    assert llm["by_model"]["qwen-flash"]["tokens"] == 7500
    assert llm["by_model"]["qwen-max"]["tokens"] == 4500
    assert llm["tokens_by_stage"]["structure"] == 7500


def test_record_llm_prices_by_model():
    db = MagicMock()
    with patch("app.services.cost_ledger.emit"):
        cheap = cost_ledger.record_llm(db, "p1", 10_000, 2_000, stage="structure",
                                       model="qwen-flash")
        pricey = cost_ledger.record_llm(db, "p1", 10_000, 2_000, stage="script",
                                        model="qwen-max")
    assert cheap < pricey / 5
    ev = db.add.call_args_list[0][0][0]
    assert ev.model == "qwen-flash"
    assert ev.input_tokens == 10_000
    assert ev.output_tokens == 2_000
    assert ev.stage == "structure"


def test_record_video_computes_amount():
    db = MagicMock()
    with patch("app.services.cost_ledger.emit"):
        amt = cost_ledger.record_video(db, "p1", seconds=5, model="wan", ref_id="clip1")
    assert amt == 0.75
    db.add.assert_called_once()


def test_record_video_wan_r2v_bills_and_labels_as_wan():
    db = MagicMock()
    with patch("app.services.cost_ledger.emit"):
        amt = cost_ledger.record_video(db, "p1", seconds=5, model="wan_r2v", ref_id="clip1")
    # bills at the wan rate, and groups under the wan2.7 analytics label
    assert amt == 0.75
    ev = db.add.call_args[0][0]
    assert ev.model == "wan2.7"
