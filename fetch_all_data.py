#!/usr/bin/env python3
"""
Fetch all supported ETL sources into the data folder.

CI-ready orchestrator: each source runs independently, failures are
collected, a per-source summary is printed at the end, and the exit
code is non-zero if any selected source failed.

Usage:
    python3 fetch_all_data.py
    python3 fetch_all_data.py --source fapda --fapda_limit 50
    python3 fetch_all_data.py --source pine
    python3 fetch_all_data.py --no_csv
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data"
SOURCES = ("fapda", "gifna", "pine")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run FAPDA, GIFNA, and PINE ETL fetchers and store outputs under data/."
    )
    parser.add_argument(
        "--source",
        choices=list(SOURCES) + ["all"],
        default="all",
        help="Fetch a single source, or 'all' (default).",
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
    return parser.parse_args()


def run_command(label: str, command: list[str]) -> None:
    print(f"[{label}] {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def read_metadata_summary(metadata_path: Path) -> list[str]:
    """Return human-readable per-asset lines from a *_etl_metadata.json file."""
    lines: list[str] = []
    try:
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return lines

    # FAPDA: {"summaries": {name: {rows, output_path, ...}}}
    for name, summary in (meta.get("summaries") or {}).items():
        lines.append(f"{name}: {summary.get('rows')} rows -> {summary.get('output_path')}")
    # GIFNA: {"assets": {name: {records, jsonl_path, ...}}}
    for name, summary in (meta.get("assets") or {}).items():
        if isinstance(summary, dict):
            lines.append(f"{name}: {summary.get('records')} records -> {summary.get('jsonl_path')}")
    # PINE: {"downloads": {name: {rows, csv_path, ...}}}
    for name, summary in (meta.get("downloads") or {}).items():
        if isinstance(summary, dict):
            lines.append(f"{name}: {summary.get('rows')} rows -> {summary.get('csv_path')}")
    return lines


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = list(SOURCES) if args.source == "all" else [args.source]

    commands: dict[str, tuple[list[str], Path]] = {}

    fapda_output = output_dir / "fapda"
    fapda_cmd = [
        sys.executable,
        str(REPO_ROOT / "fetch_fapda_data.py"),
        "--resource", "both",
        "--output_dir", str(fapda_output),
    ]
    if args.fapda_limit is not None:
        fapda_cmd.extend(["--limit", str(args.fapda_limit)])
    if args.no_csv:
        fapda_cmd.append("--no_csv")
    commands["fapda"] = (fapda_cmd, fapda_output / "fapda_etl_metadata.json")

    gifna_output = output_dir / "gifna"
    gifna_cmd = [
        sys.executable,
        str(REPO_ROOT / "fetch_gifna_data.py"),
        "--output_dir", str(gifna_output),
    ]
    if args.skip_gifna_boundaries:
        gifna_cmd.append("--skip_boundaries")
    if args.no_csv:
        gifna_cmd.append("--no_csv")
    commands["gifna"] = (gifna_cmd, gifna_output / "gifna_etl_metadata.json")

    pine_output = output_dir / "pine"
    pine_cmd = [
        sys.executable,
        str(REPO_ROOT / "fetch_pine_data.py"),
        "--output_dir", str(pine_output),
    ]
    commands["pine"] = (pine_cmd, pine_output / "pine_etl_metadata.json")

    results: dict[str, str] = {}
    failures: dict[str, str] = {}

    for source in selected:
        command, metadata_path = commands[source]
        started = time.monotonic()
        try:
            run_command(source, command)
        except subprocess.CalledProcessError as exc:
            failures[source] = f"exit code {exc.returncode}"
            results[source] = "FAILED"
            print(f"[{source}] FAILED ({exc.returncode})", flush=True)
            continue
        except Exception as exc:  # noqa: BLE001 - keep going, report at end
            failures[source] = str(exc)
            results[source] = "FAILED"
            print(f"[{source}] FAILED ({exc})", flush=True)
            continue
        elapsed = time.monotonic() - started
        results[source] = "OK"
        print(f"[{source}] OK in {elapsed:.0f}s", flush=True)
        for line in read_metadata_summary(metadata_path):
            print(f"[{source}]   {line}", flush=True)

    print("\n=== Fetch summary ===")
    for source in selected:
        status = results.get(source, "SKIPPED")
        detail = f" ({failures[source]})" if source in failures else ""
        print(f"{source}: {status}{detail}")
    print(f"Outputs under: {output_dir}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
