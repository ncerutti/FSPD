"""
Incremental update pipeline: fetcher outputs -> new rows to classify.

Takes the latest fetcher outputs (FAPDA JSONL, PINE instruments CSV, optional
GIFNA manual CSV), transforms each source to the canonical 49-column schema
(shared with build_dataset.py), deduplicates against the existing canonical
dataset on the stable per-source (db, id) key, and writes:

  1. data/updates/new_rows_<YYYYMMDD>.parquet — only genuinely new rows,
     canonical schema, no classification columns, ready for the classifier
     (only written when there are new rows);
  2. the updated combined dataset (--output, default data/FSPD_new.parquet);
  3. a JSON summary with per-source fetched/new/duplicate counts and a GIFNA
     freshness signal — printed and saved for the GitHub Actions PR body.

Dedupe keys: FAPDA decisions/frameworks use the FAPDA record id (same id the
record URLs carry as policydecisionid/policyframeworkid, so the JSONL path and
the manual-export path agree); PINE uses InstrumentId; GIFNA uses Policy_Id.

Pure pandas — no ML imports. Missing source files are skipped (and flagged in
the summary), so one failed fetcher does not block the rest.

Usage (defaults match the fetcher output locations):
    .venv-fetch/bin/python3 -m src.pipeline.update_dataset
    .venv-fetch/bin/python3 -m src.pipeline.update_dataset \
        --gifna_csv data/gifna/original/GIFNA-...-2026-05-16.csv \
        --output /tmp/FSPD_updated.parquet
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from src.pipeline.build_dataset import CANONICAL_COLUMNS, load_gifna, load_pine  # noqa: E402
from src.pipeline.transform import _read_jsonl, transform_decision, transform_framework  # noqa: E402

# transform.py labels decisions "FAPDA"; the canonical dataset uses
# "FAPDA_decisions" (build_dataset.py). Normalise so the (db, id) dedupe key
# matches across both transform paths.
_DB_NORMALISE = {"FAPDA": "FAPDA_decisions"}

_NUMERIC_COLS = ("y_start", "y_end", "gendermainstreamed", "nutritionmainstreamed")


# ---------------------------------------------------------------------------
# Source loaders -> canonical-schema DataFrames
# ---------------------------------------------------------------------------

def _conform(df: pd.DataFrame) -> pd.DataFrame:
    """Project a transformed DataFrame onto the canonical 49-column schema."""
    df = df.copy()
    df["db"] = df["db"].replace(_DB_NORMALISE)
    df["id"] = df["id"].astype(str)
    df = df.reindex(columns=CANONICAL_COLUMNS)
    for col in _NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # reindex creates absent columns as all-NaN float64; pandas 3 then raises
    # when strings are later assigned into them (e.g. region enrichment).
    # Cast the non-numeric ones to object so they accept any value.
    for col in df.columns:
        if (col not in _NUMERIC_COLS
                and pd.api.types.is_float_dtype(df[col])
                and df[col].isna().all()):
            df[col] = df[col].astype("object")
    return df


def load_fapda_jsonl(path: Path, kind: str) -> pd.DataFrame:
    """Transform a FAPDA JSONL file (decisions or frameworks) to canonical schema."""
    transformer = transform_decision if kind == "decisions" else transform_framework
    records = _read_jsonl(path)
    print(f"Transforming {len(records):,} FAPDA {kind} from {path.name} …")
    return _conform(pd.DataFrame([transformer(r) for r in records]))


def _load_sources(args: argparse.Namespace) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Load every available source; return {db: df} plus {db: skip-reason}."""
    sources: dict[str, pd.DataFrame] = {}
    skipped: dict[str, str] = {}

    def _try(db: str, path: Path | None, loader) -> None:
        if path is None:
            skipped[db] = "no input path given"
            return
        if not path.exists():
            skipped[db] = f"input file not found: {path}"
            return
        try:
            sources[db] = loader(path)
        except Exception as exc:  # noqa: BLE001 — isolate per-source failures
            skipped[db] = f"load failed: {exc}"

    _try("FAPDA_decisions", args.fapda_decisions, lambda p: load_fapda_jsonl(p, "decisions"))
    _try("FAPDA_F", args.fapda_frameworks, lambda p: load_fapda_jsonl(p, "frameworks"))
    _try("PINE", args.pine_instruments, lambda p: _conform(load_pine(p)))
    _try("GIFNA", args.gifna_csv, lambda p: _conform(load_gifna(p)))
    return sources, skipped


