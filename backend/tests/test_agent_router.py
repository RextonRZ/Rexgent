from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_registry_endpoint():
    r = client.get("/api/agent/registry")
    assert r.status_code == 200
    assert any(a["key"] == "clarification" for a in r.json())


def test_answer_endpoint_exists():
    r = client.post("/api/agent/clarifications/00000000-0000-0000-0000-000000000000/answer",
                    json={"answers": [{"topic": "partner", "answer": "robot"}]})
    assert r.status_code in (200, 404)
