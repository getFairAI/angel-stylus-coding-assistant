# Output Schema

The skill response should include a human-readable Markdown report followed by a JSON appendix.

## Markdown sections (required)
1. High-Level Recommendation (Prose)
2. Impact Verdicts
3. Ballpark Impact Estimate (Assumed Usage)
4. Candidate Summary
5. Score Breakdown
6. Good-Candidate Signals Found
7. Bad-Candidate Signals Found
8. Hard Blockers and Mitigations
9. Unknowns and Reliability Disclaimer
10. Evidence Snapshot

### High-Level Recommendation (Prose) requirements
- Must appear first in the report.
- Must be 3-6 sentences in plain prose.
- Must state one clear stance: `port now`, `pilot first`, or `defer`.
- Must briefly justify the stance using upside vs migration complexity.

### Impact Verdicts requirements
- Must explicitly classify contracts as:
- `high_stylus_benefit`
- `medium_stylus_benefit`
- `low_stylus_impact`
- Must provide a short reason and confidence for each classified contract.
- Keep this section judgment-focused. Do not provide phased roadmap steps unless requested.

### Ballpark Impact Estimate requirements
- Must include explicit usage assumptions.
- If usage is not user-provided, default to `100000` relevant executions/day and label as arbitrary baseline.
- Must provide:
  - Per-call gas estimate delta (range if uncertain).
  - Aggregate daily and monthly gas estimate delta from stated assumptions.
  - Execution-speed or throughput estimate (percent and/or x-multiple).
  - Confidence level and caveat notes.
- Estimates must be directional and approximate; do not present as precise measurements.

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
    "usage_assumptions": {
      "provided_by_user": false,
      "executions_per_day": 100000,
      "notes": "string"
    },
    "gas": {
      "per_call_delta_gas": {
        "min": 0,
        "max": 0
      },
      "per_call_percent_delta": {
        "min_percent": 0,
        "max_percent": 0
      },
      "daily_delta_gas": {
        "min": 0,
        "max": 0
      },
      "monthly_delta_gas": {
        "min": 0,
        "max": 0
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
