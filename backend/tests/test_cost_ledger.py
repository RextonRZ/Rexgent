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


def test_record_video_computes_amount():
    db = MagicMock()
    with patch("app.services.cost_ledger.emit"):
        amt = cost_ledger.record_video(db, "p1", seconds=5, model="wan", ref_id="clip1")
    assert amt == 0.75
    db.add.assert_called_once()
