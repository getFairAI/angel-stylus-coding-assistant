from pathlib import Path

import contract_analysis


def test_parse_github_target_repo_url():
    parsed = contract_analysis.parse_github_target_url(
        "https://github.com/acme-defi/core-contracts"
    )
    assert parsed is not None
    assert parsed["mode"] == "github_repo"
    assert parsed["owner"] == "acme-defi"
    assert parsed["repo"] == "core-contracts"


def test_parse_github_target_blob_url():
    parsed = contract_analysis.parse_github_target_url(
        "https://github.com/foo/bar/blob/main/contracts/My.sol"
    )
    assert parsed is not None
    assert parsed["mode"] == "github_file"
    assert parsed["branch"] == "main"
    assert parsed["subpath"] == "contracts/My.sol"


def test_parse_github_target_tree_url():
    parsed = contract_analysis.parse_github_target_url(
        "https://github.com/foo/bar/tree/master/contracts"
    )
    assert parsed is not None
    assert parsed["mode"] == "github_dir"
    assert parsed["branch"] == "master"
    assert parsed["subpath"] == "contracts"


def test_parse_github_target_without_scheme():
    parsed = contract_analysis.parse_github_target_url("github.com/gmx-io/gmx-contracts")
    assert parsed is not None
    assert parsed["owner"] == "gmx-io"
    assert parsed["repo"] == "gmx-contracts"
    assert parsed["source_url"] == "https://github.com/gmx-io/gmx-contracts"


def test_analyze_contract_target_uses_github_target(monkeypatch):
    called = {}

    def fake_analyze(target):
        called["target"] = target
        return {"mode": "github_repo", "target": target["source_url"]}

    monkeypatch.setattr(contract_analysis, "_analyze_github_target", fake_analyze)

    result = contract_analysis.analyze_contract_target(
        "Analyze https://github.com/acme-defi/core-contracts and classify targets."
    )

    assert result is not None
    assert result["mode"] == "github_repo"
    assert called["target"]["owner"] == "acme-defi"


def test_analyze_contract_target_github_prompt_paraphrase_stability(monkeypatch):
    prompts = [
        "Analyze https://github.com/gmx-io/gmx-contracts and classify targets.",
        "Please audit candidacy for github.com/gmx-io/gmx-contracts (high vs low impact).",
        "For this repo: https://github.com/gmx-io/gmx-contracts/, what should be ported first?",
        "Analyze `https://github.com/gmx-io/gmx-contracts` for stylus migration fit.",
    ]
    calls = []

    def fake_analyze(target):
        calls.append(target)
        return {"mode": "github_repo", "target": target["source_url"]}

    monkeypatch.setattr(contract_analysis, "_analyze_github_target", fake_analyze)

    results = [contract_analysis.analyze_contract_target(prompt) for prompt in prompts]

    assert all(item is not None for item in results)
    assert all(item["mode"] == "github_repo" for item in results)
    assert all(call["owner"] == "gmx-io" and call["repo"] == "gmx-contracts" for call in calls)


def test_extract_github_target_prefers_action_url_over_reference_link():
    prompt = (
        "Use benchmark context from https://github.com/LimeChain/stylus-benchmark, "
        "then analyze https://github.com/gmx-io/gmx-contracts and identify high_stylus_benefit targets."
    )
    parsed = contract_analysis._extract_github_target_from_prompt(prompt)

    assert parsed is not None
    assert parsed["owner"] == "gmx-io"
    assert parsed["repo"] == "gmx-contracts"


def test_extract_github_target_prefers_specific_blob_over_repo_when_analyzing_file():
    prompt = (
        "Analyze contract file https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Pool.sol "
        "and use https://github.com/Uniswap/v3-core as general context."
    )
    parsed = contract_analysis._extract_github_target_from_prompt(prompt)

    assert parsed is not None
    assert parsed["mode"] == "github_file"
    assert parsed["subpath"] == "contracts/UniswapV3Pool.sol"


def test_analyze_contract_target_uses_local_path(monkeypatch, tmp_path):
    local = tmp_path / "contracts"
    local.mkdir()
    target = local / "Token.sol"
    target.write_text("contract Token {}", encoding="utf-8")

    called = {}

    def fake_local(path: Path):
        called["path"] = path
        return {"mode": "local_path", "target": str(path)}

    monkeypatch.setattr(contract_analysis, "_analyze_local_target", fake_local)

    result = contract_analysis.analyze_contract_target(f"Analyze this: {target}")

    assert result is not None
    assert result["mode"] == "local_path"
    assert called["path"] == target.resolve()


