from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional
from urllib.parse import urlparse


GITHUB_URL_RE = re.compile(r"https?://github\.com/[^\s)>\]]+", re.IGNORECASE)
LOCAL_PATH_RE = re.compile(
    r"(?:(?:\.{1,2}/|~/|/)[^\s'\"<>]+|[A-Za-z0-9_.-]+/[^\s'\"<>]+|[A-Za-z]:\\[^\s'\"<>]+|[A-Za-z0-9_.-]+\.sol)"
)
SKIP_GITHUB_PATH_PREFIXES = {
    "issues",
    "pull",
    "pulls",
    "actions",
    "releases",
    "discussions",
    "projects",
    "security",
    "wiki",
}
NON_TARGET_PATH_HINTS = {
    "/test/",
    "/tests/",
    "/mock/",
    "/mocks/",
    "/script/",
    "/scripts/",
    "/example/",
    "/examples/",
    "/bench/",
    "/benchmark/",
    "/docs/",
    "/doc/",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR_SCRIPT = (
    REPO_ROOT
    / "skills"
    / "sift-stylus-porting-auditor"
    / "scripts"
    / "extract_contract_signals.py"
)
CLONE_CACHE_DIR = Path(tempfile.gettempdir()) / "stylus-porting-repo-cache"

_ANALYSIS_CACHE: Dict[str, Dict[str, object]] = {}
SIGNAL_LABELS = {
    "high-compute-signals": "compute-heavy paths",
    "crypto-workload": "crypto-heavy operations",
    "low-external-coupling": "low external coupling",
    "inline-assembly-yul-dependence": "inline assembly or Yul dependence",
    "proxy-upgrade-complexity": "proxy/upgrade complexity",
    "high-external-call-fanout": "high external call fanout",
    "high-integration-coupling": "high integration coupling",
    "simple-token-low-upside-risk": "token/accounting flow with limited compute upside",
}


def _clean_url(value: str) -> str:
    return value.rstrip(".,);:]}>\"'")


def parse_github_target_url(url: str) -> Optional[Dict[str, str]]:
    parsed = urlparse(_clean_url(url))
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None

    mode = "github_repo"
    branch = ""
    subpath = ""
    source_url = f"https://github.com/{owner}/{repo}"

    if len(parts) >= 3:
        marker = parts[2]
        if marker in SKIP_GITHUB_PATH_PREFIXES:
            return None
        if marker in {"blob", "tree"} and len(parts) >= 5:
            branch = parts[3]
            subpath = "/".join(parts[4:])
            mode = "github_file" if marker == "blob" else "github_dir"
            source_url = _clean_url(url)
        elif marker in {"blob", "tree"}:
            mode = "github_repo"
            source_url = _clean_url(url)
        elif marker not in {"", "commit"}:
            # Keep repository-level behavior for unknown subpages.
            mode = "github_repo"

    return {
        "mode": mode,
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "subpath": subpath,
        "source_url": source_url,
        "repo_url": f"https://github.com/{owner}/{repo}",
        "clone_url": f"https://github.com/{owner}/{repo}.git",
    }


def _extract_github_target_from_prompt(prompt: str) -> Optional[Dict[str, str]]:
    for raw in GITHUB_URL_RE.findall(prompt):
        parsed = parse_github_target_url(raw)
        if parsed:
            return parsed
    return None


def _extract_local_target_from_prompt(prompt: str) -> Optional[Path]:
    scrubbed = GITHUB_URL_RE.sub(" ", prompt)
    for candidate in LOCAL_PATH_RE.findall(scrubbed):
        cleaned = candidate.strip("`'\"()[]{}<>")
        cleaned = cleaned.rstrip(".,);:]}>\"'")
        if not cleaned:
            continue

        normalized = cleaned
        if re.match(r"^[A-Za-z]:\\", normalized):
            normalized = normalized.replace("\\", "/")

        path = Path(normalized).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        else:
            path = path.resolve()

        if not path.exists():
            continue

        if path.is_file() and path.suffix != ".sol":
            continue
        if path.is_dir() or (path.is_file() and path.suffix == ".sol"):
            return path
    return None


def _clone_repo(target: Dict[str, str]) -> Path:
    CLONE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    key_material = f"{target['owner']}/{target['repo']}:{target.get('branch') or 'default'}"
    cache_key = hashlib.sha1(key_material.encode("utf-8")).hexdigest()[:12]
    repo_dir = CLONE_CACHE_DIR / f"{target['owner']}-{target['repo']}-{cache_key}"

    if (repo_dir / ".git").exists():
        return repo_dir
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)

    clone_cmd = ["git", "clone", "--depth", "1"]
    if target.get("branch"):
        clone_cmd.extend(["--branch", target["branch"], "--single-branch"])
    clone_cmd.extend([target["clone_url"], str(repo_dir)])

    result = subprocess.run(
        clone_cmd,
        capture_output=True,
        text=True,
        timeout=150,
        check=False,
    )
    if result.returncode == 0:
        return repo_dir

    if target.get("branch"):
        retry_cmd = ["git", "clone", "--depth", "1", target["clone_url"], str(repo_dir)]
        retry = subprocess.run(
            retry_cmd,
            capture_output=True,
            text=True,
            timeout=150,
            check=False,
        )
        if retry.returncode == 0:
            return repo_dir

    raise RuntimeError(
        f"Failed to clone {target['clone_url']}: {result.stderr.strip() or result.stdout.strip()}"
    )


