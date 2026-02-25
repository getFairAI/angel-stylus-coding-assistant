# Output Schema

The skill response should include a human-readable Markdown report followed by a JSON appendix.

## Markdown sections (required)
1. High-Level Recommendation (Prose)
2. Potential Upside Snapshot
3. Impact Verdicts
4. Ballpark Impact Estimate (%)
5. Candidate Summary
6. Score Breakdown
7. Good-Candidate Signals Found
8. Bad-Candidate Signals Found
9. Hard Blockers and Mitigations
10. Unknowns and Reliability Disclaimer
11. Evidence Snapshot

### High-Level Recommendation (Prose) requirements
- Must appear first in the report.
- Must be 3-6 sentences in plain prose.
- Must state one clear stance: `port now`, `pilot first`, or `defer`.
- Must briefly justify the stance using upside vs migration complexity.
- Must emphasize potential value before caveats, even when stance is `defer`.

### Potential Upside Snapshot requirements
- Must appear before risk-heavy sections.
- Must include concrete upside opportunities from analyzed signals (for example compute hotspots, bounded carveouts, or interface-isolated pilots).
- If overall stance is `defer`, still include at least one bounded pilot/carveout opportunity.

### Impact Verdicts requirements
- Must explicitly classify contracts as:
- `high_stylus_benefit`
- `medium_stylus_benefit`
- `low_stylus_impact`
- Must provide a short reason and confidence for each classified contract.
- Keep this section judgment-focused. Do not provide phased roadmap steps unless requested.

### Ballpark Impact Estimate requirements
- Must provide:
  - Gas savings estimate in percent range (directional).
  - Execution-speed or throughput estimate (percent and/or x-multiple).
  - Confidence level and caveat notes.
- Estimates must be directional and approximate; do not present as precise measurements.

### Bounded LLM augmentation requirements (when contract is provided)
- Keep static analyzer ranking as the baseline.
- Add only schema-valid augmentation claims with citations.
- Every augmentation claim must include at least one URL citation.
- If schema or citation rules fail, fall back to static-only recommendation behavior.

## JSON appendix
```json
{
  "skill": "sift-stylus-porting-auditor",
  "json_appendix_path": "string|null",
  "as_of_date": "YYYY-MM-DD",
  "mode": "single_contract | codebase_map",
  "target": "stylus-rust",
  "high_level_recommendation": {
    "stance": "port_now | pilot_first | defer",
    "summary": "string",
    "confidence": "high | medium | low"
  },
  "impact_verdicts": {
    "high_stylus_benefit": [
      {
        "contract": "string",
        "reason": "string",
        "confidence": "high | medium | low"
      }
    ],
    "medium_stylus_benefit": [
      {
        "contract": "string",
        "reason": "string",
        "confidence": "high | medium | low"
      }
    ],
    "low_stylus_impact": [
      {
        "contract": "string",
        "reason": "string",
        "confidence": "high | medium | low"
      }
    ],
    "boundary_assumptions": [
      {
        "interface_or_event": "string",
        "assumption": "string",
        "risk_if_wrong": "string"
      }
    ]
  },
  "ballpark_estimate": {
    "gas": {
      "percent_delta": {
        "min_percent": 0,
        "max_percent": 0
      }
    },
    "performance": {
      "speedup_percent": {
        "min_percent": 0,
        "max_percent": 0
      },
      "throughput_multiplier": {
        "min_x": 1.0,
        "max_x": 1.0
      }
    },
    "confidence": "high | medium | low",
    "basis": ["string"]
  },
  "llm_augmentation": {
    "mode": "bounded_second_pass | static_only_fallback",
    "additional_good_fit_signals": [
      {
        "contract": "string",
        "signal": "string",
        "confidence": "high | medium | low",
        "citations": ["https://..."]
      }
    ],
    "additional_bad_fit_signals": [
      {
        "contract": "string",
        "signal": "string",
        "confidence": "high | medium | low",
        "citations": ["https://..."]
      }
    ],
    "recommended_carveouts": [
      {
        "contract": "string",
        "recommendation": "string",
        "rationale": "string",
        "confidence": "high | medium | low",
        "citations": ["https://..."]
      }
    ],
    "confidence": "high | medium | low",
    "citations": ["https://..."]
  },
  "contract": {
    "name": "string",
    "path": "string",
    "github_url": "string|null"
  },
  "scores": {
    "final": 0,
    "upside": 0,
    "portability": 0,
    "integration": 0,
    "weights": {
      "upside": 0.7,
      "portability": 0.2,
      "integration": 0.1
    }
  },
  "recommendation_band": "strong_now | caveated | weak | poor",
  "evidence_mix": {
    "independent": 0,
    "anecdotal": 0,
    "official": 0,
    "audit": 0
  },
  "evidence_quality": {
    "tier1_count": 0,
    "tier2_count": 0,
    "tier3_count": 0,
    "conflicting_signals": []
  },
  "claims": [
    {
      "claim": "string",
      "verdict": "supported | mixed | weak",
      "sources": [
        {
          "url": "string",
          "tier": "tier1 | tier2 | tier3"
        }
      ]
    }
  ],
  "hard_blockers": [
    {
      "title": "string",
      "evidence": ["file:line"],
      "mitigation": "string"
    }
  ],
  "unknowns": [
    {
      "item": "string",
      "impact": "low | medium | high",
      "needed_to_resolve": "string"
    }
  ],
  "evidence": [
    {
      "claim": "string",
      "refs": ["file:line"]
    }
  ],
  "analogs_used": [
    {
      "project": "string",
      "archetype": "string",
      "source_url": "string",
      "signal": "supports | contradicts"
    }
  ],
  "operational_constraints": ["string"],
  "migration_risk_notes": ["string"],
  "impact_summary": "string"
}
```

## Persistence (local runs)
- Save JSON appendices under `artifacts/sift-stylus-porting-auditor/` by default.
- Use `scripts/save_json_appendix.py` to persist JSON from stdin or from a file.
- Include the saved path in `json_appendix_path` when available.
