from typing import Any, Dict, List, Optional, Tuple

ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def build_porting_augmentation_contract() -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "mode": "bounded_second_pass",
        "required_output": {
            "additional_good_fit_signals": [
                {
                    "contract": "string",
                    "signal": "string",
                    "confidence": "high|medium|low",
                    "citations": ["https://..."],
                }
            ],
            "additional_bad_fit_signals": [
                {
                    "contract": "string",
                    "signal": "string",
                    "confidence": "high|medium|low",
                    "citations": ["https://..."],
                }
            ],
            "recommended_carveouts": [
                {
                    "contract": "string",
                    "recommendation": "string",
                    "rationale": "string",
                    "confidence": "high|medium|low",
                    "citations": ["https://..."],
                }
            ],
            "confidence": "high|medium|low",
            "citations": ["https://..."],
        },
        "validation_rules": {
            "require_citations_per_item": True,
            "drop_uncited_items": True,
            "mark_conflicts_low_confidence": True,
            "on_validation_failure": "fallback_static_only",
        },
        "ranking_influence_bounds": {
            "base_ranking_source": "codebase_analysis",
            "max_rank_shift": 1,
            "max_new_high_targets": 2,
            "allow_removal_of_static_candidates": False,
        },
    }


def render_porting_augmentation_contract(contract: Dict[str, Any]) -> str:
    if not isinstance(contract, dict):
        return ""
    lines = [
        "LLM augmentation contract:",
        "- Treat codebase_analysis ranking as the base recommendation.",
        (
            "- Return only schema-shaped augmentation fields: additional_good_fit_signals, "
            "additional_bad_fit_signals, recommended_carveouts, confidence, citations."
        ),
        "- Include at least one URL citation for each augmentation claim.",
        "- Drop uncited or conflicting claims; if uncertain, fall back to static-only output.",
    ]
    return "\n".join(lines)


