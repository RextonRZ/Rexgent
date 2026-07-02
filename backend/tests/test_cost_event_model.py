from app.models.cost_event import CostEvent


def test_cost_event_columns():
    cols = CostEvent.__table__.columns.keys()
    for c in ["id", "project_id", "category", "stage", "unit", "quantity",
              "amount_usd", "ref_id", "created_at"]:
        assert c in cols
