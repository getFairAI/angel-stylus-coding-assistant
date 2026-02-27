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


def _normalize_contract_key(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./").lower()


def _contract_aliases(value: Any) -> List[str]:
    normalized = _normalize_contract_key(value)
    if not normalized:
        return []
    aliases = [normalized]
    basename = normalized.rsplit("/", 1)[-1]
    if basename != normalized:
        aliases.append(basename)
    if basename.endswith(".sol"):
        aliases.append(basename[:-4])
    deduped: List[str] = []
    seen = set()
    for item in aliases:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _find_target_index(targets: List[Dict[str, Any]], contract_ref: Any) -> int:
    signal_aliases = set(_contract_aliases(contract_ref))
    if not signal_aliases:
        return -1

    best_index = -1
    best_score = -1
    exact_ref = _normalize_contract_key(contract_ref)
    for index, row in enumerate(targets):
        row_path = str(row.get("path") or row.get("contract") or "")
        row_aliases = set(_contract_aliases(row_path))
        if not row_aliases:
            continue
        if signal_aliases.isdisjoint(row_aliases):
            continue

        score = 1
        if exact_ref and exact_ref == _normalize_contract_key(row_path):
            score = 2
        if score > best_score:
            best_score = score
            best_index = index

    return best_index


def _copy_targets(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _annotate_target(target: Dict[str, Any], *, kind: str, payload: Dict[str, Any], message_key: str) -> None:
    note = {
        "kind": kind,
        "message": str(payload.get(message_key) or "").strip(),
        "confidence": str(payload.get("confidence") or "").strip().lower() or "low",
        "citations": _normalize_citations(payload.get("citations")),
    }
    notes = target.get("augmentation_notes")
    if not isinstance(notes, list):
        notes = []
        target["augmentation_notes"] = notes
    notes.append(note)


def _path_set(targets: List[Dict[str, Any]]) -> set:
    values = set()
    for item in targets:
        key = _normalize_contract_key(item.get("path"))
        if key:
            values.add(key)
    return values


def _path_samples(targets: List[Dict[str, Any]], allowed: set) -> List[str]:
    values: List[str] = []
    for item in targets:
        path = str(item.get("path") or "").strip()
        key = _normalize_contract_key(path)
        if not path or key not in allowed:
            continue
        if path in values:
            continue
        values.append(path)
    return values


def compare_porting_analysis_with_augmentation(
    static_analysis: Any,
    validated_augmentation: Any,
    *,
    contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    static = static_analysis if isinstance(static_analysis, dict) else {}
    static_high = _copy_targets(static.get("high_targets"))
    static_low = _copy_targets(static.get("low_targets"))

    base = {
        "mode": "static_only",
        "static": {
            "high_targets": static_high,
            "low_targets": static_low,
        },
        "augmented": {
            "high_targets": _copy_targets(static_high),
            "low_targets": _copy_targets(static_low),
            "applied_bounds": {},
            "warnings": [],
            "unmatched_signals": [],
        },
        "quality_delta": {
            "static_high_count": len(static_high),
            "augmented_high_count": len(static_high),
            "high_targets_added": [],
            "high_targets_removed": [],
            "promotions": 0,
            "demotions": 0,
        },
    }

    if not static:
        base["quality_delta"]["reason"] = "missing_static_analysis"
        return base

    augmentation = validated_augmentation if isinstance(validated_augmentation, dict) else {}
    if augmentation.get("mode") != "bounded_second_pass":
        validation = augmentation.get("validation") if isinstance(augmentation, dict) else {}
        if isinstance(validation, dict):
            base["augmented"]["warnings"] = list(validation.get("warnings") or [])
            base["quality_delta"]["reason"] = str(validation.get("reason") or "augmentation_not_applied")
        else:
            base["quality_delta"]["reason"] = "augmentation_not_applied"
        return base

    contract_config = contract if isinstance(contract, dict) else build_porting_augmentation_contract()
    bounds = contract_config.get("ranking_influence_bounds") or {}
    max_rank_shift = max(0, int(bounds.get("max_rank_shift") or 1))
    max_new_high_targets = max(0, int(bounds.get("max_new_high_targets") or 2))
    allow_removal = bool(bounds.get("allow_removal_of_static_candidates"))

    augmented_high = _copy_targets(static_high)
    augmented_low = _copy_targets(static_low)
    unmatched_signals: List[str] = []
    promotions = 0
    demotions = 0
    applied_bounds: Dict[str, Any] = {}

    for signal in augmentation.get("additional_good_fit_signals") or []:
        if not isinstance(signal, dict):
            continue
        contract_ref = signal.get("contract")
        high_index = _find_target_index(augmented_high, contract_ref)
        if high_index >= 0:
            _annotate_target(augmented_high[high_index], kind="good_signal", payload=signal, message_key="signal")
            continue

        low_index = _find_target_index(augmented_low, contract_ref)
        if low_index < 0:
            unmatched_signals.append(str(contract_ref or ""))
            continue

        target = augmented_low[low_index]
        _annotate_target(target, kind="good_signal", payload=signal, message_key="signal")
        if promotions >= max_new_high_targets:
            continue

        promoted = dict(target)
        promoted["augmentation_promoted"] = True
        promoted["augmentation_confidence"] = str(signal.get("confidence") or "low")
        del augmented_low[low_index]

        if augmented_high and max_rank_shift > 0:
            insert_at = max(len(augmented_high) - max_rank_shift, 0)
        else:
            insert_at = len(augmented_high)
        augmented_high.insert(insert_at, promoted)
        promotions += 1
        applied_bounds["max_new_high_targets"] = max_new_high_targets
        applied_bounds["max_rank_shift"] = max_rank_shift

    for signal in augmentation.get("additional_bad_fit_signals") or []:
        if not isinstance(signal, dict):
            continue
        contract_ref = signal.get("contract")

        high_index = _find_target_index(augmented_high, contract_ref)
        if high_index >= 0:
            _annotate_target(augmented_high[high_index], kind="bad_signal", payload=signal, message_key="signal")
            if max_rank_shift > 0 and high_index < (len(augmented_high) - 1):
                swap_index = min(high_index + max_rank_shift, len(augmented_high) - 1)
                augmented_high[high_index], augmented_high[swap_index] = (
                    augmented_high[swap_index],
                    augmented_high[high_index],
                )
                demotions += 1
                applied_bounds["max_rank_shift"] = max_rank_shift
            elif allow_removal and high_index == (len(augmented_high) - 1):
                moved = dict(augmented_high.pop(high_index))
                moved["augmentation_demoted"] = True
                augmented_low.insert(0, moved)
                demotions += 1
                applied_bounds["allow_removal_of_static_candidates"] = True
            continue

        low_index = _find_target_index(augmented_low, contract_ref)
        if low_index >= 0:
            _annotate_target(augmented_low[low_index], kind="bad_signal", payload=signal, message_key="signal")
            continue

        unmatched_signals.append(str(contract_ref or ""))

    for carveout in augmentation.get("recommended_carveouts") or []:
        if not isinstance(carveout, dict):
            continue
        contract_ref = carveout.get("contract")
        high_index = _find_target_index(augmented_high, contract_ref)
        if high_index >= 0:
            _annotate_target(
                augmented_high[high_index],
                kind="carveout",
                payload=carveout,
                message_key="recommendation",
            )
            continue
        low_index = _find_target_index(augmented_low, contract_ref)
        if low_index >= 0:
            _annotate_target(
                augmented_low[low_index],
                kind="carveout",
                payload=carveout,
                message_key="recommendation",
            )
            continue
        unmatched_signals.append(str(contract_ref or ""))

    static_high_set = _path_set(static_high)
    augmented_high_set = _path_set(augmented_high)
    high_added = augmented_high_set - static_high_set
    high_removed = static_high_set - augmented_high_set

    warnings = []
    validation = augmentation.get("validation")
    if isinstance(validation, dict):
        warnings = list(validation.get("warnings") or [])

    return {
        "mode": "bounded_second_pass",
        "static": {
            "high_targets": static_high,
            "low_targets": static_low,
        },
        "augmented": {
            "high_targets": augmented_high,
            "low_targets": augmented_low,
            "applied_bounds": applied_bounds,
            "warnings": warnings,
            "unmatched_signals": unmatched_signals,
        },
        "quality_delta": {
            "static_high_count": len(static_high),
            "augmented_high_count": len(augmented_high),
            "high_targets_added": _path_samples(augmented_high, high_added),
            "high_targets_removed": _path_samples(static_high, high_removed),
            "promotions": promotions,
            "demotions": demotions,
        },
    }