def test_extract_local_target_supports_relative_path_without_dot_prefix(monkeypatch, tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    target = contracts_dir / "Token.sol"
    target.write_text("contract Token {}", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    result = contract_analysis._extract_local_target_from_prompt("Analyze contracts/Token.sol")

    assert result == target.resolve()


def test_extract_local_target_prompt_paraphrase_stability(monkeypatch, tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    target = contracts_dir / "Token.sol"
    target.write_text("contract Token {}", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    prompts = [
        "Analyze contracts/Token.sol",
        "Please evaluate `./contracts/Token.sol` for stylus porting.",
        "What do you think about (contracts/Token.sol)?",
    ]

    results = [contract_analysis._extract_local_target_from_prompt(prompt) for prompt in prompts]
    assert all(item == target.resolve() for item in results)


def test_clone_repo_retries_without_branch_on_failure(monkeypatch, tmp_path):
    target = {
        "owner": "acme",
        "repo": "core",
        "branch": "feature-x",
        "clone_url": "https://github.com/acme/core.git",
    }
    monkeypatch.setattr(contract_analysis, "CLONE_CACHE_DIR", tmp_path / "cache")

    calls = []

    class _Result:
        def __init__(self, returncode, stderr="", stdout=""):
            self.returncode = returncode
            self.stderr = stderr
            self.stdout = stdout

    def fake_run(cmd, capture_output=True, text=True, timeout=150, check=False):
        calls.append(cmd)
        # First clone (with branch) fails, retry succeeds.
        if len(calls) == 1:
            return _Result(1, stderr="missing branch")
        return _Result(0)

    monkeypatch.setattr(contract_analysis.subprocess, "run", fake_run)

    repo_dir = contract_analysis._clone_repo(target)

    assert repo_dir.name.startswith("acme-core-")
    assert len(calls) == 2
    assert "--branch" in calls[0]
    assert "--branch" not in calls[1]


def test_analyze_github_target_builds_summary_refs_and_cache(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo"
    contracts_dir = repo_dir / "contracts"
    contracts_dir.mkdir(parents=True)
    target_file = contracts_dir / "Pool.sol"
    target_file.write_text("contract Pool {}", encoding="utf-8")

    target = {
        "mode": "github_repo",
        "owner": "uniswap",
        "repo": "v3-core",
        "branch": "main",
        "subpath": "contracts",
        "source_url": "https://github.com/uniswap/v3-core",
        "repo_url": "https://github.com/uniswap/v3-core",
        "clone_url": "https://github.com/uniswap/v3-core.git",
    }

    extractor_payload = {
        "aggregate": {
            "files": 1,
            "contracts": 1,
            "hints": {"final": 73, "upside": 81, "portability": 70, "integration": 58},
        },
        "files": [
            {
                "path": str(target_file),
                "contract_names": ["Pool"],
                "archetype_hint": "compute",
                "upside_score_hint": 81,
                "portability_score_hint": 70,
                "integration_score_hint": 58,
                "positive_signals": ["high-compute-signals"],
                "risk_signals": ["high-external-call-fanout"],
            }
        ],
    }

    monkeypatch.setattr(contract_analysis, "_clone_repo", lambda _target: repo_dir)
    monkeypatch.setattr(contract_analysis, "_detect_repo_branch", lambda _repo, fallback="main": "main")
    monkeypatch.setattr(contract_analysis, "_run_extractor", lambda _path: extractor_payload)
    monkeypatch.setattr(contract_analysis, "_ANALYSIS_CACHE", {})

    result_first = contract_analysis._analyze_github_target(target)
    result_cached = contract_analysis._analyze_github_target(target)

    assert result_first["cache_hit"] is False
    assert result_first["mode"] == "github_repo"
    assert result_first["high_targets"]
    assert any(ref["url"].startswith("https://github.com/uniswap/v3-core/blob/main/") for ref in result_first["references"])
    assert "High stylus benefit candidates (heuristic):" in result_first["summary"]

    assert result_cached["cache_hit"] is True
    assert result_cached["target"] == result_first["target"]


def test_select_targets_prefers_production_contract_paths():
    rows = [
        {"path": "test/FastPath.t.sol", "hint_score": 92, "archetype_hint": "compute"},
        {"path": "contracts/Router.sol", "hint_score": 88, "archetype_hint": "compute"},
        {"path": "contracts/Vault.sol", "hint_score": 32, "archetype_hint": "orchestration"},
    ]

    high, low = contract_analysis._select_targets(rows)

    assert high
    assert high[0]["path"] == "contracts/Router.sol"
    assert all("test/" not in str(row.get("path", "")).lower() for row in high + low)


def test_select_targets_falls_back_when_only_non_production_paths():
    rows = [
        {"path": "test/FastPath.t.sol", "hint_score": 90, "archetype_hint": "compute"},
        {"path": "mocks/Helper.sol", "hint_score": 20, "archetype_hint": "orchestration"},
    ]

    high, low = contract_analysis._select_targets(rows)

    assert high
    assert low
    assert high[0]["path"] == "test/FastPath.t.sol"
    assert low[0]["path"] == "mocks/Helper.sol"


def test_build_target_rows_includes_human_driver_labels():
    payload = {
        "files": [
            {
                "path": "contracts/Router.sol",
                "contract_names": ["Router"],
                "archetype_hint": "isolated-utility-or-mixed",
                "upside_score_hint": 80,
                "portability_score_hint": 90,
                "integration_score_hint": 70,
                "positive_signals": ["high-compute-signals", "low-external-coupling"],
                "risk_signals": ["proxy-upgrade-complexity"],
            }
        ]
    }

    rows = contract_analysis._build_target_rows(payload)
    assert rows
    row = rows[0]
    assert "compute-heavy paths" in row["positive_drivers"]
    assert "low external coupling" in row["positive_drivers"]
    assert "proxy/upgrade complexity" in row["risk_drivers"]


def test_summary_includes_top_driver_lines_and_candidate_drivers():
    high_targets = [
        {
            "path": "contracts/A.sol",
            "hint_score": 88,
            "archetype_hint": "compute",
            "positive_drivers": ["compute-heavy paths", "low external coupling"],
            "risk_drivers": ["proxy/upgrade complexity"],
        }
    ]
    low_targets = [
        {
            "path": "contracts/B.sol",
            "hint_score": 34,
            "archetype_hint": "orchestration",
            "positive_drivers": [],
            "risk_drivers": ["high integration coupling"],
        }
    ]

    summary = contract_analysis._build_summary(
        mode="github_repo",
        target="https://github.com/example/repo",
        aggregate={"files": 2, "contracts": 2, "hints": {"final": 60, "upside": 70, "portability": 65, "integration": 45}},
        high_targets=high_targets,
        low_targets=low_targets,
    )

    assert "Top positive drivers:" in summary
    assert "Top risk drivers:" in summary
    assert "+ compute-heavy paths, low external coupling" in summary
    assert "- proxy/upgrade complexity" in summary
