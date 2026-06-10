[![Weekly data update](https://github.com/ncerutti/FSPD/actions/workflows/weekly-update.yml/badge.svg?branch=main)](https://github.com/ncerutti/FSPD/actions/workflows/weekly-update.yml)

# OpenFPD — Open Food Policy Database

Automated ML pipeline that harmonizes food policy data from multiple sources and classifies it via transformer-based multi-task learning.

## Project Overview

The Open Food Policy Database (OpenFPD) aggregates 46,155 policies and frameworks from FAPDA, GIFNA, and PINE covering 195+ countries. This project transforms those static snapshots into a living database that automatically:

1. Ingests new policies from source databases (FAPDA, PINE, GIfNA)
2. Classifies them using transformer-based ML models
3. Updates the database with confidence scores
4. Makes data available through a web interface and API

## Status

| Component | Status |
|---|---|
| Stage 1: XLM-RoBERTa multi-task | Complete |
| Stage 2: XGBoost hybrid | Complete |
| Conference abstract (CS2Italy2026) | Complete |
| ETL harmonization (FSPD_new.parquet) | Complete |
| Policy submission web app | Complete |
| Weekly update automation (GitHub Actions) | Complete |
| Production pipeline & API | In progress (API pending) |

## Model Performance

Two-stage hybrid: XLM-RoBERTa embeddings + XGBoost classifiers.

| Task | Stage 1 F1 | Stage 2 F1 | Δ |
|---|---|---|---|
| Segment | 83.9 | 86.5 | +2.6 |
| Lever | 63.7 | 66.2 | +2.5 |
| Type | 87.0 | 90.4 | +3.4 |
| Inclusion | 65.4 | 71.4 | +6.0 |
| EnviTarget | 82.8 | 82.4 | −0.4 |
| DietHealth | 70.9 | 73.8 | +2.8 |

Feature importance: ~99% from transformer embeddings across all tasks.

## Automation

A scheduled GitHub Actions workflow (`.github/workflows/weekly-update.yml`)
runs every Wednesday night (22:45 UK): it fetches new FAPDA/PINE data (plus a GIFNA freshness signal),
dedupes against `data/FSPD_new.parquet`, classifies new rows with the
two-stage model (CPU, models pulled from a private Hugging Face repo), and
opens a pull request with the updated dataset and a run report. See
`docs/automation.md` for the schedule, dry-run mode, review checklist, and
failure playbook.

## Data Sources

- **FAPDA** (Food and Agriculture Policy Decision Analysis): Agricultural policies
- **PINE** (Policy Instruments for the Environment): Environmental policies
- **GIfNA** (Global Database on Implementation of Nutrition Action): Nutrition policies

## Classification Tasks

The ML models predict:
- **Segment** (10 categories): Inputs, Farming, Trade, Processing, Retail, Food service, Final consumption, etc.
- **Lever** (~135 types): Specific policy instruments (subsidies, taxes, regulations, etc.)
- **Type of lever** (8 categories): Producer subsidy, Trade policy, Regulations, Consumer subsidy, etc.
- **Objectives** (3 binary flags): Environmental sustainability, Inclusion, Dietary health

## Architecture

- **Stage 1**: XLM-RoBERTa-base (278M params), multi-task fine-tuned on 6 heads, inverse-frequency class weighting
- **Stage 2**: 768-dim CLS embeddings + categorical metadata → XGBoost (one classifier per task)
- **Confidence control**: predictions below 0.7 flagged for expert review

## Key Files

```
src/models/
├── model.py        # FSPDMultiTaskModel
├── train.py        # Stage 1 training
├── stage2.py       # Stage 2 (XGBoost hybrid)
└── config.py       # ModelConfig, DataConfig

outputs/models/
├── best_model.pt           # Stage 1 trained model
├── test_metrics.json       # Stage 1 metrics
├── stage2_metrics.json     # Stage 1 vs Stage 2 comparison
└── stage2_models/          # Saved XGBoost classifiers
```

## Project Structure

```
FSPD/
├── data/                      # Raw and processed data
├── fetch_all_data.py          # Run all ETL fetchers into data/
├── fetch_fapda_data.py        # ETL entrypoint for FAPDA ingestion
├── fetch_gifna_data.py        # ETL entrypoint for GIFNA public assets
├── fetch_pine_data.py         # ETL entrypoint for PINE (record-level, OECD Shiny app)
├── src/
│   ├── models/               # ML model definitions and training
│   ├── pipeline/             # Data ingestion and transformation
│   ├── api/                  # REST API implementation
│   └── utils/                # Utility functions
├── notebooks/                # Jupyter notebooks for analysis
├── outputs/
│   ├── models/              # Trained model checkpoints
│   └── plots/               # Visualizations
├── config/                   # Configuration files
└── docs/                     # Documentation
```

## Data

46,155 policies and frameworks from FAPDA (decisions + frameworks), GIFNA, and PINE, harmonized into `data/FSPD_new.parquet`. The original `data/FSPD.csv` (15,592 rows) is retained as the labelled training set for the ML models.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Quick Start

### Train Model
```bash
python train_model.py
```

### Make Predictions
```bash
python predict_policies.py \
  --model_path outputs/models/best_model.pt \
  --input data/new_policies.csv \
  --output predictions.csv
```

### Fetch All Sources (ETL)
```bash
python fetch_all_data.py
```

### Fetch FAPDA Data
```bash
python fetch_fapda_data.py --resource both --output_dir data/raw/fapda
```

### Fetch GIFNA Data
```bash
python fetch_gifna_data.py --output_dir data/raw/gifna
```

### Fetch PINE Data
```bash
python fetch_pine_data.py --output_dir data/raw/pine
```

### Run Analysis
```bash
jupyter notebook notebooks/01_exploratory_analysis.ipynb
```

## Reference

Lowder, S.K., Ruggeri Laderchi, C., Cerutti, N., Parsons, K. (2025). Food System Policies: a Global Snapshot from the Food System Policy Database (FSPD). Global Food Security. https://doi.org/10.1016/j.gfs.2025.100894

OpenFPD builds on and extends the original FSPD dataset.

## License

(To be determined)
