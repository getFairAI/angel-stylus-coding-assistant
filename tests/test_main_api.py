from fastapi.testclient import TestClient

import main as app_module


def test_health_endpoint():
    client = TestClient(app_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stylus_chat_validates_empty_prompt():
    client = TestClient(app_module.app)
    response = client.post("/stylus-chat", json={"prompt": ""})
    assert response.status_code == 422


def test_stylus_chat_handles_internal_error_with_safe_response(monkeypatch):
    def raise_error(_prompt):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "retrieve_stylus_context", raise_error)
    client = TestClient(app_module.app)
    response = client.post("/stylus-chat", json={"prompt": "test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is False
    assert payload["reason"] == "Retrieval failed due to an internal error."
    assert payload["references"] == []
    assert payload["agent_guidance"]["behavior"] == "references_first"
