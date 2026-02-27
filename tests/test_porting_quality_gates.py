from pathlib import Path

import skill_registry


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _target_names(items) -> set:
    names = set()
    for item in items or []:
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        names.add(Path(path).name)
    return names


def _bucket_quality_score(high_names: set, low_names: set, expected_high: set, expected_low: set) -> int:
    score = 0
    for name in expected_high:
        if name in high_names:
            score += 2
        elif name in low_names:
            score -= 2

    for name in expected_low:
        if name in low_names:
            score += 1
        elif name in high_names:
            score -= 1

    return score


def test_static_plus_augmentation_improves_quality_on_labeled_fixture(tmp_path, monkeypatch):
    repo = tmp_path / "quality-fixture"

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
    _write(
        repo / "contracts" / "TokenLedger.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        interface IERC20 {
            function transfer(address to, uint256 amount) external returns (bool);
        }

        contract TokenLedger {
            mapping(address => uint256) public balances;
            IERC20 public token;

            constructor(IERC20 token_) {
                token = token_;
            }

            function payout(address to, uint256 amount) external {
                balances[msg.sender] -= amount;
                token.transfer(to, amount);
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

    prompt = "Analyze ./contracts and identify high_stylus_benefit vs low_stylus_impact targets."
    expected_high = {"ComputeHeavy.sol", "Router.sol"}
    expected_low = {"TokenLedger.sol"}

    static_payload = skill_registry.run_skill_search(
        skill_registry.SKILL_ID_PORTING_AUDITOR,
        prompt,
    )
    static_analysis = static_payload.get("codebase_analysis") or {}
    static_high = _target_names(static_analysis.get("high_targets"))
    static_low = _target_names(static_analysis.get("low_targets"))
    static_score = _bucket_quality_score(static_high, static_low, expected_high, expected_low)

    augmented_payload = skill_registry.run_skill_search(
        skill_registry.SKILL_ID_PORTING_AUDITOR,
        prompt,
        augmentation={
            "additional_good_fit_signals": [
                {
                    "contract": "contracts/Router.sol",
                    "signal": "isolated compute path worth pilot despite boundary complexity",
                    "confidence": "medium",
                    "citations": ["https://example.com/router-pilot"],
                }
            ],
            "additional_bad_fit_signals": [],
            "recommended_carveouts": [],
            "confidence": "medium",
            "citations": ["https://example.com/summary"],
        },
    )

    augmented_analysis = augmented_payload.get("codebase_analysis_augmented") or {}
    augmented_high = _target_names(augmented_analysis.get("high_targets"))
    augmented_low = _target_names(augmented_analysis.get("low_targets"))
    augmented_score = _bucket_quality_score(augmented_high, augmented_low, expected_high, expected_low)

    comparison = augmented_payload.get("augmentation_comparison") or {}
    delta = comparison.get("quality_delta") or {}

    assert comparison.get("mode") == "bounded_second_pass"
    assert augmented_score > static_score
    assert int(delta.get("promotions") or 0) >= 1
    assert int(delta.get("promotions") or 0) <= 2
