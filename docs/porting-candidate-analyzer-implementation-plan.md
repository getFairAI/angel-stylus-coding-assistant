# Porting Candidate Analyzer Implementation Plan

## Goal
Improve the quality and usefulness of Stylus porting-candidate recommendations while keeping behavior generic, modular, testable, and resistant to overfitting.

## Scope
- Focus only on `sift-stylus-porting-auditor` backend analysis flow.
- Keep frontend behavior and skill UX contract stable.
- Preserve existing response shape so downstream agents/clients remain compatible.

## Constraints
- No protocol-specific scoring logic (no GMX/Uniswap hardcoding in analyzer rules).
- Every scoring change must be explainable from extracted static signals.
- Avoid divergence from origin by preferring incremental, reviewable refactors.

## Phase 0: Baseline and Guardrails
1. Freeze a baseline prompt suite:
   - Single contract GitHub blob
   - GitHub repo map-style triage
   - Local path file
   - Local path directory
2. Capture current output snapshots for:
   - Top high/low candidates
   - Aggregate hint scores
   - Runtime duration and cache behavior
3. Add guardrail checks:
   - No protocol-name tokens in scoring features
   - No references to non-target local/private URLs in output

## Phase 1: Modularize Analyzer Pipeline
1. Refactor `extract_contract_signals.py` into clear modules/stages:
   - Feature extraction
   - Heuristic scoring
   - Candidate selection
   - Explanation assembly
2. Introduce versioned scoring config:
   - `v1` (current-compatible)
   - `v2` (improved weighting)
3. Add a runtime switch (env/config):
   - `STYLUS_PORTING_SCORING_VERSION=v1|v2`

## Phase 2: Heuristic v2 Improvements
1. Fix coupling/integration misweighting:
   - Reduce/remove import-count penalty as a direct integration risk proxy.
   - Emphasize real coupling signals (external call fanout, proxy/delegatecall complexity).
2. Expand static coupling signals:
   - Detect typed external calls in addition to low-level calls.
   - Capture interface-boundary complexity hints.
3. Improve compute/upside signals:
   - Add richer arithmetic/bitwise/crypto-intensity indicators.
   - Preserve penalties for storage-heavy and orchestration-only patterns.
4. Production candidate hygiene:
   - Exclude tests/mocks/examples/audits from candidate ranking inputs by default.
   - Keep fallback behavior when only non-production files are present.

## Phase 3: Output Usefulness Upgrades
1. Candidate-level explainability:
   - Top positive and negative drivers per candidate.
   - Clear confidence rationale from signal quality.
2. Keep estimates directional and percentage-based:
   - Gas delta percent ranges
   - Execution speed / throughput directional ranges
3. Maintain existing shape:
   - `codebase_analysis` + `summary` + `references` contract remains stable.

## Phase 4: Testing (Unit, Integration, E2E)
1. Unit tests:
   - Feature extraction counters
   - Scoring formula behavior and threshold boundaries
   - Path parsing and source targeting
   - Candidate filtering and fallback
2. Integration tests:
   - Fixture repos/contracts across archetypes (DEX, lending, governance, token-heavy, proxy-heavy, utility)
   - Assert ranking characteristics and monotonicity, not protocol-specific names
3. E2E tests:
   - HTTP calls for GitHub and local-path prompts
   - Verify analyzer metadata, candidate buckets, and references
   - Verify compatibility with current frontend runtime flow

## Phase 5: Anti-Overfitting Validation
1. Holdout fixture set not used in tuning.
2. Compare `v1` vs `v2` ranking deltas on shared suite.
3. Add regression tests for known failure patterns:
   - Audit fixture contamination
   - Import-heavy false negatives
   - Proxy-heavy false positives

## Rollout Strategy
1. Merge modularization + `v1` parity first.
2. Merge `v2` behind feature flag.
3. Run shadow comparisons and review diffs.
4. Flip default to `v2` only after test/quality gates pass.

## Deliverables
1. Analyzer refactor with versioned scoring.
2. Updated tests across unit/integration/e2e layers.
3. Documentation updates for scoring model and validation approach.
4. Stable, generic porting candidate outputs with improved usefulness.
