#!/usr/bin/env bash
#
# PostToolUse hook: after an Edit/Write to a `.rs` file inside a Stylus project,
# type-check the crate and feed any compiler errors back to the agent so it can
# self-correct (the `retrieve -> generate -> verify -> fix` loop).
#
# Behaviour contract:
#   - No-op (exit 0, silent) when: the edit is not a .rs file, the file is not in
#     a Stylus project (no Cargo.toml with `stylus-sdk`), cargo is missing, or the
#     hook is disabled via STYLUS_HOOK_DISABLE=1.
#   - On a compile error: print the errors to stderr and exit 2, which Claude Code
#     surfaces back to the agent as actionable feedback.
#   - On success: a short note on stdout (shown in the transcript) and exit 0.
#
# Fast by default: runs `cargo check` (type-check, no codegen, no network). Set
# STYLUS_HOOK_FULL=1 to run the heavier `cargo stylus check` (WASM build + size +
# activation dry-run against STYLUS_RPC_ENDPOINT), which is the true deploy gate.
#
# Env:
#   STYLUS_HOOK_DISABLE=1   disable the hook entirely
#   STYLUS_HOOK_FULL=1      run `cargo stylus check` instead of `cargo check`
#   STYLUS_RPC_ENDPOINT     RPC used by the full check (default cargo-stylus default)
set -uo pipefail

[ "${STYLUS_HOOK_DISABLE:-}" = "1" ] && exit 0

# Read the payload once into a temp file — apply_patch diffs can be large, so avoid
# passing it through argv/env.
payload_file="$(mktemp 2>/dev/null || echo "/tmp/stylus-hook.$$")"
trap 'rm -f "$payload_file"' EXIT
cat > "$payload_file"

# --- extract the edited .rs file path, tolerant of multiple host payload shapes --
# Claude Code: tool_input.file_path (absolute).
# Codex:       apply_patch — paths embedded in tool_input.command, relative to cwd.
# python3 handles both; jq is a fallback for the simple Claude Code shape only.
PY_EXTRACT='
import sys, os, json, re
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = d.get("tool_input") or {}
cwd = d.get("cwd") or ""
cands = []
fp = ti.get("file_path") or ti.get("filePath")
if fp:
    cands.append(fp)
cmd = ti.get("command")
if isinstance(cmd, str) and "*** " in cmd:
    cands += re.findall(r"\*\*\*\s+(?:Add|Update|Delete)\s+File:\s+(.+)", cmd)
    cands += re.findall(r"\*\*\*\s+Move to:\s+(.+)", cmd)
for c in cands:
    c = c.strip()
    p = c if os.path.isabs(c) else (os.path.join(cwd, c) if cwd else c)
    if p.endswith(".rs"):
        print(os.path.normpath(p))
        break
'

file_path=""
if command -v python3 >/dev/null 2>&1; then
  file_path="$(python3 -c "$PY_EXTRACT" < "$payload_file" 2>/dev/null)"
elif command -v jq >/dev/null 2>&1; then
  file_path="$(jq -r '.tool_input.file_path // .tool_input.filePath // empty' < "$payload_file" 2>/dev/null)"
fi

[ -z "$file_path" ] && exit 0
case "$file_path" in
  *.rs) ;;
  *) exit 0 ;;
esac
[ -f "$file_path" ] || exit 0

# --- walk up to the crate manifest and confirm it is a Stylus project -----------
dir="$(cd "$(dirname "$file_path")" 2>/dev/null && pwd)" || exit 0
manifest=""
while [ -n "$dir" ] && [ "$dir" != "/" ]; do
  if [ -f "$dir/Cargo.toml" ]; then
    manifest="$dir/Cargo.toml"
    break
  fi
  dir="$(dirname "$dir")"
done
[ -z "$manifest" ] && exit 0
grep -q 'stylus-sdk' "$manifest" 2>/dev/null || exit 0

command -v cargo >/dev/null 2>&1 || exit 0

project_dir="$(dirname "$manifest")"

# --- run the check --------------------------------------------------------------
if [ "${STYLUS_HOOK_FULL:-}" = "1" ] && command -v cargo-stylus >/dev/null 2>&1; then
  cmd=(cargo stylus check)
  [ -n "${STYLUS_RPC_ENDPOINT:-}" ] && cmd+=(--endpoint "$STYLUS_RPC_ENDPOINT")
  label="cargo stylus check"
else
  # Build the command incrementally (avoids empty-array expansion under `set -u`
  # on bash 3.2). Prefer the wasm target when installed (wasm-accurate), else fall
  # back to the host target so we still catch type errors offline.
  cmd=(cargo check --quiet --manifest-path "$manifest")
  if rustup target list --installed 2>/dev/null | grep -q 'wasm32-unknown-unknown'; then
    cmd+=(--target wasm32-unknown-unknown)
  fi
  label="cargo check"
fi

output="$(cd "$project_dir" && "${cmd[@]}" 2>&1)"
status=$?

if [ "$status" -ne 0 ]; then
  {
    echo "Stylus verify (${label}) failed for $(basename "$file_path"):"
    echo "$output" | tail -40
    echo ""
    echo "Fix the compile errors above before continuing."
  } >&2
  exit 2
fi

echo "Stylus verify (${label}) passed for $(basename "$file_path")."
exit 0
