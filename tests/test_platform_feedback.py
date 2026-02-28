import json

from fastapi.testclient import TestClient

import main as app_module


def test_platform_feedback_logs_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    client = TestClient(app_module.app)
    payload = {
        "message": "The toolbox button is hard to find",
        "source": "web",
    }

    response = client.post("/platform-feedback", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["feedback_id"]

    log_path = tmp_path / "platform_feedback.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["message"] == payload["message"]
    assert entry["source"] == payload["source"]


def test_admin_platform_feedback_pagination(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_BEARER_TOKEN", "admin-secret")
    monkeypatch.setenv("ADMIN_HASHED_PASSWORD", app_module.hash_password("hunter2"))

    client = TestClient(app_module.app)
    messages = ["first entry", "follow-up", "another note"]
    for text in messages:
        client.post("/platform-feedback", json={"message": text})

    auth = client.post("/admin/auth", json={"password": "hunter2"})
    assert auth.status_code == 200
    token = auth.json()["token"]

    response = client.get("/admin/platform-feedback", headers={"Authorization": f"Bearer {token}"}, params={"limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["next_offset"] == 1
    assert body["has_more"] is True
    assert len(body["feedback"]) == 1
    assert body["feedback"][0]["message"] == messages[0]
