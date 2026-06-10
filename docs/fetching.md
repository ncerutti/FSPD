# Data fetching

How OpenFPD pulls source data, what is automated, and what remains manual.

All fetchers run with the ETL venv:

```bash
.venv-fetch/bin/python3 fetch_all_data.py                 # everything
.venv-fetch/bin/python3 fetch_all_data.py --source fapda  # one source
.venv-fetch/bin/python3 fetch_all_data.py --source fapda --fapda_limit 50  # smoke run
```

`fetch_all_data.py` runs each source independently, prints a per-source
summary (records fetched, output paths), and exits non-zero if any selected
source failed — suitable for a scheduled GitHub Actions job.

## FAPDA (FAO) — automation: FULL

- Endpoint: `https://fapda.apps.fao.org/fapda/` (DataTables-style JSON API,
  paginated; policy decisions and policy frameworks resources).
- Fetcher: `fetch_fapda_data.py` / `src/pipeline/fapda_etl.py`.
- Output: `data/fapda/fapda_policy_decisions.jsonl`,
  `data/fapda/fapda_policy_frameworks.jsonl` (+ CSV exports,
  `fapda_etl_metadata.json`).
- Volume: ~28,400 decisions + ~13,900 frameworks; the full pull is large
  (~800 MB) — use `--limit` for tests.
- Robustness: the server intermittently truncates large responses and
  occasionally cannot serialize a specific record at all (HTTP 200 with a
  truncated body containing an embedded 500 stack trace — e.g. framework id
  20626, June 2026). The fetcher retries with backoff, recursively halves
  failing windows, and as a last resort fetches records one at a time,
  skipping only the poisoned ones. Skipped offsets are listed with a WARNING
  in the log and under `skipped_offsets` in `fapda_etl_metadata.json`; they
  are retried from scratch on the next run.
- Run alone:
  `.venv-fetch/bin/python3 fetch_fapda_data.py --resource both --limit 50 --output_dir /tmp/fapda_smoke`

## PINE (OECD) — automation: FULL (record level)

- Source: https://pinedatabase.oecd.org/ (redirects to
  `oecd-main.shinyapps.io/pinedatabase`). PINE has **no SDMX dataflow** and
  no static bulk file; the earlier SDMX fetch (CAPMF/ERTR flows) was a
  different dataset and has been removed.
- The site is an R Shiny app. `src/pipeline/pine_etl.py` speaks the
  Shiny/SockJS protocol over plain HTTP (xhr-polling, `requests` only):
  it opens a session, sends the Shiny `init` message, reads the
  server-registered download hrefs, and downloads the CSVs.
- Working download handlers (headless): `downloadcsv4` (Data > Subscheme
  data — instrument-level columns + `SubSchemeId`) and `downloadcsv3`
  (Data > Environmentally related tax revenue, optional `--include_ertr`).
  `downloadcsv1` (Data > Instrument data — the one matching the manual
  export `data/pine/original/OECD-PINEVersion2026.csv`) errors server-side
  without a real browser, so the instrument-level table is derived from the
  subscheme table by deduplicating on `InstrumentId`.
- Output: `data/pine/pine_instruments.csv` (instrument level, same schema
  as the manual export minus trailing export-metadata columns),
  `data/pine/pine_subschemes.csv`, raw TSV, `pine_etl_metadata.json`.
- Run alone: `.venv-fetch/bin/python3 fetch_pine_data.py --output_dir data/pine`
- Fragility note: this depends on the Shiny wire protocol and the app's
  internal handler names (`downloadcsv4`); if OECD redeploys the app the
  fetcher may need updating. It validates required columns and a minimum
  row count (`--min_rows`, default 1000) and fails loudly otherwise.

## GIFNA (WHO) — automation: PARTIAL (record level is manual)

- Site: https://gifna.who.int — a **Blazor Server** application. All search
  results and the CSV export travel over a SignalR websocket circuit
  (binary MessagePack render batches); there is no JSON/AJAX backend for
  the policy records, no static JSON with records, and every probed API
  path returns the SPA shell. The CSV export is generated server-side and
  pushed through the circuit as a base64 blob (`SaveAsFile.js`).
  Replicating a Blazor circuit with `requests` is not practical, so
  record-level GIFNA stays manual.
- Automated (fetcher `fetch_gifna_data.py` / `src/pipeline/gifna_etl.py`):
  - `https://gifna.who.int/json/mapData.json` — per-country action counts
    (useful as a freshness signal: if counts change, re-export manually).
  - `https://gifna.who.int/json/disputed.json` — map geometry metadata.
  - WHO ArcGIS boundaries (used by `transform.py` for the WHO-region
    lookup).
- Manual fallback (record level): open https://gifna.who.int/search, leave
  filters empty, use the CSV export button, and save the file as
  `data/gifna/original/GIFNA-SearchPage-policies-data-items-<YYYY-MM-DD>.csv`.
  The downstream pipeline (`src/pipeline/build_dataset.py --gifna ...`)
  reads that file.
- Run alone:
  `.venv-fetch/bin/python3 fetch_gifna_data.py --skip_boundaries --output_dir /tmp/gifna_smoke`

## Downstream

- `src/pipeline/update_dataset.py` — incremental update: fetcher outputs →
  dedupe against `data/FSPD_new.parquet` → new rows to classify
  (see `docs/pipeline.md`).
- `src/pipeline/transform.py` — FAPDA JSONL to canonical schema.
- `src/pipeline/build_dataset.py` — full rebuild of `data/FSPD_new.parquet`
  from FAPDA + GIFNA + PINE exports; defines the canonical schema
  (`CANONICAL_COLUMNS`).