def _detect_repo_branch(repo_dir: Path, fallback: str = "main") -> str:
    try:
        branch = subprocess.check_output(
            ["git", "-C", str(repo_dir), "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
        ).strip()
        if branch and branch != "HEAD":
            return branch
        remote_head = subprocess.check_output(
            ["git", "-C", str(repo_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            text=True,
        ).strip()
        if "/" in remote_head:
            return remote_head.split("/", 1)[1]
    except Exception:
        return fallback
    return fallback


def _run_extractor(target_path: Path) -> Dict[str, object]:
    if not EXTRACTOR_SCRIPT.exists():
        raise RuntimeError(f"Extractor script missing: {EXTRACTOR_SCRIPT}")

    result = subprocess.run(
        [sys.executable, str(EXTRACTOR_SCRIPT), str(target_path)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Extractor failed")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Extractor returned invalid JSON output") from exc


def _file_hint_score(file_payload: Dict[str, object]) -> int:
    upside = int(file_payload.get("upside_score_hint") or 0)
    portability = int(file_payload.get("portability_score_hint") or 0)
    integration = int(file_payload.get("integration_score_hint") or 0)
    score = int(round((upside * 0.7) + (portability * 0.2) + (integration * 0.1)))
    return max(0, min(100, score))


def _label_signal(signal: str) -> str:
    key = str(signal or "").strip()
    if not key:
        return ""
    return SIGNAL_LABELS.get(key, key.replace("-", " "))


def _signal_summary(row: Dict[str, object], max_items: int = 2) -> str:
    positives = [item for item in row.get("positive_drivers") or [] if item][:max_items]
    risks = [item for item in row.get("risk_drivers") or [] if item][:max_items]
    parts = []
    if positives:
        parts.append(f"+ {', '.join(positives)}")
    if risks:
        parts.append(f"- {', '.join(risks)}")
    return " | ".join(parts)


def _count_driver_labels(rows: List[Dict[str, object]], field: str, max_items: int = 6) -> List[Dict[str, object]]:
    counts: Dict[str, int] = {}
    for row in rows:
        for label in row.get(field) or []:
            key = str(label or "").strip()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"driver": label, "count": count} for label, count in ranked[:max_items]]


def _is_candidate_contract_path(path_value: str) -> bool:
    path = str(path_value or "").replace("\\", "/").lower().strip("/")
    if not path:
        return True

    wrapped = f"/{path}/"
    if any(marker in wrapped for marker in NON_TARGET_PATH_HINTS):
        return False

    base = path.rsplit("/", 1)[-1]
    if base.endswith(".t.sol") or base.endswith(".s.sol"):
        return False
    return True


def _build_target_rows(extractor_payload: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for item in extractor_payload.get("files", []):
        path = str(item.get("path") or "")
        contracts = item.get("contract_names") or []
        positive_signals = [str(signal) for signal in item.get("positive_signals") or [] if signal]
        risk_signals = [str(signal) for signal in item.get("risk_signals") or [] if signal]
        rows.append(
            {
                "path": path,
                "contracts": contracts,
                "archetype_hint": item.get("archetype_hint") or "mixed",
                "hint_score": _file_hint_score(item),
                "positive_signals": positive_signals,
                "risk_signals": risk_signals,
                "positive_drivers": [_label_signal(signal) for signal in positive_signals],
                "risk_drivers": [_label_signal(signal) for signal in risk_signals],
            }
        )
    return rows


def _select_targets(rows: List[Dict[str, object]]) -> tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    candidate_rows = [
        row for row in rows if _is_candidate_contract_path(str(row.get("path") or ""))
    ]
    pool = candidate_rows if candidate_rows else rows
    rows_desc = sorted(pool, key=lambda row: int(row.get("hint_score") or 0), reverse=True)
    rows_asc = sorted(pool, key=lambda row: int(row.get("hint_score") or 0))
    high_targets = [row for row in rows_desc if int(row.get("hint_score") or 0) >= 65][:5]
    low_targets = [row for row in rows_asc if int(row.get("hint_score") or 0) <= 45][:5]
    return high_targets, low_targets


def _build_github_blob_url(
    owner: str,
    repo: str,
    branch: str,
    repo_dir: Path,
    path_value: str,
) -> Optional[str]:
    rel_path = ""
    try:
        candidate = Path(path_value)
        if candidate.is_absolute():
            rel = candidate.resolve().relative_to(repo_dir.resolve())
            rel_path = "/".join(rel.parts)
        else:
            rel_path = str(candidate).replace("\\", "/").lstrip("/")
    except Exception:
        return None

    if not rel_path:
        return None
    return f"https://github.com/{owner}/{repo}/blob/{branch}/{rel_path}"


def _build_summary(
    mode: str,
    target: str,
    aggregate: Dict[str, object],
    high_targets: List[Dict[str, object]],
    low_targets: List[Dict[str, object]],
) -> str:
    hints = aggregate.get("hints") or {}
    files = aggregate.get("files") or 0
    contracts = aggregate.get("contracts") or 0

    lines = [
        (
            f"Static contract analysis ({mode}) scanned {files} Solidity files "
            f"across {contracts} contracts for target: {target}."
        ),
        (
            f"Heuristic hint scores: final={hints.get('final', 0)}, "
            f"upside={hints.get('upside', 0)}, portability={hints.get('portability', 0)}, "
            f"integration={hints.get('integration', 0)}."
        ),
    ]

    top_positive = _count_driver_labels(high_targets + low_targets, "positive_drivers")
    top_risks = _count_driver_labels(high_targets + low_targets, "risk_drivers")
    if top_positive:
        lines.append(
            "Top positive drivers: " + ", ".join(f"{item['driver']} ({item['count']})" for item in top_positive)
        )
    if top_risks:
        lines.append(
            "Top risk drivers: " + ", ".join(f"{item['driver']} ({item['count']})" for item in top_risks)
        )

    if high_targets:
        lines.append("High stylus benefit candidates (heuristic):")
        for target_row in high_targets[:5]:
            path = target_row.get("path") or "unknown"
            score = target_row.get("hint_score", 0)
            archetype = target_row.get("archetype_hint", "mixed")
            signals = _signal_summary(target_row)
            if signals:
                lines.append(f"- {path} | score={score} | archetype={archetype} | {signals}")
            else:
                lines.append(f"- {path} | score={score} | archetype={archetype}")

    if low_targets:
        lines.append("Low stylus impact candidates (heuristic):")
        for target_row in low_targets[:5]:
            path = target_row.get("path") or "unknown"
            score = target_row.get("hint_score", 0)
            archetype = target_row.get("archetype_hint", "mixed")
            signals = _signal_summary(target_row)
            if signals:
                lines.append(f"- {path} | score={score} | archetype={archetype} | {signals}")
            else:
                lines.append(f"- {path} | score={score} | archetype={archetype}")

    lines.append(
        "These are static source-level signals and should be validated with runtime profiling and invariants."
    )
    return "\n".join(lines)


def _merge_reference_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    merged: List[Dict[str, str]] = []
    seen = set()
    for row in rows:
        url = str(row.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        if url in seen:
            continue
        seen.add(url)
        merged.append(
            {
                "title": str(row.get("title") or "Reference").strip(),
                "url": url,
                "source": str(row.get("source") or "analysis"),
            }
        )
    return merged


def _analyze_github_target(target: Dict[str, str]) -> Dict[str, object]:
    cache_key = (
        f"github:{target['owner']}/{target['repo']}:"
        f"{target.get('mode')}:{target.get('branch')}:{target.get('subpath')}"
    )
    if cache_key in _ANALYSIS_CACHE:
        cached = dict(_ANALYSIS_CACHE[cache_key])
        cached["cache_hit"] = True
        return cached

    repo_dir = _clone_repo(target)
    branch = _detect_repo_branch(repo_dir, fallback=target.get("branch") or "main")

    analyze_path = repo_dir
    subpath = (target.get("subpath") or "").strip()
    if subpath:
        candidate = repo_dir / subpath
        if candidate.exists():
            analyze_path = candidate

    extractor_payload = _run_extractor(analyze_path)
    aggregate = extractor_payload.get("aggregate") or {}
    rows = _build_target_rows(extractor_payload)
    repo_root = repo_dir.resolve()
    for row in rows:
        current = str(row.get("path") or "")
        try:
            rel = Path(current).resolve().relative_to(repo_root)
            row["path"] = "/".join(rel.parts)
        except Exception:
            row["path"] = current.replace("\\", "/")
    high_targets, low_targets = _select_targets(rows)

    refs = [
        {
            "title": f"{target['owner']}/{target['repo']} repository",
            "url": target["repo_url"],
            "source": "analysis",
        },
        {
            "title": "Original target URL",
            "url": target["source_url"],
            "source": "analysis",
        },
    ]

    for row in high_targets + low_targets:
        blob_url = _build_github_blob_url(
            owner=target["owner"],
            repo=target["repo"],
            branch=branch,
            repo_dir=repo_dir,
            path_value=str(row.get("path") or ""),
        )
        if blob_url:
            refs.append(
                {
                    "title": f"Analyzed contract file: {row.get('path')}",
                    "url": blob_url,
                    "source": "analysis",
                }
            )

    driver_totals = {
        "positive": _count_driver_labels(high_targets + low_targets, "positive_drivers"),
        "risk": _count_driver_labels(high_targets + low_targets, "risk_drivers"),
    }

    result = {
        "mode": target.get("mode") or "github_repo",
        "target": target["source_url"],
        "repo_url": target["repo_url"],
        "branch": branch,
        "analyzed_path": str(analyze_path),
        "aggregate": aggregate,
        "high_targets": high_targets,
        "low_targets": low_targets,
        "driver_totals": driver_totals,
        "summary": _build_summary(
            mode=target.get("mode") or "github_repo",
            target=target["source_url"],
            aggregate=aggregate,
            high_targets=high_targets,
            low_targets=low_targets,
        ),
        "references": _merge_reference_rows(refs),
        "cache_hit": False,
    }
    _ANALYSIS_CACHE[cache_key] = dict(result)
    return result


def _analyze_local_target(path: Path) -> Dict[str, object]:
    cache_key = f"local:{path.resolve()}"
    if cache_key in _ANALYSIS_CACHE:
        cached = dict(_ANALYSIS_CACHE[cache_key])
        cached["cache_hit"] = True
        return cached

    extractor_payload = _run_extractor(path)
    aggregate = extractor_payload.get("aggregate") or {}
    rows = _build_target_rows(extractor_payload)
    high_targets, low_targets = _select_targets(rows)
    driver_totals = {
        "positive": _count_driver_labels(high_targets + low_targets, "positive_drivers"),
        "risk": _count_driver_labels(high_targets + low_targets, "risk_drivers"),
    }

    result = {
        "mode": "local_path",
        "target": str(path),
        "analyzed_path": str(path),
        "aggregate": aggregate,
        "high_targets": high_targets,
        "low_targets": low_targets,
        "driver_totals": driver_totals,
        "summary": _build_summary(
            mode="local_path",
            target=str(path),
            aggregate=aggregate,
            high_targets=high_targets,
            low_targets=low_targets,
        ),
        "references": [],
        "cache_hit": False,
    }
    _ANALYSIS_CACHE[cache_key] = dict(result)
    return result


def analyze_contract_target(user_prompt: str) -> Optional[Dict[str, object]]:
    prompt = str(user_prompt or "").strip()
    if not prompt:
        return None

    github_target = _extract_github_target_from_prompt(prompt)
    if github_target:
        try:
            return _analyze_github_target(github_target)
        except Exception:
            return None

    local_target = _extract_local_target_from_prompt(prompt)
    if local_target:
        try:
            return _analyze_local_target(local_target)
        except Exception:
            return None

    return None
