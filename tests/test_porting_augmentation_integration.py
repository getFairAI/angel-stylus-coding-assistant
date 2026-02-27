from pathlib import Path

from augmentation_contract import (
    build_porting_augmentation_contract,
    compare_porting_analysis_with_augmentation,
    validate_porting_augmentation,
)
import skill_registry


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_static_vs_augmentation_quality_delta_is_bounded(tmp_path, monkeypatch):
    repo = tmp_path / "sample"

    _write(
        repo / "contracts" / "ComputeHeavy.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        contract ComputeHeavy {
            function verify(bytes32[] memory leaves) external pure returns (bytes32 h) {
                for (uint256 i = 0; i < leaves.length; i++) {
                    h = keccak256(abi.encodePacked(h, leaves[i], i));
                }
            }
        }
        """,
    )
    _write(
        repo / "contracts" / "Router.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        interface IERC20 {
            function transfer(address to, uint256 amount) external returns (bool);
        }

        contract Router {
            mapping(address => uint256) public balances;
            address public implementation;

            function settle(address token, address to, uint256 amount) external {
                balances[msg.sender] += amount;
                IERC20(token).transfer(to, amount);
            }

            function execute(bytes calldata data) external returns (bytes memory out) {
                (bool ok, bytes memory response) = implementation.delegatecall(data);
                require(ok, "delegatecall failed");
                return response;
            }
        }
        """,
    )

    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        skill_registry,
        "retrieve_stylus_context",
        lambda _prompt, include_research_contract=False, max_chars=10000, session_id=None: {
            "found": True,
            "context": "retrieval context",
            "references": [],
        },
    )

    payload = skill_registry.run_skill_search(
        skill_registry.SKILL_ID_PORTING_AUDITOR,
        "Analyze ./contracts and identify high_stylus_benefit vs low_stylus_impact targets.",
    )
    analysis = payload.get("codebase_analysis") or {}

    contract = build_porting_augmentation_contract()
    validated = validate_porting_augmentation(
        {
            "additional_good_fit_signals": [
                {
                    "contract": "contracts/Router.sol",
                    "signal": "isolated compute subpath should be piloted",
                    "confidence": "medium",
                    "citations": ["https://example.com/router-pilot"],
                }
            ],
            "additional_bad_fit_signals": [],
            "recommended_carveouts": [],
            "confidence": "medium",
            "citations": ["https://example.com/summary"],
        },
        contract=contract,
    )
    comparison = compare_porting_analysis_with_augmentation(
        analysis,
        validated,
        contract=contract,
    )

    max_new = int(contract["ranking_influence_bounds"]["max_new_high_targets"])
    max_shift = int(contract["ranking_influence_bounds"]["max_rank_shift"])

    assert comparison["mode"] == "bounded_second_pass"
    assert comparison["quality_delta"]["promotions"] <= max_new
    assert comparison["quality_delta"]["demotions"] <= max_shift
    assert comparison["quality_delta"]["augmented_high_count"] >= comparison["quality_delta"]["static_high_count"]
