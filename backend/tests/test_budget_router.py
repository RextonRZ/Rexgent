from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ledger_endpoint_returns_aggregate():
    with patch("app.routers.budget.aggregate", return_value={"grand_total": 1.0, "by_category": {}}):
        r = client.get("/api/budget/ledger/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 200
    assert r.json()["grand_total"] == 1.0
