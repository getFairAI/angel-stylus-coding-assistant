"""Compile-pass metric for Stylus code fixtures.

Measures whether complete Stylus contract fixtures actually build with the real
toolchain (`cargo stylus check`). This is the ground-truth quality signal for the
code-helper skill: a snippet that reads plausibly but does not compile is worthless.

Trust boundary: this runs the toolchain locally / in CI on *curated fixtures* only.
It must never be pointed at untrusted user-submitted code on a shared backend.

Runs are infra-gated: if cargo / cargo-stylus / the wasm32 target are missing, the
metric reports ``status: "skipped"`` with a reason instead of failing. Provision a
CI job with rustup + `rustup target add wasm32-unknown-unknown` + `cargo install
cargo-stylus` to get live numbers.

Fixtures: each subdirectory of ``eval/code_fixtures/`` is a complete cargo project
(``Cargo.toml`` + ``src/lib.rs``). A ``--baseline`` run instead scaffolds a fresh
``cargo stylus new --minimal`` project and checks that, giving a version-matched
smoke test without hardcoding SDK source that could drift.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

WASM_TARGET = "wasm32-unknown-unknown"


# ---------------------------------------------------------------------------
# Capability probe
# ---------------------------------------------------------------------------
def probe_capabilities() -> dict:
    """Detect whether the toolchain needed to compile Stylus contracts is present.

    The wasm32 target must be *installed* (not merely known to rustc) for a build to
    succeed, so we probe `rustup target list --installed`. Without rustup we cannot
    confirm it and treat the target as unavailable to avoid noisy false failures.
    """
    has_cargo = shutil.which("cargo") is not None
    has_cargo_stylus = shutil.which("cargo-stylus") is not None
    has_rustup = shutil.which("rustup") is not None
    has_wasm_target = False
    if has_rustup:
        try:
            out = subprocess.run(
                ["rustup", "target", "list", "--installed"],
                capture_output=True, text=True, timeout=30,
            )
            has_wasm_target = WASM_TARGET in out.stdout
        except Exception:
            has_wasm_target = False

    missing = []
    if not has_cargo:
        missing.append("cargo")
    if not has_cargo_stylus:
        missing.append("cargo-stylus")
    if not has_wasm_target:
        missing.append(f"{WASM_TARGET} target (run: rustup target add {WASM_TARGET})")
    return {
        "cargo": has_cargo,
        "cargo_stylus": has_cargo_stylus,
        "rustup": has_rustup,
        "wasm_target_installed": has_wasm_target,
        "skip_reason": None if not missing else f"missing: {', '.join(missing)}",
    }


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------
def _run_check(project_dir: Path, timeout: float = 600.0) -> dict:
    """Run `cargo stylus check` in a project dir; return pass/fail + tail of output.

    `cargo stylus check` compiles to WASM and dry-runs activation against an RPC
    endpoint (default http://localhost:8547, override with STYLUS_RPC_ENDPOINT — a
    Nitro dev node). It is the real deploy gate, so we use it rather than a bare
    `cargo build`.
    """
    endpoint = os.environ.get("STYLUS_RPC_ENDPOINT")
    cmd = ["cargo", "stylus", "check"]
    if endpoint:
        cmd += ["--endpoint", endpoint]
    try:
        proc = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True, timeout=timeout,
        )
        ok = proc.returncode == 0
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-8:]
        return {"passed": ok, "output_tail": tail}
    except subprocess.TimeoutExpired:
        return {"passed": False, "output_tail": ["timeout"]}
    except Exception as exc:
        return {"passed": False, "output_tail": [str(exc)]}


def check_fixture(project_dir: Path) -> dict:
    result = {"fixture": project_dir.name}
    result.update(_run_check(project_dir))
    return result


def run_baseline(workdir: Path) -> Optional[dict]:
    """Scaffold `cargo stylus new --minimal` and check it. None if scaffold fails."""
    proj = workdir / "baseline"
    try:
        proc = subprocess.run(
            ["cargo", "stylus", "new", "--minimal", "baseline"],
            cwd=workdir, capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0 or not proj.exists():
            return {"fixture": "baseline", "passed": False,
                    "output_tail": (proc.stderr or proc.stdout).strip().splitlines()[-8:]}
    except Exception as exc:
        return {"fixture": "baseline", "passed": False, "output_tail": [str(exc)]}
    result = {"fixture": "baseline"}
    result.update(_run_check(proj))
    return result


# ---------------------------------------------------------------------------
# Aggregation (pure — unit tested)
# ---------------------------------------------------------------------------
def aggregate_compile_results(results: list[dict], skipped_reason: Optional[str]) -> dict:
    if skipped_reason:
        return {"status": "skipped", "reason": skipped_reason,
                "total": 0, "passed": 0, "compile_pass_rate": None, "results": []}
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    return {
        "status": "ran",
        "reason": None,
        "total": total,
        "passed": passed,
        "compile_pass_rate": round(passed / total, 4) if total else None,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run(fixtures_dir: Path, include_baseline: bool, out: Optional[Path]) -> dict:
    caps = probe_capabilities()
    if caps["skip_reason"]:
        summary = aggregate_compile_results([], caps["skip_reason"])
        summary["capabilities"] = caps
        _emit(summary, out)
        return summary

    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="stylus-compile-") as tmp:
        if include_baseline:
            baseline = run_baseline(Path(tmp))
            if baseline:
                results.append(baseline)
        if fixtures_dir.is_dir():
            for proj in sorted(p for p in fixtures_dir.iterdir() if (p / "Cargo.toml").exists()):
                results.append(check_fixture(proj))

    summary = aggregate_compile_results(results, None)
    summary["capabilities"] = caps
    _emit(summary, out)
    return summary


def _emit(summary: dict, out: Optional[Path]) -> None:
    if out:
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if summary["status"] == "skipped":
        print(f"compile-pass: SKIPPED ({summary['reason']})")
        return
    print(f"compile-pass: {summary['passed']}/{summary['total']} "
          f"(rate={summary['compile_pass_rate']})")
    for r in summary["results"]:
        if not r.get("passed"):
            print(f"  FAIL {r['fixture']}: {' / '.join(r.get('output_tail', []))[-200:]}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stylus compile-pass metric")
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).parent / "code_fixtures")
    parser.add_argument("--baseline", action="store_true", help="also scaffold+check cargo stylus new --minimal")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "compile_scorecard.json")
    parser.add_argument("--require-toolchain", action="store_true",
                        help="exit non-zero if the toolchain is missing (instead of skipping)")
    args = parser.parse_args(argv)

    summary = run(args.fixtures, args.baseline, args.out)
    if summary["status"] == "skipped":
        return 1 if args.require_toolchain else 0
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
