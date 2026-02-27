from pathlib import Path

import skill_registry


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _stub_retrieval(monkeypatch):
    monkeypatch.setattr(
        skill_registry,
        "retrieve_stylus_context",
        lambda _prompt, include_research_contract=False, max_chars=10000, session_id=None: {
            "found": True,
            "context": "holdout-fixture retrieval context",
            "references": [],
        },
    )


def _build_holdout_repo(repo: Path):
    _write(
        repo / "contracts" / "MerkleFold.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        contract MerkleFold {
            function fold(bytes32[] memory leaves) external pure returns (bytes32 h) {
                for (uint256 i = 0; i < leaves.length; i++) {
                    h = keccak256(abi.encodePacked(h, leaves[i], i));
                }
            }
        }
        """,
    )
    _write(
        repo / "contracts" / "BatchHasher.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        contract BatchHasher {
            function hashN(bytes32 seed, uint256 rounds) external pure returns (bytes32 out) {
                out = seed;
                for (uint256 i = 0; i < rounds; i++) {
                    out = sha256(abi.encodePacked(out, i));
                }
            }
        }
        """,
    )
    _write(
        repo / "contracts" / "ExecutionHub.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        interface IFeed {
            function quote(uint256 amount) external view returns (uint256);
        }
        interface IFeeCollector {
            function collect(address user, uint256 fee) external;
        }
        interface IERC20 {
            function transfer(address to, uint256 amount) external returns (bool);
            function transferFrom(address from, address to, uint256 amount) external returns (bool);
        }

        contract ExecutionHub {
            mapping(address => uint256) public balances;
            mapping(address => uint256) public feeDebt;
            mapping(address => address) public operators;
            mapping(bytes32 => uint256) public checkpoints;
            mapping(address => bool) public isEnabled;
            address public implementation;

            function route(address feed, address collector, uint256 amount) external returns (uint256 out) {
                balances[msg.sender] += amount;
                feeDebt[msg.sender] += (amount / 100);
                out = IFeed(feed).quote(amount);
                IFeeCollector(collector).collect(msg.sender, feeDebt[msg.sender]);
            }

            function settle(address token, address to, uint256 amount) external {
                IERC20(token).transfer(to, amount);
            }

            function pull(address token, address from, uint256 amount) external {
                IERC20(token).transferFrom(from, address(this), amount);
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
    _write(
        repo / "benchmarks" / "BenchOnly.sol",
        """
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        contract BenchOnly {
            function burnCpu(bytes32 seed) external pure returns (bytes32 out) {
                out = seed;
                for (uint256 i = 0; i < 500; i++) {
                    out = keccak256(abi.encodePacked(out, i));
                }
            }
        }
        """,
    )


def _collect_target_names(items) -> list[str]:
    names = []
    for item in items or []:
        value = str(item.get("path") or "")
        names.append(Path(value).name)
    return names


def test_porting_acceptance_holdout_fixture_meets_ranking_gate(tmp_path, monkeypatch):
    repo = tmp_path / "holdout"
    _build_holdout_repo(repo)
    _stub_retrieval(monkeypatch)
    monkeypatch.chdir(repo)

    payload = skill_registry.run_skill_search(
        skill_registry.SKILL_ID_PORTING_AUDITOR,
        "Analyze ./contracts and identify high_stylus_benefit vs low_stylus_impact targets.",
    )
    analysis = payload.get("codebase_analysis") or {}
    high_targets = analysis.get("high_targets") or []
    low_targets = analysis.get("low_targets") or []
    high_names = _collect_target_names(high_targets)
    low_names = _collect_target_names(low_targets)

    assert analysis.get("mode") == "local_path"
    assert "MerkleFold.sol" in high_names
    assert "BatchHasher.sol" in high_names
    assert "ExecutionHub.sol" in low_names
    assert "BenchOnly.sol" not in [*high_names, *low_names]

    high_scores = [int(item.get("hint_score") or 0) for item in high_targets]
    low_scores = [int(item.get("hint_score") or 0) for item in low_targets]
    assert high_scores
    assert low_scores
    assert high_scores == sorted(high_scores, reverse=True)
    assert low_scores == sorted(low_scores)
    assert all(score >= 65 for score in high_scores)
    assert all(score <= 45 for score in low_scores)
    assert min(high_scores) > max(low_scores)


def test_porting_acceptance_holdout_prompt_paraphrases_keep_target_sets_stable(tmp_path, monkeypatch):
    repo = tmp_path / "holdout"
    _build_holdout_repo(repo)
    _stub_retrieval(monkeypatch)
    monkeypatch.chdir(repo)

    prompts = [
        "Analyze ./contracts and identify high_stylus_benefit vs low_stylus_impact targets.",
        "For ./contracts, classify high_stylus_benefit candidates and low_stylus_impact defer candidates.",
        "Evaluate (./contracts) for stylus migration fit and split into high-benefit and low-impact buckets.",
    ]

    signatures = []
    for prompt in prompts:
        payload = skill_registry.run_skill_search(skill_registry.SKILL_ID_PORTING_AUDITOR, prompt)
        analysis = payload.get("codebase_analysis") or {}
        high_names = _collect_target_names(analysis.get("high_targets"))
        low_names = _collect_target_names(analysis.get("low_targets"))
        signatures.append((tuple(high_names), tuple(low_names)))

    assert len(set(signatures)) == 1
