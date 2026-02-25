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
