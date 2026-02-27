from pathlib import Path

import skill_registry


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_porting_pipeline_local_codebase_map_filters_non_production_and_surfaces_drivers(
    tmp_path, monkeypatch
):
    repo = tmp_path / "sample"

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
        repo / "contracts" / "StorageRouter.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        interface IFeed {
            function quote(uint256 amount) external view returns (uint256);
        }
        interface IERC20 {
            function transfer(address to, uint256 amount) external returns (bool);
            function transferFrom(address from, address to, uint256 amount) external returns (bool);
        }

        contract StorageRouter {
            mapping(address => uint256) public balances;
            mapping(address => uint256) public feeDebt;
            mapping(address => address) public operators;
            mapping(bytes32 => uint256) public checkpoints;
            mapping(address => bool) public isEnabled;
            address public implementation;

            function route(address feed, uint256 amount) external returns (uint256 out) {
                balances[msg.sender] += amount;
                feeDebt[msg.sender] += (amount / 100);
                out = IFeed(feed).quote(amount);
            }

            function settle(address token, address to, uint256 amount) external {
                IERC20(token).transfer(to, amount);
            }

            function pull(address token, address from, uint256 amount) external {
                IERC20(token).transferFrom(from, address(this), amount);
            }

            function upgrade(address newImpl) external {
                implementation = newImpl;
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
        repo / "tests" / "HighButIgnored.t.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        contract HighButIgnored {
            function bench(bytes memory data) external pure returns (bytes32 v) {
                for (uint256 i = 0; i < 256; i++) {
                    v = keccak256(abi.encodePacked(v, data, i));
                }
            }
        }
        """,
    )

    monkeypatch.chdir(repo)
    payload = skill_registry.run_skill_search(
        skill_registry.SKILL_ID_PORTING_AUDITOR,
        "Analyze ./contracts and identify high_stylus_benefit vs low_stylus_impact targets.",
    )

    analysis = payload.get("codebase_analysis") or {}
    assert analysis.get("mode") == "local_path"

    high_targets = analysis.get("high_targets") or []
    low_targets = analysis.get("low_targets") or []
    assert high_targets
    assert low_targets

    high_paths = [str(item.get("path") or "") for item in high_targets]
    low_paths = [str(item.get("path") or "") for item in low_targets]

    assert any("ComputeHeavy.sol" in path for path in high_paths)
    assert any("StorageRouter.sol" in path for path in low_paths)
    assert all("HighButIgnored.t.sol" not in path for path in [*high_paths, *low_paths])

    first_high = high_targets[0]
    assert isinstance(first_high.get("positive_drivers"), list)
    assert first_high["positive_drivers"]

    summary = str(analysis.get("summary") or "")
    assert "Top positive drivers:" in summary
    assert "Top risk drivers:" in summary

    action_paths = payload.get("analysis_action_paths") or []
    assert isinstance(action_paths, list)
    assert len(action_paths) >= 3
    assert payload.get("llm_augmentation_contract", {}).get("mode") == "bounded_second_pass"
