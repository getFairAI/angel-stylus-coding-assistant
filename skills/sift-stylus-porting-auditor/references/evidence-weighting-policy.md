# Evidence Weighting Policy

This skill is intentionally community-weighted for opportunity assessment, while still using official and security sources as feasibility gates.

## Weighted influence
- Independent benchmarks + project repos/case studies: `45%`
- Anecdotal/community practitioner reports: `30%`
- Official docs + SDK notes: `15%`
- Audits + security advisories: `10%`

Use these weights for confidence and recommendation framing. Keep numeric candidacy scoring upside-first (`70/20/10`) as defined in `SKILL.md`.

## Source tiers
- Tier 1:
- Official protocol/runtime docs.
- SDK/toolchain release notes.
- Security audits.
- Tier 2:
- Independent benchmark repos and reproducible test harnesses.
- Open-source project implementation notes with code.
- Tier 3:
- Community newsletters, forum posts, and practitioner anecdotes.

## Claim strength rules
- `supported`:
- At least one Tier 1 source, or two corroborating Tier 2 sources.
- `mixed`:
- Sources disagree or only one weak independent source exists.
- `weak`:
- Single anecdotal source with no corroboration.

## Contradiction handling
When evidence conflicts:
1. Keep the claim but mark verdict `mixed`.
2. Decrease confidence.
3. Explicitly describe where the contradiction comes from.
4. Prefer contract-specific behavior over generic ecosystem claims.

## Mandatory gating checks
Regardless of weighting, never skip these checks:
- Binary size feasibility.
- Storage layout migration safety.
- Cross-contract call/reentrancy risk.
- Operational lifecycle constraints (activation/reactivation/verification paths).

## Freshness
Include `as_of_date` in all outputs and prefer more recent sources when evidence quality is otherwise equal.
