# Output Schema

The skill response should include a human-readable Markdown report followed by a JSON appendix.

## Markdown sections (required)
1. High-Level Recommendation (Prose)
2. Impact Verdicts
3. Candidate Summary
4. Score Breakdown
5. Good-Candidate Signals Found
6. Bad-Candidate Signals Found
7. Hard Blockers and Mitigations
8. Unknowns and Reliability Disclaimer
9. Evidence Snapshot

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
