"""
Merge classifier predictions back into the canonical dataset.

Takes the combined dataset written by update_dataset.py and the classified
new-rows file written by classify_new.py (canonical columns + pred_<task>,
<task>_confidence, needs_review), matches rows on the (db, id) key, and fills
the classification columns in the combined dataset:

  segment, lever, type            (multiclass labels)
  inclusion, envitarget, diethealth   (binary 0/1)
  <task>_confidence (six columns), needs_review, classified_date

The canonical 49-column schema (build_dataset.CANONICAL_COLUMNS) carries no
classification columns; this script adds them on first run and maintains them
afterwards. Rows without predictions keep null values. Existing predictions
are only overwritten for rows present in the predictions file.

Pure pandas — no ML imports; safe to run anywhere.

Usage (as in the monthly GitHub Actions workflow):
    python -m src.pipeline.merge_predictions \
        --combined data/FSPD_new.parquet \
        --predictions data/updates/new_rows_<YYYYMMDD>_classified.parquet \
        --output data/FSPD_new.parquet
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

MULTICLASS_TASKS = ["segment", "lever", "type"]
BINARY_TASKS = ["inclusion", "envitarget", "diethealth"]
TASKS = MULTICLASS_TASKS + BINARY_TASKS
KEY = ["db", "id"]


def _ensure_columns(combined: pd.DataFrame) -> pd.DataFrame:
    """Add the classification columns if absent (typed so parquet roundtrips)."""
    for task in MULTICLASS_TASKS:
        if task not in combined.columns:
            combined[task] = pd.Series(pd.NA, index=combined.index, dtype="string")
    for task in BINARY_TASKS:
        if task not in combined.columns:
            combined[task] = pd.Series(np.nan, index=combined.index, dtype="float64")
    for task in TASKS:
        col = f"{task}_confidence"
        if col not in combined.columns:
            combined[col] = pd.Series(np.nan, index=combined.index, dtype="float64")
    if "needs_review" not in combined.columns:
        combined["needs_review"] = pd.Series(pd.NA, index=combined.index, dtype="boolean")
    if "classified_date" not in combined.columns:
        combined["classified_date"] = pd.Series(pd.NA, index=combined.index, dtype="string")
    return combined


def merge(combined_path: Path, predictions_path: Path, output_path: Path) -> dict:
    combined = pd.read_parquet(combined_path)
    preds = pd.read_parquet(predictions_path)
    combined["id"] = combined["id"].astype(str)
    preds["id"] = preds["id"].astype(str)

    missing = [f"pred_{t}" for t in TASKS if f"pred_{t}" not in preds.columns]
    if missing:
        raise SystemExit(f"Predictions file lacks columns: {missing}")

    combined = _ensure_columns(combined)

    preds = preds.drop_duplicates(subset=KEY, keep="first").set_index(KEY)
    combined_keys = pd.MultiIndex.from_frame(combined[KEY])
    mask = combined_keys.isin(preds.index)
    n_matched = int(mask.sum())
    if n_matched < len(preds):
        print(f"WARNING: {len(preds) - n_matched} predicted rows not found in combined dataset")

    aligned = preds.reindex(combined_keys[mask])
    for task in MULTICLASS_TASKS:
        combined.loc[mask, task] = aligned[f"pred_{task}"].astype("string").to_numpy()
    for task in BINARY_TASKS:
        combined.loc[mask, task] = aligned[f"pred_{task}"].astype("float64").to_numpy()
    for task in TASKS:
        col = f"{task}_confidence"
        combined.loc[mask, col] = aligned[col].astype("float64").to_numpy()
    combined.loc[mask, "needs_review"] = aligned["needs_review"].astype("boolean").to_numpy()
    combined.loc[mask, "classified_date"] = date.today().isoformat()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output_path, index=False)

    n_review = int(combined.loc[mask, "needs_review"].fillna(False).sum())
    print(f"Merged predictions for {n_matched:,} rows into {output_path}")
    print(f"  needs_review among merged rows: {n_review} "
          f"({100 * n_review / max(n_matched, 1):.1f}%)")
    return {"matched": n_matched, "predictions": len(preds), "needs_review": n_review}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill classification columns in the combined dataset from classify_new.py output."
    )
    parser.add_argument("--combined", type=Path, required=True,
                        help="Combined dataset parquet (output of update_dataset.py).")
    parser.add_argument("--predictions", type=Path, required=True,
                        help="Classified new-rows parquet (output of classify_new.py).")
    parser.add_argument("--output", type=Path, required=True,
                        help="Where to write the merged parquet (may equal --combined).")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    merge(args.combined, args.predictions, args.output)
