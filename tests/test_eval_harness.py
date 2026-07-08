"""Unit tests for the eval harness pure logic (no backend / no toolchain needed)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "eval"))

import compile_pass  # noqa: E402
import run_eval  # noqa: E402


def _resp(found=True, context="", references=None, chunks=3, error=None):
    r = {"found": found, "context": context, "references": references or [], "chunks_used": chunks}
    if error:
        r["_error"] = error
    return r


def test_evaluate_item_source_recall_and_found_correct():
    item = {"id": "erc20", "skill": "code_helper", "question": "erc20?",
            "expect_found": True, "expect_source_contains": ["erc20", "token"]}
    resp = _resp(found=True, context="An ERC20 TOKEN example",
                 references=[{"title": "ERC20", "url": "https://x/erc20", "source": "docs"}])
    row = run_eval.evaluate_item(item, resp)
    assert row["found_correct"] is True
    assert row["source_recall"] == 1.0  # both 'erc20' and 'token' present (case-insensitive)
    assert set(row["matched_sources"]) == {"erc20", "token"}


def test_evaluate_item_negative_case_correct_when_not_found():
    item = {"id": "off-topic", "skill": "research", "question": "solana?",
            "expect_found": False, "expect_source_contains": []}
    row = run_eval.evaluate_item(item, _resp(found=False))
    assert row["found_correct"] is True
    assert row["source_recall"] is None


def test_evaluate_item_partial_recall():
    item = {"id": "x", "skill": "research", "question": "q",
            "expect_found": True, "expect_source_contains": ["cargo stylus", "deploy"]}
    row = run_eval.evaluate_item(item, _resp(context="run cargo stylus check"))
    assert row["source_recall"] == 0.5


def test_aggregate_rates():
    results = [
        run_eval.evaluate_item({"id": "a", "expect_found": True, "expect_source_contains": ["a"]},
                               _resp(found=True, context="a")),
        run_eval.evaluate_item({"id": "b", "expect_found": True, "expect_source_contains": ["z"]},
                               _resp(found=True, context="nope")),
        run_eval.evaluate_item({"id": "c", "expect_found": False, "expect_source_contains": []},
                               _resp(found=False)),
    ]
    summary = run_eval.aggregate(results)
    assert summary["total"] == 3
    assert summary["found_accuracy"] == 1.0
    assert summary["negative_correct_rate"] == 1.0
    assert summary["avg_source_recall"] == 0.5  # (1.0 + 0.0) / 2


def test_aggregate_counts_errors_separately():
    results = [run_eval.evaluate_item({"id": "a", "expect_found": True}, _resp(error="conn refused"))]
    summary = run_eval.aggregate(results)
    assert summary["errored"] == 1
    assert summary["scored"] == 0
    assert summary["found_accuracy"] is None


def test_format_scorecard_contains_metrics():
    summary = {"total": 1, "scored": 1, "errored": 0, "found_accuracy": 1.0,
               "positive_found_rate": 1.0, "negative_correct_rate": None,
               "avg_source_recall": 1.0, "avg_chunks_used": 3}
    text = run_eval.format_scorecard(summary, [])
    assert "found_accuracy" in text and "1.0" in text


def test_golden_set_is_valid_and_covers_skills():
    items = run_eval.load_golden(REPO_ROOT / "eval" / "golden_stylus.jsonl")
    assert len(items) >= 30
    skills = {i["skill"] for i in items}
    assert {"research", "code_helper"} <= skills
    # every skill maps to a registered backend id
    assert all(i["skill"] in run_eval.SKILL_MAP for i in items)
    # at least one negative (found:false) case for honesty testing
    assert any(i["expect_found"] is False for i in items)


def test_compile_aggregate_skipped():
    summary = compile_pass.aggregate_compile_results([], "missing: cargo-stylus")
    assert summary["status"] == "skipped"
    assert summary["compile_pass_rate"] is None


def test_compile_aggregate_ran():
    results = [{"fixture": "a", "passed": True}, {"fixture": "b", "passed": False}]
    summary = compile_pass.aggregate_compile_results(results, None)
    assert summary["status"] == "ran"
    assert summary["total"] == 2 and summary["passed"] == 1
    assert summary["compile_pass_rate"] == 0.5


def test_probe_capabilities_shape():
    caps = compile_pass.probe_capabilities()
    assert set(caps) >= {"cargo", "cargo_stylus", "wasm_target_installed", "skip_reason"}
