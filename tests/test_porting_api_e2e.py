from pathlib import Path

from fastapi.testclient import TestClient

import main as app_module
import skill_registry


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_porting_audit_endpoint_e2e_local_codebase(monkeypatch, tmp_path):
    repo = tmp_path / "sample"
    (repo / "logs").mkdir(parents=True, exist_ok=True)

    _write(
        repo / "contracts" / "ComputeHeavy.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        contract ComputeHeavy {
            function verify(bytes32[] memory leaves) external pure returns (bytes32 h) {
                h = keccak256(abi.encodePacked(uint256(1)));
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
        lambda _prompt, include_research_contract=False, max_chars=10000: {
            "found": True,
            "context": "retrieved references context",
            "references": [],
        },
    )

    client = TestClient(app_module.app)
    response = client.post(
        "/stylus-porting-audit",
        json={
            "prompt": "Analyze ./contracts and identify high_stylus_benefit vs low_stylus_impact targets.",
            "augmentation": {
                "additional_good_fit_signals": [],
                "additional_bad_fit_signals": [],
                "recommended_carveouts": [],
                "confidence": "low",
                "citations": ["https://example.com/summary"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["skill"] == skill_registry.SKILL_ID_PORTING_AUDITOR
    assert payload["codebase_analysis"]["mode"] == "local_path"
    assert payload["llm_augmentation_contract"]["mode"] == "bounded_second_pass"
    assert payload["analysis_action_paths"]

    high_paths = [str(item.get("path") or "") for item in payload["codebase_analysis"]["high_targets"]]
    assert any("ComputeHeavy.sol" in path for path in high_paths)
    assert int(payload["codebase_analysis"]["aggregate"]["files"]) >= 2
