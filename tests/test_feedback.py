from fastapi.testclient import TestClient

import main as app_module


def test_feedback_endpoint_accepts_thumbsup_and_logs(monkeypatch, tmp_path):
    # Point logs to a temp dir to keep test isolated.
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    client = TestClient(app_module.app)
    payload = {
        "prompt": "What is Stylus?",
        "response": "Stylus is the Arbitrum WASM execution engine...",
        "rating": 1,
        "skill": "sift-stylus-research",
        "metadata": {"ui": "web"},
    }

    res = client.post("/feedback", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["stored"] is True
    assert body["feedback_id"]


def test_feedback_rejects_out_of_range_rating():
    client = TestClient(app_module.app)
    payload = {
        "prompt": "test",
        "response": "ok",
        "rating": 5,
    }

    res = client.post("/feedback", json=payload)
    assert res.status_code == 422

