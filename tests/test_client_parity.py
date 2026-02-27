from fastapi.testclient import TestClient

import main as app_module


def test_research_alias_and_skill_route_are_payload_equivalent(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "run_skill_search",
        lambda skill_id, prompt, augmentation=None: {
            "skill": skill_id,
            "prompt": prompt,
            "augmentation": augmentation,
            "found": True,
            "context": "ok",
            "references": [],
        },
    )
    client = TestClient(app_module.app)
    prompt = "latest stylus tools"

    alias_response = client.post("/stylus-chat", json={"prompt": prompt})
    skill_response = client.post(
        "/skills/sift-stylus-research/search",
        json={"prompt": prompt},
    )

    assert alias_response.status_code == 200
    assert skill_response.status_code == 200
    assert alias_response.json() == skill_response.json()


def test_porting_alias_and_skill_route_are_payload_equivalent_with_augmentation(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "run_skill_search",
        lambda skill_id, prompt, augmentation=None: {
            "skill": skill_id,
            "prompt": prompt,
            "augmentation": augmentation,
            "found": True,
            "context": "ok",
            "references": [],
        },
    )
    client = TestClient(app_module.app)
    body = {
        "prompt": "Analyze ./contracts",
        "augmentation": {
            "additional_good_fit_signals": [],
            "additional_bad_fit_signals": [],
            "recommended_carveouts": [],
            "confidence": "low",
            "citations": ["https://example.com/summary"],
        },
    }

    alias_response = client.post("/stylus-porting-audit", json=body)
    skill_response = client.post(
        "/skills/sift-stylus-porting-auditor/search",
        json=body,
    )

    assert alias_response.status_code == 200
    assert skill_response.status_code == 200
    assert alias_response.json() == skill_response.json()
