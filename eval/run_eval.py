"""Retrieval-quality eval harness for the Stylus RAG backend.

Runs the golden question set (``eval/golden_stylus.jsonl``) through the backend's
skill-search endpoints and reports retrieval metrics. Optionally grades context
relevance with the (previously orphaned) ``src/rag_evaluation.py`` graders when an
LLM is configured.

Design notes:
- Infra-optional. Retrieval metrics need only ``requests`` and a running backend.
  The LLM grader degrades to "skipped (reason)" when deps/keys are absent.
- Pure scoring logic (``evaluate_item``/``aggregate``/``format_scorecard``) has no
  I/O so it is unit-tested in ``tests/test_eval_harness.py`` without a live server.

Usage:
    python eval/run_eval.py --backend-url http://localhost:8001 \\
        --golden eval/golden_stylus.jsonl --out eval/scorecard.json

Env:
    EVAL_BACKEND_URL   default backend base url
    EVAL_LLM_MODEL / EVAL_LLM_BASE_URL / OPENAI_API_KEY|OPENROUTER_API_KEY
                       enable the optional context-relevance grader
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

# skill field in the golden set -> registered backend skill id
SKILL_MAP = {
    "research": "sift-stylus-research",
    "code_helper": "sift-stylus-code-helper",
    "porting": "sift-stylus-porting-auditor",
}


# ---------------------------------------------------------------------------
# Pure scoring logic (no I/O — unit tested)
# ---------------------------------------------------------------------------
def _reference_haystack(response: dict) -> str:
    """Lowercased blob of context + reference fields for substring matching."""
    parts: list[str] = [str(response.get("context", ""))]
    for ref in response.get("references", []) or []:
        if isinstance(ref, dict):
            parts.extend(str(ref.get(k, "")) for k in ("title", "url", "source"))
        else:
            parts.append(str(ref))
    return "\n".join(parts).lower()


def evaluate_item(item: dict, response: dict) -> dict:
    """Score a single golden item against its backend response. Pure function."""
    expect_found = bool(item.get("expect_found", True))
    found = bool(response.get("found", False))
    haystack = _reference_haystack(response)

    expected = [s.lower() for s in item.get("expect_source_contains", []) or []]
    matched = [s for s in expected if s in haystack]
    source_recall = (len(matched) / len(expected)) if expected else None

    return {
        "id": item.get("id"),
        "skill": item.get("skill"),
        "question": item.get("question"),
        "expect_found": expect_found,
        "found": found,
        "found_correct": found == expect_found,
        "chunks_used": int(response.get("chunks_used", 0) or 0),
        "expected_sources": expected,
        "matched_sources": matched,
        "source_recall": source_recall,
        "error": response.get("_error"),
    }


def aggregate(results: list[dict]) -> dict:
    """Aggregate per-item results into a scorecard summary. Pure function."""
    n = len(results)
    errored = [r for r in results if r.get("error")]
    scored = [r for r in results if not r.get("error")]

    found_correct = [r for r in scored if r["found_correct"]]
    positives = [r for r in scored if r["expect_found"]]
    negatives = [r for r in scored if not r["expect_found"]]
    recalls = [r["source_recall"] for r in scored if r["source_recall"] is not None]

    def _rate(part: list[dict], whole: list[dict]) -> Optional[float]:
        return round(len(part) / len(whole), 4) if whole else None

    return {
        "total": n,
        "errored": len(errored),
        "scored": len(scored),
        "found_accuracy": _rate(found_correct, scored),
        "positive_found_rate": _rate([r for r in positives if r["found"]], positives),
        "negative_correct_rate": _rate([r for r in negatives if not r["found"]], negatives),
        "avg_source_recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "avg_chunks_used": round(sum(r["chunks_used"] for r in scored) / len(scored), 2)
        if scored
        else None,
    }


def format_scorecard(summary: dict, results: list[dict]) -> str:
    """Human-readable scorecard. Pure function."""
    lines = ["=== Stylus retrieval eval scorecard ===", ""]
    for key in (
        "total",
        "scored",
        "errored",
        "found_accuracy",
        "positive_found_rate",
        "negative_correct_rate",
        "avg_source_recall",
        "avg_chunks_used",
    ):
        lines.append(f"  {key:<24} {summary.get(key)}")
    failing = [
        r for r in results if not r.get("error") and (not r["found_correct"] or (r["source_recall"] == 0.0))
    ]
    if failing:
        lines.append("")
        lines.append(f"  weakest items ({len(failing)}):")
        for r in failing[:15]:
            reason = "wrong found" if not r["found_correct"] else "0 source recall"
            lines.append(f"    - {r['id']:<18} [{reason}]")
    if any(r.get("error") for r in results):
        lines.append("")
        lines.append("  errored items:")
        for r in results:
            if r.get("error"):
                lines.append(f"    - {r['id']}: {r['error']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Optional LLM grader (wires the formerly-orphaned rag_evaluation.py)
# ---------------------------------------------------------------------------
def build_grader_llm() -> tuple[Optional[Any], Optional[str]]:
    """Return (llm, None) if a grader LLM is configured, else (None, skip_reason)."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None, "no OPENAI_API_KEY/OPENROUTER_API_KEY set"
    try:
        from langchain_openai import ChatOpenAI  # lazy: not a core dependency
    except Exception as exc:  # pragma: no cover - depends on optional extra
        return None, f"langchain_openai not installed ({exc})"
    model = os.environ.get("EVAL_LLM_MODEL", "gpt-4o-mini")
    base_url = os.environ.get("EVAL_LLM_BASE_URL")
    kwargs: dict[str, Any] = {"model": model, "temperature": 0.0, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs), None


