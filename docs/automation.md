# Weekly update automation

GitHub Actions workflow that keeps `data/FSPD_new.parquet` current: fetch new
source data, dedupe, classify with the two-stage model, open a PR.

Workflow file: `.github/workflows/weekly-update.yml`

## Overview

```
schedule (Wed 21:45 UTC = 22:45 UK in summer)  or  workflow_dispatch (dry_run)
  |
  v
Job 1: fetch (ubuntu-latest, requirements-fetch.txt)
  |- fetch_all_data.py --source fapda   (fails the run if it fails)
  |- fetch_all_data.py --source pine    (continue-on-error; OECD Shiny scrape)
  |- fetch_all_data.py --source gifna   (continue-on-error; freshness signal only)
  '- upload artifact "fetched-data":
       fapda_policy_{decisions,frameworks}.jsonl, pine_instruments.csv,
       gifna_map_data_records.jsonl, ETL metadata
  |
  v
Job 2: update-and-classify (needs fetch)
  |- download artifact into data/
  |- src/pipeline/update_dataset.py
  |    + newest data/gifna/manual/*.csv if committed (--gifna_csv)
  |    dedupe on (db,id) vs checked-in data/FSPD_new.parquet
  |    -> data/updates/new_rows_<YYYYMMDD>.parquet (only if non-empty)
  |    -> updated data/FSPD_new.parquet
  |    -> data/updates/summary_<YYYYMMDD>.json
  |- if 0 new rows: write report to job summary, stop (no PR)
  |- else:
  |    pip install CPU torch + ML deps
  |    download models from HF (ncerutti/openfpd-classifier, cached by
  |      actions/cache, key MODEL_REVISION)
  |    classify_new.py -> new_rows_<YYYYMMDD>_classified.parquet
  |    src/pipeline/merge_predictions.py -> fills classification columns
  |      (segment, lever, type, inclusion, envitarget, diethealth,
  |       *_confidence, needs_review, classified_date) in FSPD_new.parquet
  |- src/pipeline/make_pr_body.py -> pr_body.md + job summary
  '- peter-evans/create-pull-request: branch auto-update/<YYYY-MM-DD>
       contents: data/FSPD_new.parquet + data/updates/*
```

## Schedule and triggers

- Scheduled: every Wednesday at 21:45 UTC. GitHub cron is UTC-only, so this
  is 22:45 UK time during BST (summer) and 21:45 UK during GMT (winter).
- Manual: Actions tab > "Weekly data update" > Run workflow. Optional
  `dry_run` checkbox: limits FAPDA to 200 records, writes the report to the
  job summary, and never opens a PR. Use it to test the fetch/dedupe path
  without waiting a week (a dry run usually finds 0 new rows, so the
  classification steps are also skipped — the classification path itself was
  verified on Kaggle, see `docs/models.md`).

## Secrets and permissions

- `HF_TOKEN` (repository secret): Hugging Face token with read access to the
  private model repo `ncerutti/openfpd-classifier`. Set with
  `gh secret set HF_TOKEN --repo ncerutti/FSPD` (never echo the value).
- The workflow itself uses `permissions: contents: write, pull-requests:
  write` with the default `GITHUB_TOKEN`. Repository setting "Allow GitHub
  Actions to create and approve pull requests" must be enabled
  (Settings > Actions > General > Workflow permissions).

## Model cache

The 1.1 GB Stage 1 checkpoint (plus Stage 2 joblibs) is cached with
`actions/cache` under the key `openfpd-classifier-${MODEL_REVISION}`.
`MODEL_REVISION` is a manual env var at the top of the workflow — bump it
whenever the artifacts in the HF repo change, so the next run re-downloads.

## When the PR arrives

1. Check the PR body: per-source fetched/new/duplicate counts, rows
   classified, share flagged `needs_review`, GIFNA freshness verdict.
2. Spot-check flagged rows: `data/updates/new_rows_<date>_classified.parquet`
   contains every new row with `pred_<task>`, `<task>_confidence`, and
   `needs_review` (any confidence < 0.7 or near-empty text). Review/correct
   before or after merging as you prefer; the canonical parquet stores the
   same predictions.
3. If the body says **GIFNA manual refresh recommended**: export the CSV from
   https://gifna.who.int/search (procedure in `docs/pipeline.md`), save it as
   `data/gifna/manual/<name>.csv`, commit and push it to main. The next
   weekly run automatically ingests the newest CSV in that directory via
   `--gifna_csv`; dedupe on (db, id) makes re-ingesting the same file a
   no-op, so the file can stay committed indefinitely.
4. Merge. The updated `data/FSPD_new.parquet` becomes the baseline for the
   next run.

## Failure playbook

- **PINE fetch FAILED in the PR body**: the OECD Shiny app was probably
  redeployed and the wire protocol / handler names changed
  (`src/pipeline/pine_etl.py`, see fragility note in `docs/fetching.md`).
  FAPDA rows are still processed; PINE shows as `skipped` in the source
  table. Fix the fetcher; missed PINE rows are picked up by the next run
  (dedupe is idempotent).
- **FAPDA fetch fails**: the whole run fails by design (FAPDA is ~90% of the
  data). Check the FAPDA API (`https://fapda.apps.fao.org/fapda/`) and
  `fetch_fapda_data.py`; re-run manually when fixed.
- **HF model download fails**: check that the `HF_TOKEN` secret is set and
  still valid, and that the token can read `ncerutti/openfpd-classifier`.
  A stale cache can be bypassed by bumping `MODEL_REVISION`.
- **Zero new rows**: not a failure. The run stops gracefully after the update
  step; the job summary still shows the per-source counts and the GIFNA
  freshness signal. No PR is opened.
- **PR has conflicts** (e.g. the parquet changed on main since the run):
  re-run the workflow manually; it rebuilds from the current main.

## Notes / future work

- `data/FSPD_new.parquet` (~29 MB) is committed to git and rewritten on every
  run that finds new rows; the binary churn in history is accepted for now. A
  cleaner future setup is hosting the dataset in a HF dataset repo (or Git
  LFS) and keeping only the weekly `data/updates/` deltas in git.
- GIFNA record-level ingestion stays manual (Blazor websocket circuit, see
  `docs/fetching.md`); the workflow only automates the staleness check.
