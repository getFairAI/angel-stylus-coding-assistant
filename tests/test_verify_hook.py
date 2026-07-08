"""Tests for the PostToolUse Stylus verify hook (scripts/stylus-check-hook.sh).

Gating cases (non-.rs, no manifest, non-Stylus crate, disabled) are hermetic and
always run. The compile-failure case needs `cargo` and is skipped without it.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "scripts" / "stylus-check-hook.sh"

bash = shutil.which("bash")
requires_bash = pytest.mark.skipif(bash is None, reason="bash not available")


def run_hook(file_path: str, env_extra: dict | None = None):
    payload = json.dumps({"tool_input": {"file_path": file_path}})
    env = {"PATH": __import__("os").environ.get("PATH", "")}
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [bash, str(HOOK)], input=payload, capture_output=True, text=True, env=env, timeout=120,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _stylus_crate(tmp_path: Path, lib_src: str) -> Path:
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    # package name contains "stylus-sdk" so the hook's project gate matches without
    # needing to fetch the real crate over the network.
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "stylus-sdk-demo"\nversion = "0.1.0"\nedition = "2021"\n'
    )
    (src / "lib.rs").write_text(lib_src)
    return src / "lib.rs"


def test_hook_script_is_executable():
    assert HOOK.exists()
    import os
    assert os.access(HOOK, os.X_OK), "hook must be chmod +x"


@requires_bash
def test_non_rs_edit_is_noop(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hi")
    code, out, err = run_hook(str(f))
    assert code == 0 and out.strip() == "" and err.strip() == ""


@requires_bash
def test_rs_without_manifest_is_noop(tmp_path):
    f = tmp_path / "a.rs"
    f.write_text("fn main() {}")
    code, _, _ = run_hook(str(f))
    assert code == 0


@requires_bash
def test_non_stylus_crate_is_noop(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "plain"\nversion = "0.1.0"\n')
    (tmp_path / "src").mkdir()
    f = tmp_path / "src" / "lib.rs"
    f.write_text("pub fn x() -> u32 { 1 }")
    code, _, _ = run_hook(str(f))
    assert code == 0


@requires_bash
def test_disabled_env_is_noop(tmp_path):
    f = _stylus_crate(tmp_path, "pub fn x() -> u32 { let ; 1 }")  # would fail if run
    code, _, _ = run_hook(str(f), {"STYLUS_HOOK_DISABLE": "1"})
    assert code == 0


@requires_bash
@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
def test_compile_error_returns_exit_2(tmp_path):
    f = _stylus_crate(tmp_path, "pub fn x() -> u32 { let ; 1 }")
    code, _, err = run_hook(str(f))
    assert code == 2
    assert "failed" in err.lower()


@requires_bash
@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
def test_clean_crate_passes(tmp_path):
    f = _stylus_crate(tmp_path, "pub fn x() -> u32 { 1 }")
    code, out, _ = run_hook(str(f))
    assert code == 0
    assert "passed" in out.lower()