def grade_context_relevance(prompt: str, response: dict, llm: Any) -> Optional[dict]:
    """Run eval_context_relevance from rag_evaluation.py; None on failure."""
    try:
        from rag_evaluation import eval_context_relevance
        grade = eval_context_relevance(prompt, {"context": response.get("context", "")}, llm)
        return {"score": grade["score"], "relevant": grade["relevant"]}
    except Exception:  # pragma: no cover - network/LLM dependent
        return None


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def load_golden(path: Path) -> list[dict]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def fetch(backend_url: str, skill_id: str, prompt: str, timeout: float = 30.0) -> dict:
    import requests  # already a core dependency

    url = f"{backend_url.rstrip('/')}/skills/{skill_id}/search"
    try:
        resp = requests.post(url, json={"prompt": prompt}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"_error": str(exc), "found": False}


def run(golden: Path, backend_url: str, out: Optional[Path], grade: bool) -> dict:
    items = load_golden(golden)
    llm, grader_skip = (None, "disabled") if not grade else build_grader_llm()
    if grade and grader_skip:
        print(f"[grader] context-relevance grading skipped: {grader_skip}", file=sys.stderr)

    results: list[dict] = []
    for item in items:
        skill_id = SKILL_MAP.get(item.get("skill", "research"), "sift-stylus-research")
        response = fetch(backend_url, skill_id, item["question"])
        row = evaluate_item(item, response)
        if llm and row["found"]:
            row["context_relevance"] = grade_context_relevance(item["question"], response, llm)
        results.append(row)

    summary = aggregate(results)
    summary["grader"] = "ran" if llm else f"skipped:{grader_skip}"
    scorecard = {"summary": summary, "results": results}

    if out:
        out.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(format_scorecard(summary, results))
    return scorecard


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Stylus retrieval eval harness")
    parser.add_argument("--golden", type=Path, default=Path(__file__).parent / "golden_stylus.jsonl")
    parser.add_argument("--backend-url", default=os.environ.get("EVAL_BACKEND_URL", "http://localhost:8001"))
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "scorecard.json")
    parser.add_argument("--grade", action="store_true", help="also run the LLM context-relevance grader")
    parser.add_argument("--min-found-accuracy", type=float, default=None,
                        help="exit non-zero if found_accuracy is below this threshold")
    args = parser.parse_args(list(argv) if argv is not None else None)

    scorecard = run(args.golden, args.backend_url, args.out, args.grade)
    acc = scorecard["summary"].get("found_accuracy")
    if args.min_found_accuracy is not None and (acc is None or acc < args.min_found_accuracy):
        print(f"FAIL: found_accuracy {acc} < {args.min_found_accuracy}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    raise SystemExit(main())
