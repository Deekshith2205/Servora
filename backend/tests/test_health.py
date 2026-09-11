from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_endpoint_runs_end_to_end():
    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "reply" in body
    assert body["status"] in ("resolved", "escalated")
    assert len(body["trace"]) > 0
