# Archetype Analogs

Map each candidate contract to one or more archetypes. Use analogs to support or challenge upside claims.

## 1) Crypto-heavy verifier / hashing engine
Typical signals:
- Signature verification, Merkle/poseidon hashing, proof validation, heavy arithmetic loops.

Expected stylus fit:
- Usually strong upside candidate.

Supporting analogs:
- `Daniel-K-Ivanov/stylus-benchmark` crypto-focused test paths.
- OpenZeppelin Poseidon performance writeup.
- Lit and similar cryptographic workload case studies.

Common caveats:
- Binary size pressure.
- Need strict parity tests for cryptographic correctness.

## 2) Simple token/accounting contract
Typical signals:
- Primarily balance updates, allowance checks, straightforward state changes.

Expected stylus fit:
- Mixed or weak upside in many reports.

Supporting analogs:
- `stylus-benchmark` notes where simple ERC20-style behavior may underperform.

Common caveats:
- Migration cost can exceed upside if compute density is low.

## 3) Proxy + upgrade-heavy protocol core
Typical signals:
- `delegatecall`, ERC1967/UUPS patterns, inherited storage trees, many dependent modules.

Expected stylus fit:
- Often caveated unless migration plan is exceptionally strong.

Supporting analogs:
- Stylus Saturdays posts on reentrancy and code-size constraints.
- Audit and SDK release-note cautions.

Common caveats:
- Storage layout risk.
- Upgrade safety and operational complexity.

## 4) Router/orchestration contract with many external calls
Typical signals:
- High cross-contract fan-out, mostly orchestration, limited internal computation.

Expected stylus fit:
- Usually moderate-to-weak upside unless hot compute paths also exist.

Supporting analogs:
- Community reports emphasizing workload-specific gains.

Common caveats:
- Integration complexity dominates.
- Cross-system testing burden is high.

## 5) Mixed codebase triage mode
Typical signals:
- Multiple contracts with varied profiles.

Expected stylus fit:
- Use map-only ranking, then deep-dive top candidates.

Suggested ordering heuristic:
1. crypto/compute-heavy leaf modules.
2. isolated libraries/utilities.
3. low-coupling service contracts.
4. proxy-heavy core modules last.
