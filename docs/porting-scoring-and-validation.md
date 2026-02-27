# Porting Scoring and Validation

This document describes the current backend behavior for `sift-stylus-porting-auditor` and how quality is validated.

## Scoring Model

The static analyzer runs in `skills/sift-stylus-porting-auditor/scripts/extract_contract_signals.py` and emits:

- `upside_score_hint`
- `portability_score_hint`
- `integration_score_hint`
- aggregate `final` hint score (`0-100`)

Current weighting is:

- `final = upside * 0.7 + portability * 0.2 + integration * 0.1`

Design constraints:

- Protocol-agnostic scoring features only (no GMX/Uniswap hardcoding).
- Import count is treated as migration-surface complexity, not primary runtime integration risk.
- Boundary complexity (`delegatecall`, proxy terms) is penalized to reduce false high-benefit classifications.
- Non-production contracts (`tests`, `mocks`, `benchmarks`, `docs`, etc.) are excluded from ranking by default, with fallback if only those files exist.

## Retrieval and References

Porting mode retrieval is configured with:

- stricter inline-link budgets
- canonical porting references
- legacy example suppression for noisy outdated sections

This keeps references useful for candidacy decisions and avoids unrelated context leakage.

## Augmentation Contract

LLM augmentation is bounded and citation-gated:

- Validation endpoint: `POST /skills/sift-stylus-porting-auditor/validate-augmentation`
- Comparison endpoint: `POST /skills/sift-stylus-porting-auditor/compare-augmentation`
- Standard porting search (`/stylus-porting-audit` and `/skills/sift-stylus-porting-auditor/search`) requires an `augmentation` payload and auto-applies bounded merge when valid.

If augmentation fails schema/citation checks, behavior falls back to static-only.

## Acceptance Gates

Quality gates are enforced by tests:

- Holdout ranking stability and monotonicity (`test_porting_acceptance_gates.py`)
- Overfitting regressions (`test_extract_contract_signals.py`)
- Static vs augmentation bounded deltas (`test_porting_augmentation_integration.py`)
- Static+augmentation quality improvement on labeled fixture (`test_porting_quality_gates.py`)
- Baseline prompt suite snapshots and cache behavior (`test_porting_baseline_snapshots.py`)
- Client parity for alias vs skill routes (`test_client_parity.py`)
- Protocol-agnostic scoring guardrails (`test_porting_protocol_guardrails.py`)

## Fallback Policy

When acceptance gates fail, the intended behavior is:

- keep static analyzer output as source of truth
- disable reliance on augmentation output for recommendations until fixed
