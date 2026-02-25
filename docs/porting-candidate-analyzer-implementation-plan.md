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
2. Standardize on one scoring model:
   - `v2` only (no feature-flag rollout)
   - Remove dead/configurable legacy paths that are not needed

## Phase 2: Heuristic v2 Improvements
1. Fix coupling/integration misweighting:
   - Treat import-count as migration-surface complexity (small portability weight), not runtime integration risk.
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

## Phase 4: Skill Agent and LLM Orchestration
1. Ensure the backend skill output is directly consumable by any agent (frontend, IDE, CLI).
2. Keep all customization on backend skill behavior, not frontend prompt logic.
3. Add LLM augmentation as a bounded second-pass on top of deterministic scoring:
   - Keep static analyzer output as the base ranking.
   - Use the skill-using agent inference to add additional good-fit/bad-fit angles and carveout suggestions.
4. Strengthen agent payload contract for final responses:
   - Retrieval context + analyzer summary + candidate drivers + references are always present when available.
   - Include explicit `analysis_action_paths` and `analysis_brief`.
   - Include `llm_augmentation_contract` with strict JSON shape and citation requirements.
5. Add checks that final answers replicate across clients using the same published skill.

## Phase 5: LLM Augmentation Contract
1. Define strict machine-readable augmentation schema:
   - `additional_good_fit_signals[]`
   - `additional_bad_fit_signals[]`
   - `recommended_carveouts[]`
   - `confidence`
   - `citations[]`
2. Enforce evidence gates:
   - Drop uncited augmentation claims.
   - Mark conflicting/weak claims as low confidence.
3. Add fallback behavior:
   - If augmentation output fails schema or citation checks, return static-only recommendation without failing the request.
4. Bound augmentation impact:
   - Keep ranking influence constrained to avoid overpowering deterministic heuristics.

## Phase 6: Testing (Unit, Integration, E2E)
1. Unit tests:
   - Feature extraction counters
   - Scoring formula behavior and threshold boundaries
   - Path parsing and source targeting
   - Candidate filtering and fallback
   - Augmentation schema validation and fallback behavior
2. Integration tests:
   - Fixture repos/contracts across archetypes (DEX, lending, governance, token-heavy, proxy-heavy, utility)
   - Assert ranking characteristics and monotonicity, not protocol-specific names
   - Compare `static-only` vs `static+augmentation` outputs for quality deltas
3. E2E tests:
   - HTTP calls for GitHub and local-path prompts
   - Verify analyzer metadata, candidate buckets, and references
    - Verify compatibility with current frontend runtime flow
    - Verify augmentation output is schema-valid and citation-backed

## Phase 7: Anti-Overfitting Validation
1. Holdout fixture set not used in tuning.
2. Evaluate ranking stability and usefulness on shared + holdout suites.
3. Add regression tests for known failure patterns:
   - Audit fixture contamination
   - Import-heavy false negatives
   - Proxy-heavy false positives
4. Add prompt-paraphrase stability checks to ensure augmentation behavior is not brittle.

## Phase 8: Acceptance Gates
1. `static+augmentation` must improve candidate quality on labeled fixtures vs static-only baseline.
2. No increase in uncited or schema-invalid claims.
3. Latency/cost budgets must remain within agreed thresholds.
4. If gates fail, default to static-only until fixes land.

## Deliverables
1. Analyzer refactor with a single improved scoring model (`v2`).
2. LLM augmentation contract with schema, citation gates, and safe fallback.
3. Updated tests across unit/integration/e2e layers.
4. Documentation updates for scoring model and validation approach.
5. Stable, generic porting candidate outputs with improved usefulness.
