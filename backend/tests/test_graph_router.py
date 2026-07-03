from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
ZERO = "00000000-0000-0000-0000-000000000000"


def test_graph_endpoint_returns_characters_list():
    r = client.get(f"/api/graph/{ZERO}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("characters"), list)
    assert "relationships" in data and "scenes" in data
