from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys

import contract_analysis


BANNED_PROTOCOL_TOKENS = {
    "gmx",
    "uniswap",
    "aave",
    "compound",
    "maker",
    "curve",
    "balancer",
    "sushiswap",
}


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


def _assert_no_protocol_tokens(text: str):
    lowered = str(text or "").lower()
    for token in BANNED_PROTOCOL_TOKENS:
        assert token not in lowered


def test_extractor_scoring_features_are_protocol_agnostic():
    module = _load_extract_module()
    payload = {
        "patterns": {key: value.pattern for key, value in module.PATTERNS.items()},
        "signal_labels": module.SIGNAL_LABELS if hasattr(module, "SIGNAL_LABELS") else {},
        "non_production_dirs": sorted(module.NON_PRODUCTION_DIRS),
    }
    _assert_no_protocol_tokens(json.dumps(payload, sort_keys=True))


def test_contract_analysis_scoring_labels_are_protocol_agnostic():
    payload = {
        "signal_labels": contract_analysis.SIGNAL_LABELS,
        "non_target_path_hints": sorted(contract_analysis.NON_TARGET_PATH_HINTS),
        "action_tokens": sorted(contract_analysis._PROMPT_ACTION_TOKENS),
        "context_tokens": sorted(contract_analysis._PROMPT_CONTEXT_TOKENS),
    }
    _assert_no_protocol_tokens(json.dumps(payload, sort_keys=True))
