from augmentation_contract import (
    build_porting_augmentation_contract,
    compare_porting_analysis_with_augmentation,
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


def test_compare_porting_analysis_with_augmentation_promotes_low_target_with_bounds():
    static_analysis = {
        "high_targets": [
            {"path": "contracts/ComputeHeavy.sol", "hint_score": 80},
            {"path": "contracts/Hasher.sol", "hint_score": 75},
        ],
        "low_targets": [
            {"path": "contracts/Router.sol", "hint_score": 40},
        ],
    }
    validated = {
        "mode": "bounded_second_pass",
        "additional_good_fit_signals": [
            {
                "contract": "contracts/Router.sol",
                "signal": "compute-heavy path found during deep review",
                "confidence": "medium",
                "citations": ["https://example.com/router-note"],
            }
        ],
        "additional_bad_fit_signals": [],
        "recommended_carveouts": [],
        "validation": {"warnings": []},
    }

    result = compare_porting_analysis_with_augmentation(static_analysis, validated)
    augmented_high_paths = [item.get("path") for item in result["augmented"]["high_targets"]]
    augmented_low_paths = [item.get("path") for item in result["augmented"]["low_targets"]]

    assert result["mode"] == "bounded_second_pass"
    assert "contracts/Router.sol" in augmented_high_paths
    assert "contracts/Router.sol" not in augmented_low_paths
    assert result["quality_delta"]["promotions"] == 1
    assert "contracts/Router.sol" in result["quality_delta"]["high_targets_added"]
    assert result["augmented"]["applied_bounds"]["max_new_high_targets"] == 2


def test_compare_porting_analysis_with_augmentation_demotes_high_target_by_one_rank():
    static_analysis = {
        "high_targets": [
            {"path": "contracts/A.sol", "hint_score": 82},
            {"path": "contracts/B.sol", "hint_score": 79},
            {"path": "contracts/C.sol", "hint_score": 72},
        ],
        "low_targets": [],
    }
    validated = {
        "mode": "bounded_second_pass",
        "additional_good_fit_signals": [],
        "additional_bad_fit_signals": [
            {
                "contract": "contracts/A.sol",
                "signal": "hidden integration boundary",
                "confidence": "high",
                "citations": ["https://example.com/a-risk"],
            }
        ],
        "recommended_carveouts": [],
        "validation": {"warnings": []},
    }

    result = compare_porting_analysis_with_augmentation(static_analysis, validated)
    augmented_high_paths = [item.get("path") for item in result["augmented"]["high_targets"]]

    assert result["mode"] == "bounded_second_pass"
    assert augmented_high_paths == ["contracts/B.sol", "contracts/A.sol", "contracts/C.sol"]
    assert result["quality_delta"]["demotions"] == 1


def test_compare_porting_analysis_with_augmentation_keeps_static_on_fallback():
    static_analysis = {
        "high_targets": [{"path": "contracts/Compute.sol", "hint_score": 78}],
        "low_targets": [{"path": "contracts/Router.sol", "hint_score": 42}],
    }
    fallback = {
        "mode": "static_only_fallback",
        "validation": {"reason": "no_valid_cited_augmentation_claims", "warnings": []},
    }

    result = compare_porting_analysis_with_augmentation(static_analysis, fallback)

    assert result["mode"] == "static_only"
    assert result["quality_delta"]["promotions"] == 0
    assert result["quality_delta"]["demotions"] == 0
    assert result["quality_delta"]["reason"] == "no_valid_cited_augmentation_claims"
    assert result["augmented"]["high_targets"] == result["static"]["high_targets"]
    assert result["augmented"]["low_targets"] == result["static"]["low_targets"]