def _normalize_confidence(value: Any, *, default: str = "low") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_CONFIDENCE else default


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_citations(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    deduped: List[str] = []
    seen = set()
    for item in value:
        url = str(item or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _normalize_signal_item(
    item: Any,
    *,
    kind: str,
    message_key: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(item, dict):
        return None, f"{kind}: item must be an object"

    contract = _normalize_text(item.get("contract"))
    message = _normalize_text(item.get(message_key))
    citations = _normalize_citations(item.get("citations"))
    confidence = _normalize_confidence(item.get("confidence"), default="low")

    if not contract or not message:
        return None, f"{kind}: missing contract or {message_key}"
    if not citations:
        return None, f"{kind}: dropped uncited claim for contract '{contract}'"

    normalized: Dict[str, Any] = {
        "contract": contract,
        message_key: message,
        "confidence": confidence,
        "citations": citations,
    }

    if message_key == "recommendation":
        rationale = _normalize_text(item.get("rationale"))
        if not rationale:
            return None, f"{kind}: missing rationale for contract '{contract}'"
        normalized["rationale"] = rationale

    return normalized, None


def _normalize_signal_list(
    value: Any,
    *,
    kind: str,
    message_key: str,
) -> Tuple[List[Dict[str, Any]], List[str], int]:
    if not isinstance(value, list):
        return [], [f"{kind}: expected a list"], 1

    normalized: List[Dict[str, Any]] = []
    warnings: List[str] = []
    dropped = 0
    seen = set()
    for item in value:
        parsed, warning = _normalize_signal_item(item, kind=kind, message_key=message_key)
        if parsed is None:
            dropped += 1
            if warning:
                warnings.append(warning)
            continue
        signature = (parsed["contract"], parsed.get(message_key))
        if signature in seen:
            dropped += 1
            warnings.append(f"{kind}: dropped duplicate claim for contract '{parsed['contract']}'")
            continue
        seen.add(signature)
        normalized.append(parsed)

    return normalized, warnings, dropped


def _fallback_result(reason: str, warnings: Optional[List[str]] = None, dropped_items: int = 0) -> Dict[str, Any]:
    return {
        "mode": "static_only_fallback",
        "additional_good_fit_signals": [],
        "additional_bad_fit_signals": [],
        "recommended_carveouts": [],
        "confidence": "low",
        "citations": [],
        "validation": {
            "status": "fallback",
            "reason": reason,
            "warnings": warnings or [],
            "dropped_items": dropped_items,
            "applied_bounds": {},
        },
    }


def validate_porting_augmentation(
    raw_augmentation: Any,
    *,
    contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    contract_config = contract if isinstance(contract, dict) else build_porting_augmentation_contract()
    required = (
        "additional_good_fit_signals",
        "additional_bad_fit_signals",
        "recommended_carveouts",
        "confidence",
        "citations",
    )

    if not isinstance(raw_augmentation, dict):
        return _fallback_result("augmentation_payload_must_be_object")

    missing = [key for key in required if key not in raw_augmentation]
    if missing:
        return _fallback_result(f"schema_missing_required_keys:{','.join(missing)}")

    global_citations = _normalize_citations(raw_augmentation.get("citations"))
    if not global_citations:
        return _fallback_result("schema_missing_global_citations")

    good, good_warnings, good_dropped = _normalize_signal_list(
        raw_augmentation.get("additional_good_fit_signals"),
        kind="additional_good_fit_signals",
        message_key="signal",
    )
    bad, bad_warnings, bad_dropped = _normalize_signal_list(
        raw_augmentation.get("additional_bad_fit_signals"),
        kind="additional_bad_fit_signals",
        message_key="signal",
    )
    carveouts, carveout_warnings, carveout_dropped = _normalize_signal_list(
        raw_augmentation.get("recommended_carveouts"),
        kind="recommended_carveouts",
        message_key="recommendation",
    )

    warnings = [*good_warnings, *bad_warnings, *carveout_warnings]
    dropped_items = good_dropped + bad_dropped + carveout_dropped

    # Bound ranking influence by constraining uplift-like additions.
    bounds = contract_config.get("ranking_influence_bounds") or {}
    max_new_high_targets = int(bounds.get("max_new_high_targets") or 2)
    applied_bounds: Dict[str, Any] = {}
    if len(good) > max_new_high_targets:
        removed = len(good) - max_new_high_targets
        good = good[:max_new_high_targets]
        dropped_items += removed
        warnings.append(
            f"additional_good_fit_signals: trimmed to max_new_high_targets={max_new_high_targets}"
        )
        applied_bounds["max_new_high_targets"] = max_new_high_targets

    if contract_config.get("validation_rules", {}).get("mark_conflicts_low_confidence"):
        bad_contracts = {item["contract"] for item in bad}
        conflict_contracts = {item["contract"] for item in good if item["contract"] in bad_contracts}
        if conflict_contracts:
            for item in good:
                if item["contract"] in conflict_contracts:
                    item["confidence"] = "low"
            for item in bad:
                if item["contract"] in conflict_contracts:
                    item["confidence"] = "low"
            warnings.append(
                "conflicting_good_and_bad_signals_detected: set conflict contract confidence to low"
            )

    if not good and not bad and not carveouts:
        return _fallback_result(
            "no_valid_cited_augmentation_claims",
            warnings=warnings,
            dropped_items=dropped_items,
        )

    return {
        "mode": "bounded_second_pass",
        "additional_good_fit_signals": good,
        "additional_bad_fit_signals": bad,
        "recommended_carveouts": carveouts,
        "confidence": _normalize_confidence(raw_augmentation.get("confidence"), default="low"),
        "citations": global_citations,
        "validation": {
            "status": "valid",
            "reason": "ok",
            "warnings": warnings,
            "dropped_items": dropped_items,
            "applied_bounds": applied_bounds,
        },
    }
