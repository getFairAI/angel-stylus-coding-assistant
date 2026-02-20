# Community Evidence Index

Use this index to ground recommendations beyond SDK docs. Treat these as reusable analog sources when comparing candidate contracts.

## Independent benchmarks and project evidence (high weight)
- `https://github.com/OffchainLabs/awesome-stylus`
Signal: discovery hub for real Stylus projects, libraries, tooling, and benchmarks.

- `https://github.com/Daniel-K-Ivanov/stylus-benchmark`
Signal: benchmark harness shows asymmetric outcomes; compute-heavy crypto paths can outperform while simple ERC20-style flows may not.

- `https://blog.openzeppelin.com/poseidon-go-brr-with-stylus-cryptographic-functions-are-18x-more-gas-efficient-via-rust-on-arbitrum`
Signal: strong upside pattern for cryptographic workloads.

- `https://github.com/fluidity-money/long.so`
Signal: production-leaning Stylus codebase example for architecture and migration complexity patterns.

- `https://github.com/renegade-fi/renegade`
Signal: advanced project footprint useful for coupling and system-complexity analogs.

## Community and anecdotal sources (high weight)
- `https://stylus-saturdays.com/archive`
Signal: curated stream of practitioner insights, project launches, and pitfalls.

- `https://stylus-saturdays.com/p/how-to-audit-a-rust-stylus-project`
Signal: practical audit concerns and Rust-specific review angles.

- `https://stylus-saturdays.com/p/extreme-codesize-optimisations-reentrancy`
Signal: recurring code-size constraints and reentrancy-focused upgrade notes.

- `https://stylus-saturdays.com/p/how-to-verify-your-stylus-contracts`
Signal: operational friction and verification workflow realities.

- `https://stylus-saturdays.com/p/stylus-contract-deployments-list`
Signal: concrete deployment landscape for adoption/maturity context.

## Case-study narratives (independent but promotional)
- `https://blog.arbitrum.io/renegade-stylus-case-study/`
Signal: upside stories for specific workloads and architecture choices.

- `https://blog.arbitrum.io/how-superposition-is-transforming-onchain-rewards-with-stylus/`
Signal: workload-specific migration rationale.

- `https://blog.arbitrum.io/how-lit-protocol-coordinates-decentralized-key-management-with-stylus/`
Signal: crypto/key-management workload analog.

## Constraints and safety references (gating)
- `https://docs.arbitrum.io/stylus/concepts/gas-metering`
Signal: runtime model, fixed overhead, and when computation becomes favorable.

- `https://docs.arbitrum.io/stylus/how-tos/optimizing-binaries`
Signal: hard size constraints and optimization expectations.

- `https://docs.arbitrum.io/stylus/how-tos/caching-contracts`
Signal: activation/reactivation operational requirements.

- `https://docs.arbitrum.io/stylus/gentle-introduction`
Signal: high-level architecture, lifecycle behavior, and compatibility framing.

- `https://github.com/OffchainLabs/stylus-sdk-rs/releases/tag/v0.8.4`
Signal: security/behavioral changes affecting migration risk assumptions.

- `https://www.openzeppelin.com/news/stylus-rust-sdk-audit`
Signal: audited risk categories relevant to parity and call-safety concerns.

## How to use this index
1. Match the candidate contract to one or more analogs.
2. Pull at least two independent/community references when asserting upside.
3. Pair upside evidence with at least one constraints/safety reference.
4. If analogs conflict, label verdict `mixed` and lower confidence.
