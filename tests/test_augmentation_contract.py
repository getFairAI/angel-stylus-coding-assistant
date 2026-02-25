from augmentation_contract import (
    build_porting_augmentation_contract,
    render_porting_augmentation_contract,
    validate_porting_augmentation,
)


def test_porting_augmentation_contract_builder_and_renderer():
    contract = build_porting_augmentation_contract()
    rendered = render_porting_augmentation_contract(contract)

    assert contract["mode"] == "bounded_second_pass"
    assert contract["validation_rules"]["on_validation_failure"] == "fallback_static_only"
    assert "LLM augmentation contract:" in rendered


def test_validate_porting_augmentation_enforces_bounds_and_keeps_valid_claims():
    contract = build_porting_augmentation_contract()
    payload = {
        "additional_good_fit_signals": [
            {
                "contract": "A.sol",
                "signal": "heavy hashing path",
                "confidence": "high",
                "citations": ["https://example.com/a"],
            },
            {
                "contract": "B.sol",
                "signal": "proof verification loops",
                "confidence": "medium",
                "citations": ["https://example.com/b"],
            },
            {
                "contract": "C.sol",
                "signal": "memory-heavy transforms",
                "confidence": "high",
                "citations": ["https://example.com/c"],
            },
        ],
        "additional_bad_fit_signals": [],
        "recommended_carveouts": [
            {
                "contract": "D.sol",
                "recommendation": "keep boundary router in solidity",
                "rationale": "high external call fanout",
                "confidence": "medium",
                "citations": ["https://example.com/d"],
            }
        ],
        "confidence": "high",
        "citations": ["https://example.com/overview"],
    }

    result = validate_porting_augmentation(payload, contract=contract)

    assert result["mode"] == "bounded_second_pass"
    assert len(result["additional_good_fit_signals"]) == 2
    assert result["validation"]["status"] == "valid"
    assert result["validation"]["applied_bounds"]["max_new_high_targets"] == 2


def test_validate_porting_augmentation_falls_back_on_schema_missing_keys():
    result = validate_porting_augmentation({"confidence": "high"})
    assert result["mode"] == "static_only_fallback"
    assert "schema_missing_required_keys" in result["validation"]["reason"]


def test_validate_porting_augmentation_marks_conflicts_low_confidence():
    payload = {
        "additional_good_fit_signals": [
            {
                "contract": "Vault.sol",
                "signal": "compute-heavy accounting path",
                "confidence": "high",
                "citations": ["https://example.com/good"],
            }
        ],
        "additional_bad_fit_signals": [
            {
                "contract": "Vault.sol",
                "signal": "coupled upgrade boundary",
                "confidence": "high",
                "citations": ["https://example.com/bad"],
            }
        ],
        "recommended_carveouts": [],
        "confidence": "medium",
        "citations": ["https://example.com/overview"],
    }

    result = validate_porting_augmentation(payload)

    assert result["mode"] == "bounded_second_pass"
    assert result["additional_good_fit_signals"][0]["confidence"] == "low"
    assert result["additional_bad_fit_signals"][0]["confidence"] == "low"
    assert any("conflicting_good_and_bad_signals_detected" in item for item in result["validation"]["warnings"])


def test_validate_porting_augmentation_drops_uncited_and_falls_back_when_empty():
    payload = {
        "additional_good_fit_signals": [
            {
                "contract": "Token.sol",
                "signal": "fast path",
                "confidence": "high",
                "citations": [],
            }
        ],
        "additional_bad_fit_signals": [],
        "recommended_carveouts": [],
        "confidence": "medium",
        "citations": ["https://example.com/overview"],
    }

    result = validate_porting_augmentation(payload)

    assert result["mode"] == "static_only_fallback"
    assert result["validation"]["reason"] == "no_valid_cited_augmentation_claims"
    assert result["validation"]["dropped_items"] == 1
