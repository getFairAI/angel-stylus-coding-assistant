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