# ---------------------------------------------------------------------------
# Enrichment from the existing dataset (region lookups for new FAPDA rows)
# ---------------------------------------------------------------------------

def _fill_regions_from_existing(df: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    """Fill missing FAPDA_region / FAPDA_subregion / who_region from per-ISO
    majorities in the existing dataset (new FAPDA JSONL rows have ISO but no
    region columns)."""
    for col in ("FAPDA_region", "FAPDA_subregion", "who_region"):
        lookup = (
            existing.dropna(subset=["iso", col])
            .drop_duplicates(subset=["iso"])
            .set_index("iso")[col]
        )
        missing = df[col].isna() & df["iso"].notna()
        if missing.any():
            if pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].astype("object")
            df.loc[missing, col] = df.loc[missing, "iso"].map(lookup)
    return df


# ---------------------------------------------------------------------------
# GIFNA freshness signal
# ---------------------------------------------------------------------------

def gifna_freshness(map_path: Path | None, dataset_gifna_rows: int) -> dict[str, Any]:
    """Compare GIFNA per-country map counts (automated fetch) with the number
    of GIFNA rows in the dataset. A growing map total means the manual CSV
    export should be refreshed."""
    info: dict[str, Any] = {
        "map_data_file": str(map_path) if map_path else None,
        "map_action_total": None,
        "dataset_gifna_rows": int(dataset_gifna_rows),
        "refresh_recommended": None,
        "note": None,
    }
    if not map_path or not map_path.exists():
        info["note"] = "map data file not found — run fetch_gifna_data.py"
        return info
    total = 0

    def _add(val: Any) -> None:
        nonlocal total
        num = pd.to_numeric(val, errors="coerce")
        if pd.notna(num):
            total += int(num)

    try:
        if map_path.suffix == ".jsonl":
            for rec in _read_jsonl(map_path):
                _add(rec.get("action_count"))
        else:  # raw mapData.json: {bucket: [[iso2, country..., count], ...]}
            payload = json.loads(map_path.read_text(encoding="utf-8"))
            for entries in payload.values():
                for entry in entries:
                    if isinstance(entry, list) and entry:
                        _add(entry[-1])
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        info["note"] = f"could not parse map data: {exc}"
        return info
    # Baseline ratio from the 2026-05-16 snapshot, where the same-day manual
    # export had 3,731 policies while the map reported 4,038 actions (a policy
    # can carry several actions, so the two counts are not 1:1).
    baseline_ratio = 4038 / 3731
    expected_actions = int(dataset_gifna_rows * baseline_ratio)
    info["map_action_total"] = total
    info["expected_actions_at_current_rows"] = expected_actions
    info["refresh_recommended"] = total > expected_actions
    info["note"] = (
        "GIFNA map action total has grown beyond what the current dataset rows "
        "imply — do a manual CSV export from https://gifna.who.int/search and "
        "re-run with --gifna_csv"
        if total > expected_actions
        else "GIFNA map action total is consistent with the dataset — manual export likely current"
    )
    return info


# ---------------------------------------------------------------------------
# Main update logic
# ---------------------------------------------------------------------------

