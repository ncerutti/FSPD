# OpenFPD automation — summary of changes, 10 June 2026

## What the system does now

OpenFPD (Open Food Policy Database) is now a self-updating database. Every
Wednesday night a GitHub Actions workflow:

1. **Fetches** new policy records from FAPDA (FAO API) and PINE (OECD), plus a
   GIFNA staleness signal.
2. **Harmonizes** them into the canonical 49-column schema and **dedupes**
   against the existing `data/FSPD_new.parquet` (46,155 policies), keeping
   only genuinely new rows.
3. **Classifies** the new rows with the two-stage ML model (XLM-RoBERTa
   embeddings + XGBoost) on a CPU runner, downloading the models from a
   private Hugging Face repo. Predictions below 0.7 confidence are flagged
   `needs_review`.
4. **Opens a pull request** with the updated dataset and a report: per-source
   fetched/new/duplicate counts, classification confidence stats, flagged
   rows, and whether the manual GIFNA export needs refreshing.

Nothing runs on the development laptop. Training stays on Kaggle, models live
on Hugging Face, inference runs in CI.

## State before today

- Stage 1 (XLM-RoBERTa multi-task) and Stage 2 (XGBoost hybrid) were trained,
  but the Stage 2 model files existed only as expired Kaggle kernel output —
  not on disk anywhere.
- The only full checkpoint was `best_model.pt` (3.3 GB incl. optimizer state),
  too big to deploy and unloadable on the laptop.
- Fetchers existed but were unusable for automation: the PINE fetcher pulled
  the wrong OECD dataset entirely (SDMX aggregates, not policy instruments),
  the GIFNA fetcher only retrieved map metadata, and the canonical dataset had
  been built from manually downloaded exports via a separate code path
  (`build_dataset.py`) that the fetchers did not feed.
- There was no dedupe, no incremental update, no inference script, and no CI.

## What changed today

### 1. Fetch layer (`fetch_all_data.py`, `src/pipeline/*_etl.py`)

- **PINE rewritten** (`pine_etl.py`): record-level access by driving the OECD
  Shiny app's SockJS wire protocol directly with `requests`. Verified: the
  fetched instrument table matches the manual `OECD-PINEVersion2026.csv`
  export exactly (4,685/4,685 InstrumentIds). Fails loudly (schema/row-count
  validation) rather than fetching garbage if OECD redeploys the app.
- **FAPDA verified** end-to-end against the live API (it was already correct).
- **GIFNA documented as manual-only** (Blazor websocket app, no public JSON
  backend; confirmed by investigation). The fetcher now provides a freshness
  signal (per-country action counts) so the weekly PR says when a new manual
  export is worth doing. Also fixed a parsing bug for country names containing
  commas.
- **Orchestrator CI-ready**: `--source fapda|gifna|pine|all`, per-source error
  isolation, summary lines, non-zero exit on failure.
- Docs: `docs/fetching.md`.

### 2. Incremental update pipeline (`src/pipeline/update_dataset.py`, new)

- Single entrypoint: fetcher outputs -> canonical schema (reusing
  `transform.py` for FAPDA JSONL and `build_dataset.py` loaders for PINE/GIFNA
  CSVs) -> dedupe on (db, id) -> `data/updates/new_rows_<date>.parquet`,
  updated combined parquet, JSON summary.
- Verified against the May 16 baseline: 27,897 FAPDA decisions fetched, 27,892
  recognized as duplicates, 5 genuinely new (regional aggregates absent from
  the old manual export); 0 false "new" rows for frameworks, PINE, GIFNA.
- Fixed a latent `transform.py` bug (FAPDA API placeholder string corrupting
  commodity columns) and exported the canonical schema as `CANONICAL_COLUMNS`.
- Docs: `docs/pipeline.md`.

### 3. Models recovered, slimmed, hosted, verified

- **Stage 2 models recovered** by re-running `stage2.py` on a Kaggle T4
  (kernel `ncerutti/fspd-stage2-rerun`); metrics reproduce the published
  results exactly (Segment F1 0.8648, Lever 0.6619, Type 0.9038, Inclusion
  0.7140, EnviTarget 0.8239, DietHealth 0.7376). Now in
  `outputs/models/stage2_models/` and on HF.
- **Checkpoint slimmed** 3.3 GB -> 1.1 GB (`best_model_slim.pt`: weights +
  label encoders + config, no optimizer state).
- **Hosted** in private HF repo `ncerutti/openfpd-classifier`:
  `best_model_slim.pt`, `stage2_models/*.joblib`, `cat_encoder.joblib` (the
  Stage 2 categorical encoder, refit on the exact seed-42 training split).
- **Verified remotely** (Kaggle CPU kernel `ncerutti/openfpd-verify`):
  download from HF -> load -> classify 3 synthetic + 5 held-out test policies.
  4/5 segment matches (consistent with test F1 0.865), exact lever/type
  predictions on French and Spanish policies.
- **`classify_new.py`** (new, repo root): CPU two-stage inference for CI/
  Kaggle only — batched CLS embeddings, ordinal-encoded categoricals, XGBoost
  predictions with margin-derived confidences, `needs_review` flag.
- Docs: `docs/models.md`.

### 4. GitHub Actions automation (`.github/workflows/weekly-update.yml`, new)

- Schedule: **every Wednesday 21:45 UTC** (= 22:45 UK in summer/BST, 21:45 UK
  in winter/GMT — GitHub cron is UTC-only), plus manual trigger with a
  `dry_run` option (FAPDA limited to 200 records, no PR).
- Job 1 (fetch): FAPDA hard-fails the run; PINE/GIFNA are continue-on-error
  and their status is surfaced in the PR body.
- Job 2 (update + classify): dedupe; graceful stop at 0 new rows; otherwise
  CPU-only torch install, HF model download (1.1 GB cached via `actions/cache`
  keyed on `MODEL_REVISION` — bump it when HF artifacts change), inference,
  merge of predictions into the parquet (`src/pipeline/merge_predictions.py`,
  new — also adds the confidence/needs_review/classified_date columns), PR via
  `peter-evans/create-pull-request` on branch `auto-update/<YYYY-MM-DD>` with
  a report body (`src/pipeline/make_pr_body.py`, new).
- Manual GIFNA exports committed under `data/gifna/manual/` are picked up
  automatically (newest CSV passed as `--gifna_csv`).
- `HF_TOKEN` repository secret is set. `.gitignore` reworked so the canonical
  parquet, update outputs, and manual GIFNA exports are tracked while the rest
  of `data/` and all local model files stay ignored.
- Docs: `docs/automation.md` (incl. failure playbook).

## Remaining manual steps / operational notes

- Repo setting "Allow GitHub Actions to create and approve pull requests"
  must be enabled once (Settings > Actions > General).
- Recommended: one manual `dry_run` from the Actions tab to validate CI.
- GIFNA refresh, when the PR recommends it: export CSV from
  https://gifna.who.int/search, save under `data/gifna/manual/`, commit, push.
- When models on HF change: bump `MODEL_REVISION` in the workflow.
- Future work: REST API and public web interface; consider moving the dataset
  to a HF dataset repo to avoid parquet churn in git history.
