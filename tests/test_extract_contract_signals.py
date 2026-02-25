from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


def _load_extract_module():
    script_path = (
        Path(__file__).resolve().parent.parent
        / "skills"
        / "sift-stylus-porting-auditor"
        / "scripts"
        / "extract_contract_signals.py"
    )
    spec = spec_from_file_location("extract_contract_signals", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def test_collect_solidity_files_prefers_production_paths(tmp_path):
    module = _load_extract_module()

    production = tmp_path / "contracts" / "Core.sol"
    non_production = tmp_path / "tests" / "Core.t.sol"
    production.parent.mkdir(parents=True)
    non_production.parent.mkdir(parents=True)
    production.write_text("contract Core {}", encoding="utf-8")
    non_production.write_text("contract CoreTest {}", encoding="utf-8")

    files = module.collect_solidity_files(tmp_path)
    assert files == [production]


def test_collect_solidity_files_falls_back_to_non_production(tmp_path):
    module = _load_extract_module()

    only_test = tmp_path / "tests" / "Only.t.sol"
    only_test.parent.mkdir(parents=True)
    only_test.write_text("contract OnlyTest {}", encoding="utf-8")

    files = module.collect_solidity_files(tmp_path)
    assert files == [only_test]


def test_analyze_file_does_not_treat_import_volume_as_strong_integration_risk():
    module = _load_extract_module()

    source = (
        "\n".join('import "./Dep.sol";' for _ in range(14))
        + "\ncontract Foo is Bar, Baz {\n"
        + "  function run() external {\n"
        + "    for (uint256 i = 0; i < 10; i++) {}\n"
        + "  }\n"
        + "}\n"
    )

    result = module.analyze_file(Path("contracts/Foo.sol"), source)

    # High import count alone should not collapse integration confidence.
    assert result.integration_score_hint >= 85


def test_feature_stage_pipeline_builds_expected_explanations():
    module = _load_extract_module()
    source = (
        "contract C {\n"
        "  function run(uint256 n) external pure returns (bytes32 h) {\n"
        "    for (uint256 i = 0; i < n; i++) {\n"
        "      h = keccak256(abi.encodePacked(h, i));\n"
        "    }\n"
        "  }\n"
        "}\n"
    )

    cleaned = module.strip_comments(source)
    counts = module.extract_feature_counts(cleaned)
    upside, portability, integration = module.score_feature_counts(counts)
    archetype, positives, risks = module.assemble_signal_explanations(
        counts,
        upside_score_hint=upside,
        integration_score_hint=integration,
    )

    assert counts.loops >= 1
    assert counts.hash_ops >= 1
    assert upside >= 65
    assert portability >= 80
    assert integration >= 70
    assert archetype in {"crypto-heavy", "isolated-utility-or-mixed"}
    assert "low-external-coupling" in positives
    assert risks == []


def test_candidate_selection_and_explanation_prefers_higher_hint_scores():
    module = _load_extract_module()

    high = module.analyze_file(
        Path("contracts/High.sol"),
        (
            "contract High {\n"
            "  function x(uint256 n) external pure returns (bytes32 h) {\n"
            "    for (uint256 i = 0; i < n; i++) { h = keccak256(abi.encodePacked(h, i)); }\n"
            "  }\n"
            "}\n"
        ),
    )
    low = module.analyze_file(
        Path("contracts/Low.sol"),
        (
            "interface IERC20 { function transfer(address to, uint256 amount) external returns (bool); }\n"
            "contract Low {\n"
            "  mapping(address => uint256) public balances;\n"
            "  address public implementation;\n"
            "  function settle(address t, address to, uint256 a) external { IERC20(t).transfer(to, a); }\n"
            "  function exec(bytes calldata d) external { (bool ok, ) = implementation.delegatecall(d); require(ok); }\n"
            "}\n"
        ),
    )

    selected = module.select_candidate_targets([low, high], limit=1)
    assert selected
    assert selected[0].path.endswith("High.sol")

    explanation = module.build_candidate_explanation(selected[0])
    assert explanation["path"].endswith("High.sol")
    assert isinstance(explanation["hint_score"], int)
    assert explanation["reason"]
