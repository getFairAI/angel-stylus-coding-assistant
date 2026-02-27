import json
from pathlib import Path
import time

import contract_analysis
import skill_registry


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_snapshot_fixture() -> dict:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "porting_baseline_snapshot.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _build_local_repo(repo: Path) -> None:
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


def _snapshot_from_payload(payload: dict) -> dict:
    analysis = payload.get("codebase_analysis") or {}
    aggregate = analysis.get("aggregate") or {}
    hints = aggregate.get("hints") or {}
    high_targets = analysis.get("high_targets") or []
    low_targets = analysis.get("low_targets") or []

    high_top = Path(str(high_targets[0].get("path") or "")).name if high_targets else ""
    low_top = Path(str(low_targets[0].get("path") or "")).name if low_targets else ""

    return {
        "mode": str(analysis.get("mode") or ""),
        "files": int(aggregate.get("files") or 0),
        "contracts": int(aggregate.get("contracts") or 0),
        "final_hint": int(hints.get("final") or 0),
        "high_top": high_top,
        "low_top": low_top,
    }


def test_porting_baseline_prompt_suite_matches_snapshots(tmp_path, monkeypatch):
    fixture = _load_snapshot_fixture()
    repo = tmp_path / "baseline"
    _build_local_repo(repo)
    monkeypatch.chdir(repo)
    contract_analysis._ANALYSIS_CACHE.clear()

    monkeypatch.setattr(
        skill_registry,
        "retrieve_stylus_context",
        lambda _prompt, include_research_contract=False, max_chars=10000, session_id=None: {
            "found": True,
            "context": "baseline retrieval context",
            "references": [],
        },
    )

    github_blob_prompt = (
        "Analyze https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Pool.sol and return a porting verdict."
    )
    github_repo_prompt = (
        "Analyze https://github.com/gmx-io/gmx-contracts and identify high_stylus_benefit vs low_stylus_impact targets."
    )

    blob_target = contract_analysis._extract_github_target_from_prompt(github_blob_prompt) or {}
    repo_target = contract_analysis._extract_github_target_from_prompt(github_repo_prompt) or {}
    github_snapshot = {
        "github_blob": {
            "mode": str(blob_target.get("mode") or ""),
            "owner": str(blob_target.get("owner") or ""),
            "repo": str(blob_target.get("repo") or ""),
            "subpath": str(blob_target.get("subpath") or ""),
        },
        "github_repo": {
            "mode": str(repo_target.get("mode") or ""),
            "owner": str(repo_target.get("owner") or ""),
            "repo": str(repo_target.get("repo") or ""),
            "subpath": str(repo_target.get("subpath") or ""),
        },
    }

    local_file_prompt = "Analyze ./contracts/ComputeHeavy.sol and return a porting verdict."
    local_dir_prompt = "Analyze ./contracts and identify high_stylus_benefit vs low_stylus_impact targets."

    file_payload = skill_registry.run_skill_search(
        skill_registry.SKILL_ID_PORTING_AUDITOR,
        local_file_prompt,
    )
    dir_start = time.perf_counter()
    dir_payload_first = skill_registry.run_skill_search(
        skill_registry.SKILL_ID_PORTING_AUDITOR,
        local_dir_prompt,
    )
    dir_first_duration = time.perf_counter() - dir_start

    dir_start = time.perf_counter()
    dir_payload_second = skill_registry.run_skill_search(
        skill_registry.SKILL_ID_PORTING_AUDITOR,
        local_dir_prompt,
    )
    dir_second_duration = time.perf_counter() - dir_start

    local_snapshot = {
        "local_file": _snapshot_from_payload(file_payload),
        "local_dir": _snapshot_from_payload(dir_payload_first),
        "cache_behavior": {
            "local_dir_first_cache_hit": bool(
                (dir_payload_first.get("codebase_analysis") or {}).get("cache_hit")
            ),
            "local_dir_second_cache_hit": bool(
                (dir_payload_second.get("codebase_analysis") or {}).get("cache_hit")
            ),
        },
    }

    assert github_snapshot["github_blob"] == fixture["github_blob"]
    assert github_snapshot["github_repo"] == fixture["github_repo"]
    assert local_snapshot["local_file"] == fixture["local_file"]
    assert local_snapshot["local_dir"] == fixture["local_dir"]
    assert local_snapshot["cache_behavior"] == fixture["cache_behavior"]
    assert dir_second_duration <= (dir_first_duration * 1.2)
