#!/usr/bin/env python3
"""Persist a Stylus porting auditor JSON appendix to disk.

Usage examples:
  # from stdin
  cat report.json | python scripts/save_json_appendix.py --stdin

  # from file
  python scripts/save_json_appendix.py --in report.json

  # explicit output path
  python scripts/save_json_appendix.py --in report.json --out artifacts/my-report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

DEFAULT_OUT_DIR = Path("artifacts/sift-stylus-porting-auditor")
DEFAULT_PREFIX = "stylus-audit"


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return normalized or "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save auditor JSON appendix to disk")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--in", dest="in_path", help="Path to existing JSON appendix file")
    source.add_argument("--stdin", action="store_true", help="Read JSON appendix from stdin")
    parser.add_argument("--out", help="Explicit output file path")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help=f"Output directory when --out is not set (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Filename prefix when --out is not set (default: {DEFAULT_PREFIX})",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing output file")
    return parser.parse_args()


def read_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.stdin:
        raw = sys.stdin.read()
        if not raw.strip():
            raise ValueError("No JSON input received on stdin")
    else:
        in_path = Path(args.in_path)
        if not in_path.exists():
            raise ValueError(f"Input file does not exist: {in_path}")
        raw = in_path.read_text(encoding="utf-8")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("JSON appendix must be an object")

    return payload


def make_default_filename(payload: Dict[str, Any], prefix: str) -> str:
    contract_name = "unknown"
    contract = payload.get("contract")
    if isinstance(contract, dict):
        maybe_name = contract.get("name")
        if isinstance(maybe_name, str) and maybe_name.strip():
            contract_name = maybe_name

    if contract_name == "unknown":
        aggregate = payload.get("aggregate")
        if isinstance(aggregate, dict):
            top = aggregate.get("top_candidates")
            if isinstance(top, list) and top:
                first = top[0]
                if isinstance(first, dict):
                    contracts = first.get("contracts")
                    if isinstance(contracts, list) and contracts and isinstance(contracts[0], str):
                        contract_name = contracts[0]
                    else:
                        maybe_path = first.get("path")
                        if isinstance(maybe_path, str) and maybe_path.strip():
                            contract_name = Path(maybe_path).stem

    if contract_name == "unknown":
        files = payload.get("files")
        if isinstance(files, list) and files:
            first = files[0]
            if isinstance(first, dict):
                contracts = first.get("contract_names")
                if isinstance(contracts, list) and contracts and isinstance(contracts[0], str):
                    contract_name = contracts[0]
                else:
                    maybe_path = first.get("path")
                    if isinstance(maybe_path, str) and maybe_path.strip():
                        contract_name = Path(maybe_path).stem

    stance = "unknown"
    hl = payload.get("high_level_recommendation")
    if isinstance(hl, dict):
        maybe_stance = hl.get("stance")
        if isinstance(maybe_stance, str) and maybe_stance.strip():
            stance = maybe_stance
    if stance == "unknown":
        maybe_band = payload.get("recommendation_band")
        if isinstance(maybe_band, str) and maybe_band.strip():
            stance = maybe_band

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{slug(prefix)}_{slug(contract_name)}_{slug(stance)}_{timestamp}.json"


def resolve_out_path(args: argparse.Namespace, payload: Dict[str, Any]) -> Path:
    if args.out:
        return Path(args.out)

    out_dir = Path(args.out_dir)
    filename = make_default_filename(payload, args.prefix)
    return out_dir / filename


def main() -> int:
    args = parse_args()
    payload = read_payload(args)

    out_path = resolve_out_path(args, payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not args.force:
        raise ValueError(f"Output file already exists: {out_path} (use --force to overwrite)")

    payload["json_appendix_path"] = str(out_path)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(str(out_path))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
