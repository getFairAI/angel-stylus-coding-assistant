"""Tests for the PostToolUse Stylus verify hook (scripts/stylus-check-hook.sh).

Gating cases (non-.rs, no manifest, non-Stylus crate, disabled) are hermetic and
always run. The compile-failure case needs `cargo` and is skipped without it.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "scripts" / "stylus-check-hook.sh"

bash = shutil.which("bash")
requires_bash = pytest.mark.skipif(bash is None, reason="bash not available")
requires_python3 = pytest.mark.skipif(shutil.which("python3") is None, reason="python3 not available")


def run_hook_raw(payload: dict, env_extra: dict | None = None):
    env = {"PATH": os.environ.get("PATH", "")}
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [bash, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=120,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_hook(file_path: str, env_extra: dict | None = None):
    """Claude Code payload shape."""
    return run_hook_raw({"tool_input": {"file_path": file_path}}, env_extra)


def codex_patch_payload(rel_path: str, cwd: str):
    """Codex apply_patch payload — file path embedded in tool_input.command."""
    command = f"*** Begin Patch\n*** Update File: {rel_path}\n@@\n+// edit\n*** End Patch"
    return {"tool_name": "apply_patch", "cwd": cwd, "tool_input": {"command": command}}


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


# --- Codex apply_patch payload shape (path in tool_input.command, relative to cwd) ---
@requires_bash
@requires_python3
def test_codex_non_rs_patch_is_noop(tmp_path):
    (tmp_path / "README.md").write_text("# hi")
    code, out, err = run_hook_raw(codex_patch_payload("README.md", str(tmp_path)))
    assert code == 0 and out.strip() == "" and err.strip() == ""


@requires_bash
@requires_python3
@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
def test_codex_apply_patch_compile_error_exit_2(tmp_path):
    _stylus_crate(tmp_path, "pub fn x() -> u32 { let ; 1 }")
    code, _, err = run_hook_raw(codex_patch_payload("src/lib.rs", str(tmp_path)))
    assert code == 2
    assert "failed" in err.lower()


@requires_bash
@requires_python3
@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
def test_codex_apply_patch_clean_passes(tmp_path):
    _stylus_crate(tmp_path, "pub fn x() -> u32 { 1 }")
    code, out, _ = run_hook_raw(codex_patch_payload("src/lib.rs", str(tmp_path)))
    assert code == 0
    assert "passed" in out.lower()
