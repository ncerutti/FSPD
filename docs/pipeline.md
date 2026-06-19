# Incremental update pipeline

Turns fetcher outputs into "new rows to classify" and an updated canonical
dataset. Designed for a weekly GitHub Actions run. Pure pandas — no ML
dependencies; run with the ETL venv (`.venv-fetch`).

## Data flow

```
fetch_all_data.py (weekly, automated)
  ├─ FAPDA  → data/fapda/fapda_policy_decisions.xlsx
  │           data/fapda/fapda_policy_frameworks.xlsx
  ├─ PINE   → data/pine/pine_instruments.csv
  └─ GIFNA  → data/gifna/gifna_map_data_records.jsonl   (freshness signal only)

manual, when freshness signal fires
  └─ GIFNA  → data/gifna/original/GIFNA-SearchPage-...-<YYYY-MM-DD>.csv

src/pipeline/update_dataset.py
  ├─ transform each source to the canonical 49-col schema
  │    FAPDA xlsx   → build_dataset.load_fapda_decisions_xlsx / _frameworks_xlsx
  │    PINE CSV     → build_dataset.load_pine  (food-domain filter)
  │    GIFNA CSV    → build_dataset.load_gifna
  ├─ dedupe on (db, id) against --existing (data/FSPD_new.parquet)
  │    and within the fetched batch
  ├─ enrich new rows (FAPDA_region / who_region from existing rows by ISO)
  └─ outputs
       data/updates/new_rows_<YYYYMMDD>.parquet   → classifier input
       data/updates/new_rows_<YYYYMMDD>.csv       → same rows, human-readable
       --output (default data/FSPD_new.parquet)   → updated combined dataset
       data/updates/summary_<YYYYMMDD>.json       → counts for the PR body
```

The canonical schema is `CANONICAL_COLUMNS` in `src/pipeline/build_dataset.py`
(49 columns; no classification/model columns — the classifier adds those
downstream from the new-rows file).

## How to run

```bash
# normal weekly run (after fetch_all_data.py; updates data/FSPD_new.parquet)
.venv-fetch/bin/python3 -m src.pipeline.update_dataset

# with a fresh GIFNA manual export
.venv-fetch/bin/python3 -m src.pipeline.update_dataset \
    --gifna_csv data/gifna/original/GIFNA-SearchPage-policies-data-items-2026-05-16.csv

# dry run / test (never overwrite the canonical parquet in tests)
.venv-fetch/bin/python3 -m src.pipeline.update_dataset \
    --output /tmp/FSPD_updated.parquet \
    --updates_dir /tmp/updates \
    --summary /tmp/summary.json
```

Flags: `--fapda_decisions`, `--fapda_frameworks`, `--pine_instruments`,
`--gifna_csv` (optional), `--gifna_map`, `--existing`, `--output`,
`--updates_dir`, `--summary`. Defaults point at the standard fetcher output
locations. A missing or unreadable source file is skipped and reported in the
summary (`"skipped": reason`) — one failed fetcher does not block the rest.

## Dedupe key per source

| db               | id                          | source of the id                               |
|------------------|-----------------------------|------------------------------------------------|
| FAPDA_decisions  | FAPDA decision id (numeric) | xlsx `ID` column; equals `policydecisionid=` in old URLs  |
| FAPDA_F          | FAPDA framework id (numeric)| xlsx `ID` column; equals `policyframeworkid=` in old URLs |
| GIFNA            | `Policy_Id`                 | manual search-export CSV                        |
| PINE             | `InstrumentId`              | `pine_instruments.csv` / manual export          |

The key is the pair `(db, id)` as strings. The new Cloud Run xlsx export's
`ID` column equals the existing FAPDA ids in the canonical dataset (verified
2026-06-19: of 28,342 exported decisions, 27,828 already present and 514 new;
frameworks 13,893 present, 2 new), so dedupe is stable across the API
migration.

## GIFNA manual refresh procedure

GIFNA record data cannot be fetched headlessly (Blazor websocket circuit, see
`docs/fetching.md`). The automated fetch does retrieve per-country action
counts (`gifna_map_data_records.jsonl`), which the summary uses as a freshness
signal:

- `gifna_freshness.map_action_total` — actions reported by the GIFNA map now;
- `gifna_freshness.dataset_gifna_rows` — GIFNA policies in the dataset;
- `refresh_recommended` — true when the map total exceeds what the current
  row count implies (actions and policies are not 1:1; the 2026-05-16
  snapshot baseline is 4,038 actions for 3,731 policies).

When `refresh_recommended` is true:

1. Open https://gifna.who.int/search, leave all filters empty.
2. Use the CSV export button; save as
   `data/gifna/original/GIFNA-SearchPage-policies-data-items-<YYYY-MM-DD>.csv`.
3. Re-run the update with `--gifna_csv <that file>`.

## Notes / caveats

- `data/FSPD.csv` is the labelled training set only — it is never read by
  this pipeline and must not be used to populate the database.
- The combined output simply appends new rows; existing rows are never
  modified, so upstream edits/deletions in source databases are not picked up
  (a full rebuild via `build_dataset.py` from fresh exports handles that).
- The 2026-05-16 baseline test produced 5 new rows (all FAPDA decisions —
  regional aggregate records like "Caribbean" that the manual xls export
  omits, with no ISO code) and 0 new rows for FAPDA_F/PINE/GIFNA.
- For frameworks, `policycategorycode` from the JSONL path contains FAPDA
  classification ids rather than the numeric category codes of the xlsx
  export; `policycategory` (labels) is consistent across both paths.
