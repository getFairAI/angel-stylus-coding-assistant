# Stylus Porting Signals

Use this checklist to compare Solidity contracts against candidate quality signals.

## High-value positive signals
- Compute-heavy loops in hot paths.
- Frequent hashing/signature/proof operations.
- Deterministic data transformation logic with limited external dependencies.
- Isolated contract boundaries with low coupling.
- Existing test coverage and invariant definitions.
- Stable external ABI/events that Solidity neighbors can keep consuming without change.
- Limited bidirectional call coupling with non-ported contracts.

## Negative signals
- Predominantly storage-bound operations.
- High fan-out cross-contract orchestration.
- Heavy inline assembly/Yul dependence.
- Proxy/inheritance layouts with fragile storage assumptions.
- Very simple logic where migration overhead likely outweighs performance gains.
- Tight runtime coupling to many Solidity neighbors where interface drift is likely.
- Port candidate requires simultaneous migration of many dependent contracts.

## Hard blockers
- Inability to prove storage compatibility for upgrade/migration path.
- Critical dependency contracts unavailable for parity testing.
- Binary size likely infeasible without a concrete optimization plan.
- Unknown operational lifecycle requirements for target deployment process.
- No clear hybrid boundary (uncertain ABI/event compatibility with Solidity side).
- Critical cross-contract invariants cannot be validated across mixed Solidity/Rust execution.

## Suggested metric mapping
Use static signals as directional evidence, not truth:
- Compute density:
- `loop_count`, `hash_ops`, `crypto_calls`, arithmetic-heavy function count.
- Portability friction:
- `assembly_blocks`, `delegatecall` usage, proxy keywords.
- Integration complexity:
- external call count, inheritance depth, contract fan-out.
- Hybrid fit:
- interface stability, dependency fan-out to non-ported contracts, boundary invariant count.

## Scoring defaults
- Final score: `0.70 * Upside + 0.20 * Portability + 0.10 * Integration`
- Recommendation bands:
- `80-100`: strong now
- `60-79`: caveated
- `40-59`: weak
- `0-39`: poor

Blockers never suppress numeric scoring, but must be prominently disclosed.
The final recommendation should primarily answer impact: "high Stylus benefit" or "low Stylus impact," with concise reasons.
Do not produce a roadmap unless the user explicitly asks for planning.