def update(args: argparse.Namespace) -> dict[str, Any]:
    existing = pd.read_parquet(args.existing)
    missing_cols = [c for c in CANONICAL_COLUMNS if c not in existing.columns]
    if missing_cols:
        raise SystemExit(f"Existing dataset {args.existing} lacks canonical columns: {missing_cols}")
    existing["id"] = existing["id"].astype(str)
    existing_keys = set(zip(existing["db"], existing["id"]))
    print(f"Existing dataset: {len(existing):,} rows ({args.existing})")

    sources, skipped = _load_sources(args)

    per_source: dict[str, dict[str, Any]] = {}
    new_parts: list[pd.DataFrame] = []
    for db, df in sources.items():
        fetched = len(df)
        df = df.drop_duplicates(subset=["db", "id"], keep="first")
        within_batch_dupes = fetched - len(df)
        is_new = ~df.set_index(["db", "id"]).index.isin(existing_keys)
        new_df = df[is_new].copy()
        per_source[db] = {
            "fetched": fetched,
            "within_batch_duplicates": within_batch_dupes,
            "already_in_dataset": int((~is_new).sum()),
            "new": int(is_new.sum()),
        }
        if len(new_df):
            new_parts.append(new_df)
    for db, reason in skipped.items():
        per_source[db] = {"skipped": reason}

    if new_parts:
        new_rows = pd.concat(new_parts, ignore_index=True)
        new_rows = _fill_regions_from_existing(new_rows, existing)
    else:
        new_rows = pd.DataFrame(columns=CANONICAL_COLUMNS)

    # Outputs
    run_tag = date.today().strftime("%Y%m%d")
    updates_dir = Path(args.updates_dir)
    new_rows_file: str | None = None
    new_rows_csv: str | None = None
    if len(new_rows):
        updates_dir.mkdir(parents=True, exist_ok=True)
        new_rows_path = updates_dir / f"new_rows_{run_tag}.parquet"
        new_rows.to_parquet(new_rows_path, index=False)
        new_rows_file = str(new_rows_path)
        new_rows_csv_path = updates_dir / f"new_rows_{run_tag}.csv"
        new_rows.to_csv(new_rows_csv_path, index=False)
        new_rows_csv = str(new_rows_csv_path)
        print(f"Wrote {len(new_rows):,} new rows -> {new_rows_path}")
        print(f"Wrote {len(new_rows):,} new rows -> {new_rows_csv_path}")
    else:
        print("No new rows — skipping new_rows parquet/csv.")

    combined = pd.concat([existing, new_rows], ignore_index=True) if len(new_rows) else existing
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output, index=False)
    print(f"Wrote combined dataset: {len(combined):,} rows -> {output}")

    summary: dict[str, Any] = {
        "run_date": date.today().isoformat(),
        "existing_dataset": str(args.existing),
        "existing_rows": len(existing),
        "sources": per_source,
        "new_rows_total": int(len(new_rows)),
        "new_rows_file": new_rows_file,
        "new_rows_csv": new_rows_csv,
        "output": str(output),
        "output_rows": len(combined),
        "gifna_freshness": gifna_freshness(
            args.gifna_map, int((combined["db"] == "GIFNA").sum())
        ),
    }

    summary_path = Path(args.summary) if args.summary else updates_dir / f"summary_{run_tag}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== Update summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSummary saved -> {summary_path}")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incremental OpenFPD update: transform fetcher outputs, dedupe, emit new rows."
    )
    parser.add_argument("--fapda_decisions", type=Path,
                        default=REPO / "data/fapda/fapda_policy_decisions.jsonl")
    parser.add_argument("--fapda_frameworks", type=Path,
                        default=REPO / "data/fapda/fapda_policy_frameworks.jsonl")
    parser.add_argument("--pine_instruments", type=Path,
                        default=REPO / "data/pine/pine_instruments.csv")
    parser.add_argument("--gifna_csv", type=Path, default=None,
                        help="Optional manual GIFNA search export CSV (record level is not automatable).")
    parser.add_argument("--gifna_map", type=Path,
                        default=REPO / "data/gifna/gifna_map_data_records.jsonl",
                        help="GIFNA map-data records (or raw mapData.json) for the freshness signal.")
    parser.add_argument("--existing", type=Path, default=REPO / "data/FSPD_new.parquet",
                        help="Existing canonical dataset to dedupe against.")
    parser.add_argument("--output", type=Path, default=REPO / "data/FSPD_new.parquet",
                        help="Where to write the updated combined dataset.")
    parser.add_argument("--updates_dir", type=Path, default=REPO / "data/updates",
                        help="Directory for new_rows_<YYYYMMDD>.parquet and default summary location.")
    parser.add_argument("--summary", type=Path, default=None,
                        help="Path for the JSON summary (default: <updates_dir>/summary_<YYYYMMDD>.json).")
    return parser.parse_args(argv)


if __name__ == "__main__":
    update(parse_args())
