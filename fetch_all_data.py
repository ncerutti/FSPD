#!/usr/bin/env python3
"""
Fetch all supported ETL sources into the data folder.

Usage:
    python fetch_all_data.py
    python fetch_all_data.py --no_csv --fapda_limit 500
    python fetch_all_data.py --pine_flow_id DSD_CAPMF@DF_CAPMF
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run FAPDA, GIFNA, and PINE ETL fetchers and store outputs under data/."
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Base output directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--no_csv",
        action="store_true",
        help="Skip CSV exports for all sources.",
    )
    parser.add_argument(
        "--fapda_limit",
        type=int,
        default=None,
        help="Optional limit for FAPDA records (for smoke runs).",
    )
    parser.add_argument(
        "--skip_gifna_boundaries",
        action="store_true",
        help="Skip WHO boundaries extraction in GIFNA fetch.",
    )
    parser.add_argument(
        "--pine_flow_id",
        action="append",
        default=None,
        help="PINE flow ID to fetch (repeatable). If omitted, PINE defaults are used.",
    )
    parser.add_argument(
        "--pine_start_period",
        type=str,
        default=None,
        help="Optional PINE startPeriod filter (e.g. 2010).",
    )
    parser.add_argument(
        "--pine_end_period",
        type=str,
        default=None,
        help="Optional PINE endPeriod filter (e.g. 2025).",
    )
    return parser.parse_args()


def run_command(label: str, command: list[str]) -> None:
    print(f"[{label}] {' '.join(command)}")
    subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    fapda_output = output_dir / "fapda"
    gifna_output = output_dir / "gifna"
    pine_output = output_dir / "pine"

    fapda_cmd = [
        sys.executable,
        str(REPO_ROOT / "fetch_fapda_data.py"),
        "--resource",
        "both",
        "--output_dir",
        str(fapda_output),
    ]
    if args.fapda_limit is not None:
        fapda_cmd.extend(["--limit", str(args.fapda_limit)])
    if args.no_csv:
        fapda_cmd.append("--no_csv")
    run_command("fapda", fapda_cmd)

    gifna_cmd = [
        sys.executable,
        str(REPO_ROOT / "fetch_gifna_data.py"),
        "--output_dir",
        str(gifna_output),
    ]
    if args.skip_gifna_boundaries:
        gifna_cmd.append("--skip_boundaries")
    if args.no_csv:
        gifna_cmd.append("--no_csv")
    run_command("gifna", gifna_cmd)

    pine_cmd = [
        sys.executable,
        str(REPO_ROOT / "fetch_pine_data.py"),
        "--output_dir",
        str(pine_output),
    ]
    if args.pine_flow_id:
        for flow_id in args.pine_flow_id:
            pine_cmd.extend(["--flow_id", flow_id])
    if args.pine_start_period:
        pine_cmd.extend(["--start_period", args.pine_start_period])
    if args.pine_end_period:
        pine_cmd.extend(["--end_period", args.pine_end_period])
    if args.no_csv:
        pine_cmd.append("--no_csv")
    run_command("pine", pine_cmd)

    print(f"All fetches completed. Outputs saved under: {output_dir}")


if __name__ == "__main__":
    main()
