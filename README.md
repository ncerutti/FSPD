# Living Food System Policy Database (FSPD)

Automated ML pipeline that transforms the static FSPD into a living database via transformer-based policy classification.

## Project Overview

The Food System Policy Database (FSPD) contains approximately 11,900 policies and 3,700 frameworks covering 192 countries and eight regional groups. This project transforms the FSPD from a static snapshot into a living database that automatically:

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
| Production pipeline & API | In progress |

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
├── fetch_pine_data.py         # ETL entrypoint for PINE (OECD SDMX)
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

15,592 policies from 195 countries, sourced from FAPDA, PINE, GIfNA, and Nourishing. Split 80/10/10, stratified by segment, seed=42.

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

## License

(To be determined)
