#!/usr/bin/env python3
"""Extract Solidity migration signals for Stylus candidacy triage.

This script is intentionally heuristic. It does not prove safety or runtime behavior.

Usage:
  python scripts/extract_contract_signals.py contracts/MyContract.sol
  python scripts/extract_contract_signals.py path/to/repo --json-out signals.json
  cat MyContract.sol | python scripts/extract_contract_signals.py --stdin --name MyContract.sol
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)

PATTERNS = {
    "contracts": re.compile(r"\bcontract\s+([A-Za-z_][A-Za-z0-9_]*)"),
    "functions": re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    "loops": re.compile(r"\b(for|while)\s*\("),
    "do_loops": re.compile(r"\bdo\s*\{"),
    "hash_ops": re.compile(r"\b(keccak256|sha256|ripemd160|ecrecover)\s*\("),
    "crypto_terms": re.compile(r"\b(poseidon|merkle|ed25519|secp256k1|bls12|bn254|pairing)\b", re.IGNORECASE),
    "abi_ops": re.compile(r"\babi\.(encode|decode|encodePacked|encodeWithSelector)\s*\("),
    "mapping_decl": re.compile(r"\bmapping\s*\("),
    "storage_kw": re.compile(r"\bstorage\b"),
    "assembly": re.compile(r"\bassembly\b"),
    "emit": re.compile(r"\bemit\b"),
    "imports": re.compile(r"^\s*import\s+", re.MULTILINE),
    "inherits": re.compile(r"\bcontract\s+[A-Za-z_][A-Za-z0-9_]*\s+is\s+([^\{]+)"),
    "ext_calls": re.compile(r"\.\s*(call|delegatecall|staticcall)\s*\("),
    "value_calls": re.compile(r"\.\s*(send|transfer)\s*\("),
    "proxy_terms": re.compile(
        r"\b(UUPS|ERC1967|TransparentUpgradeableProxy|BeaconProxy|ProxyAdmin|implementation|delegatecall|initializer)\b",
        re.IGNORECASE,
    ),
    "token_terms": re.compile(r"\b(ERC20|ERC721|ERC1155|IERC20|IERC721|IERC1155)\b"),
}

IGNORE_DIRS = {"node_modules", "dist", "build", "out", "artifacts", ".git"}


@dataclass
class FileSignals:
    path: str
    contract_names: List[str]
    loc: int
    functions: int
    loops: int
    hash_ops: int
    crypto_terms: int
    abi_ops: int
    mapping_decl: int
    storage_kw: int
    assembly: int
    emit_count: int
    imports: int
    inheritance_edges: int
    ext_calls: int
    value_calls: int
    delegatecalls: int
    proxy_terms: int
    token_terms: int
    upside_score_hint: int
    portability_score_hint: int
    integration_score_hint: int
    archetype_hint: str
    positive_signals: List[str]
    risk_signals: List[str]


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def count(pattern_key: str, text: str) -> int:
    return len(PATTERNS[pattern_key].findall(text))


def count_inheritance_edges(text: str) -> int:
    total = 0
    for match in PATTERNS["inherits"].finditer(text):
        clause = match.group(1)
        parents = [part.strip() for part in clause.split(",") if part.strip()]
        total += len(parents)
    return total


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def detect_archetype(
    hash_ops: int,
    crypto_terms: int,
    loops: int,
    token_terms: int,
    proxy_terms: int,
    delegatecalls: int,
    ext_calls: int,
) -> str:
    if (hash_ops + crypto_terms) >= 3 or (hash_ops >= 1 and loops >= 2):
        return "crypto-heavy"
    if delegatecalls >= 1 or proxy_terms >= 3:
        return "proxy-upgrade-heavy"
    if token_terms >= 2 and loops <= 1 and hash_ops == 0:
        return "simple-token-accounting"
    if ext_calls >= 3:
        return "router-orchestration"
    return "isolated-utility-or-mixed"


def analyze_file(path: Path, text: str) -> FileSignals:
    cleaned = strip_comments(text)
    lines = [line for line in cleaned.splitlines() if line.strip()]

    contract_names = [match.group(1) for match in PATTERNS["contracts"].finditer(cleaned)]

    functions = count("functions", cleaned)
    loops = count("loops", cleaned) + count("do_loops", cleaned)
    hash_ops = count("hash_ops", cleaned)
    crypto_terms = count("crypto_terms", cleaned)
    abi_ops = count("abi_ops", cleaned)
    mapping_decl = count("mapping_decl", cleaned)
    storage_kw = count("storage_kw", cleaned)
    assembly = count("assembly", cleaned)
    emit_count = count("emit", cleaned)
    imports = count("imports", cleaned)
    inheritance_edges = count_inheritance_edges(cleaned)
    ext_calls = count("ext_calls", cleaned)
    value_calls = count("value_calls", cleaned)
    delegatecalls = len(re.findall(r"\.\s*delegatecall\s*\(", cleaned))
    proxy_terms = count("proxy_terms", cleaned)
    token_terms = count("token_terms", cleaned)

    compute_raw = (loops * 3.0) + (hash_ops * 5.0) + (crypto_terms * 6.0) + (abi_ops * 1.5)
    storage_raw = (mapping_decl * 3.5) + (storage_kw * 1.0)
    coupling_raw = (ext_calls * 2.5) + (inheritance_edges * 2.0) + (imports * 1.5)
    portability_penalty = (assembly * 14.0) + (delegatecalls * 10.0) + (proxy_terms * 2.5)

    upside_score_hint = clamp_score(50 + (compute_raw * 2.2) - (storage_raw * 0.9) - (coupling_raw * 0.8))
    portability_score_hint = clamp_score(100 - portability_penalty - (inheritance_edges * 1.5))
    integration_score_hint = clamp_score(100 - (coupling_raw * 4.2) - (value_calls * 4.0))

    archetype_hint = detect_archetype(
        hash_ops=hash_ops,
        crypto_terms=crypto_terms,
        loops=loops,
        token_terms=token_terms,
        proxy_terms=proxy_terms,
        delegatecalls=delegatecalls,
        ext_calls=ext_calls,
    )

    positive_signals: List[str] = []
    risk_signals: List[str] = []

    if upside_score_hint >= 70:
        positive_signals.append("high-compute-signals")
    if (hash_ops + crypto_terms) >= 2:
        positive_signals.append("crypto-workload")
    if ext_calls <= 1:
        positive_signals.append("low-external-coupling")

    if assembly > 0:
        risk_signals.append("inline-assembly-yul-dependence")
    if delegatecalls > 0 or proxy_terms >= 3:
        risk_signals.append("proxy-upgrade-complexity")
    if integration_score_hint < 45:
        risk_signals.append("high-integration-coupling")
    if token_terms >= 2 and upside_score_hint < 65:
        risk_signals.append("simple-token-low-upside-risk")

    return FileSignals(
        path=str(path),
        contract_names=contract_names,
        loc=len(lines),
        functions=functions,
        loops=loops,
        hash_ops=hash_ops,
        crypto_terms=crypto_terms,
        abi_ops=abi_ops,
        mapping_decl=mapping_decl,
        storage_kw=storage_kw,
        assembly=assembly,
        emit_count=emit_count,
        imports=imports,
        inheritance_edges=inheritance_edges,
        ext_calls=ext_calls,
        value_calls=value_calls,
        delegatecalls=delegatecalls,
        proxy_terms=proxy_terms,
        token_terms=token_terms,
        upside_score_hint=upside_score_hint,
        portability_score_hint=portability_score_hint,
        integration_score_hint=integration_score_hint,
        archetype_hint=archetype_hint,
        positive_signals=positive_signals,
        risk_signals=risk_signals,
    )


def collect_solidity_files(target: Path) -> List[Path]:
    if target.is_file() and target.suffix == ".sol":
        return [target]

    files: List[Path] = []
    for path in target.rglob("*.sol"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def aggregate(signals: Sequence[FileSignals]) -> Dict[str, object]:
    if not signals:
        return {
            "files": 0,
            "contracts": 0,
            "archetypes": {},
            "hints": {
                "upside": 0,
                "portability": 0,
                "integration": 0,
                "final": 0,
            },
            "top_candidates": [],
        }

    total_contracts = sum(len(item.contract_names) for item in signals)
    archetypes: Dict[str, int] = {}
    for item in signals:
        archetypes[item.archetype_hint] = archetypes.get(item.archetype_hint, 0) + 1

    avg_upside = sum(item.upside_score_hint for item in signals) / len(signals)
    avg_portability = sum(item.portability_score_hint for item in signals) / len(signals)
    avg_integration = sum(item.integration_score_hint for item in signals) / len(signals)
    final_hint = clamp_score((avg_upside * 0.7) + (avg_portability * 0.2) + (avg_integration * 0.1))

    ranked = sorted(
        signals,
        key=lambda item: (item.upside_score_hint * 0.7)
        + (item.portability_score_hint * 0.2)
        + (item.integration_score_hint * 0.1),
        reverse=True,
    )

    top_candidates = [
        {
            "path": item.path,
            "contracts": item.contract_names,
            "archetype_hint": item.archetype_hint,
            "hint_score": clamp_score(
                (item.upside_score_hint * 0.7)
                + (item.portability_score_hint * 0.2)
                + (item.integration_score_hint * 0.1)
            ),
            "reason": ", ".join(item.positive_signals[:2]) or "mixed-signals",
        }
        for item in ranked[:5]
    ]

    return {
        "files": len(signals),
        "contracts": total_contracts,
        "archetypes": archetypes,
        "hints": {
            "upside": clamp_score(avg_upside),
            "portability": clamp_score(avg_portability),
            "integration": clamp_score(avg_integration),
            "final": final_hint,
        },
        "top_candidates": top_candidates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Solidity candidacy signals for Stylus triage")
    parser.add_argument("target", nargs="?", help="Solidity file or directory")
    parser.add_argument("--stdin", action="store_true", help="Read Solidity source from stdin")
    parser.add_argument("--name", default="stdin.sol", help="Display name when using --stdin")
    parser.add_argument("--json-out", help="Optional path to write JSON output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    signals: List[FileSignals] = []

    if args.stdin:
        raw = sys.stdin.read()
        if not raw.strip():
            print("No input received on stdin", file=sys.stderr)
            return 1
        signals.append(analyze_file(Path(args.name), raw))
    else:
        if not args.target:
            print("Provide a target path or use --stdin", file=sys.stderr)
            return 1
        target = Path(args.target)
        if not target.exists():
            print(f"Target does not exist: {target}", file=sys.stderr)
            return 1

        files = collect_solidity_files(target)
        if not files:
            print(f"No Solidity files found under: {target}", file=sys.stderr)
            return 1

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = file_path.read_text(encoding="latin-1")
            signals.append(analyze_file(file_path, content))

    payload = {
        "tool": "extract_contract_signals",
        "version": "1.0.0",
        "aggregate": aggregate(signals),
        "files": [item.__dict__ for item in signals],
    }

    rendered = json.dumps(payload, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
