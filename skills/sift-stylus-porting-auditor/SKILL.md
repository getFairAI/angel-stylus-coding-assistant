---
name: sift-stylus-porting-auditor
description: Evaluate Solidity contracts for Stylus Rust porting candidacy with an upside-first rubric weighted toward independent benchmarks and community anecdotes, while still enforcing hard feasibility and security blockers.
---

# Skill: sift-stylus-porting-auditor

Use this skill when a user asks whether a Solidity contract (or codebase) is a good candidate to port to Stylus in a hybrid Solidity + Rust architecture.

## What this skill does
- Produces an upside-first candidacy score (`0-100`) with explicit caveats.
- Compares contracts against a concrete list of "good candidate" and "bad candidate" qualities.
- Uses independent and anecdotal ecosystem evidence as first-class inputs.
- Adds ballpark impact estimates for gas savings and/or execution-speed improvements as directional percentage ranges.
- Flags hard blockers and gives mitigation paths.
- Returns line-referenced findings when source code is available.
- Optimizes for partial migration decisions (what to port now vs what should remain in Solidity).
- Prioritizes impact verdicts over migration planning: "high Stylus benefit" vs "low impact."

## Inputs to gather
- One Solidity contract file, a set of Solidity files, or a GitHub repository URL.
- Optional architecture notes (proxy model, upgrade path, critical invariants).
- Optional performance context (high-traffic paths, current bottlenecks).
- Optional workload context from the user. Use it only as context; keep estimates percentage-based and directional.

If the user supplies a full codebase, default to map-only triage and recommend deep-dive targets.

## Hybrid-first objective
Assume only some contracts will be ported. The default task is not "port everything," but "select high-value candidates that can safely coexist with remaining Solidity contracts."

Always answer:
- Which contracts should be ported now.
- Which contracts should remain in Solidity for now.
- What boundary interfaces and call paths must remain stable across the hybrid boundary.

Do not produce phased rollout plans unless explicitly requested. The primary deliverable is impact judgment quality.

## Source policy (required)
Prioritize evidence using this mix:
- Independent benchmarks and project repos/case studies: `45%`
- Community/anecdotal reports (Stylus Saturdays, practitioner writeups): `30%`
- Official Stylus docs and SDK references: `15%`
- Audits and security advisories: `10%`

Still enforce official/audit constraints as hard feasibility gates.

Details and curated links live in:
- `references/community-evidence-index.md`
- `references/evidence-weighting-policy.md`
- `references/archetype-analogs.md`

## Evaluation workflow
1. Collect source and dependency context.
2. Run quick static signal extraction with `python scripts/extract_contract_signals.py <path-or-file>`.
   - For GitHub targets, clone/fetch the referenced repo (or file path) and run extraction on actual Solidity sources.
   - For local IDE/CLI use, run extraction directly against local paths/workspaces.
3. Classify contract archetype using `references/archetype-analogs.md`.
4. Score three dimensions: `UpsideScore` (`70%`), `PortabilityScore` (`20%`), and `IntegrationScore` (`10%`).
5. Evaluate hybrid-boundary fit:
- ABI/event stability requirements.
- Cross-contract call fan-out.
- Storage coupling and upgrade coupling to Solidity neighbors.
6. Identify and report hard blockers with mitigations.
7. List unknowns and add a reliability disclaimer when unknowns are material.
8. If backend payload includes `llm_augmentation_contract`, run a bounded second pass:
   - Keep static analyzer ranking as baseline.
   - Add only citation-backed augmentation claims that satisfy the provided schema.
   - If schema/citation requirements cannot be met, fall back to static-only recommendations.
9. Emit Markdown report plus JSON appendix (schema in `references/output-schema.md`).
10. Persist the JSON appendix to disk using `python scripts/save_json_appendix.py --stdin` (paste JSON through stdin) or `python scripts/save_json_appendix.py --in <json-file>`.

## Good candidate qualities
Strong candidates usually show several of these:
- Compute-heavy paths (hashing, signature verification, arithmetic loops, proof logic).
- Memory-heavy transformations and hot execution paths.
- Isolated boundaries (limited cross-contract coupling).
- Stable external ABI surface and clear invariants.
- Existing tests/specs that make parity validation practical.

## Weak candidate qualities
Weak candidates often exhibit:
- Mostly storage-bound or orchestration-only logic.
- Simple token/accounting flows with low compute density.
- Heavy proxy/inheritance coupling with brittle storage assumptions.
- Inline assembly/Yul dependence.
- Large unknowns around dependencies, invariants, or operational lifecycle.

## Hard blocker policy
Always return a numeric score, but highlight blockers prominently. Typical blockers:
- Storage layout migration risk (proxy/inheritance-heavy systems).
- High-risk cross-contract reentrancy/caching behavior in mixed environments.
- Binary size feasibility concerns without clear reduction plan.
- Missing critical artifacts (dependency contracts, upgrade mechanism, invariants).
- Hybrid boundary fragility (unstable interfaces or high-risk cross-language call assumptions).

For each blocker include:
- Why it is blocking now.
- Evidence reference(s).
- Specific mitigation path.

## Recommendation bands
- `80-100`: Strong candidate now.
- `60-79`: Candidate with caveats.
- `40-59`: Weak candidate; defer unless strategic reason exists.
- `0-39`: Poor candidate currently.

## Output requirements
Follow `references/output-schema.md`.

At minimum include:
- High-level recommendation first (prose, 3-6 sentences) before any numeric analysis.
- Explicit recommendation stance in that prose: `port now`, `pilot first`, or `defer`.
- Explicit impact verdicts:
- `high_stylus_benefit`
- `medium_stylus_benefit`
- `low_stylus_impact`
- Ballpark impact estimate section with percentage-based directional ranges:
  - Provide gas savings estimate as a percent range.
  - Provide execution-speed or throughput improvement estimate (percent range and/or x-multiple).
  - Label confidence (`high|medium|low`) and why.
- Candidate summary.
- Score breakdown.
- Evidence-backed good/bad signal findings.
- Bounded LLM augmentation outputs (when provided by backend contract):
  - `additional_good_fit_signals`
  - `additional_bad_fit_signals`
  - `recommended_carveouts`
  - Claim-level citations and confidence
- Hard blockers and mitigations.
- Unknowns and reliability disclaimer.
- JSON appendix with machine-readable fields.

The report must open with prose context, then move to concrete details. Do not start with raw scores, tables, or bullet dumps.
Do not turn the output into a migration roadmap unless the user asks for planning.
When running in a local workspace, save the JSON appendix to disk and return the saved file path.

## Evidence quality rules
- Performance-upside claims must cite either at least one Tier 1 source or at least two Tier 2 sources.
- If sources conflict, label the claim `mixed` and lower confidence.
- Include `as_of_date` in output.

## Codebase mode default
When given many contracts:
- Provide map-only ranking by candidacy.
- Do not deep-dive every contract by default.
- Return impact-ranked judgments and concise reasoning, not an execution plan.
