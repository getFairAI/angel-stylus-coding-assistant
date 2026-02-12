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


def test_openrouter_proxy_requires_backend_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = TestClient(app_module.app)
    response = client.post(
        "/openrouter/chat/completions",
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OPENROUTER_API_KEY is not configured on the backend."


def test_openrouter_proxy_passthrough_success(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self):
            return {"id": "ok", "choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(app_module.requests, "post", fake_post)

    client = TestClient(app_module.app)
    payload = {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hello"}]}
    response = client.post("/openrouter/chat/completions", json=payload)

    assert response.status_code == 200
    assert response.json()["id"] == "ok"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "openai/gpt-4o-mini"
    assert captured["json"]["messages"][0]["content"] == "hello"
