# Claude Context: Living FSPD Project

## Project Goal
Transform the static Food System Policy Database (FSPD) into a "living database" that automatically updates with new policies from source databases (FAPDA, PINE, GIfNA) using ML classification.

## What We've Built

### 1. Data Analysis (DONE)
- Dataset: 15,592 policies from 195 countries
- Sources: FAPDA (67%), FAPDA_F (24%), Nourishing (5%), PINE (4%)
- Classifications: 11 segments, 113 levers, 9 types + 3 binary objectives
- Significant class imbalance (Lever: 246:1 ratio)
- Multilingual text (Spanish, French, English) - avg 603 chars

### 2. ML Model Architecture (DONE)
- **Model**: XLM-RoBERTa-base (278M parameters, multilingual)
- **Multi-task learning**: 6 simultaneous predictions
  - Segment (11 classes)
  - Lever (113 classes)
  - Type (9 classes)
  - Inclusion, envitarget, diethealth (3 binary)
- **Handles imbalance**: Inverse frequency class weights for segment/lever/type
- **Confidence scores**: Each prediction includes confidence, auto-flags low confidence for review (threshold: 0.7)

### 3. Code Structure
```
FSPD/
├── data/FSPD.csv                    # Original dataset (15,592 policies)
├── src/models/                      # Model code
│   ├── config.py                    # Training configuration
│   ├── dataset.py                   # PyTorch dataset with label encoding
│   ├── model.py                     # Multi-task transformer model
│   ├── train.py                     # Training script
│   └── predict.py                   # Inference script
├── src/pipeline/                    # ETL code
│   └── fapda_etl.py                 # FAPDA extraction script (API-backed)
├── fetch_fapda_data.py              # Quick start ETL runner
├── fetch_gifna_data.py              # Quick start GIFNA ETL runner
├── fetch_pine_data.py               # Quick start PINE ETL runner
├── train_model.py                   # Quick start training
├── test_training.py                 # Test pipeline works
├── predict_policies.py              # Quick start prediction
├── kaggle_training.ipynb            # GPU training notebook (used for training)
├── notebooks/01_exploratory_analysis.ipynb
├── abstract/cs2italy_template/      # Conference abstract
│   ├── fspd_abstract_v1.tex        # RoBERTa-only version
│   └── fspd_abstract_v2.tex        # Hybrid RoBERTa→XGBoost version
├── notes-paper.md                   # Research notes (CONCISE)
└── outputs/models/                  # Trained models (best_model.pt)
```

### 4. XLM-RoBERTa Training (DONE)
- **Local test**: Successfully ran on CPU (verified pipeline works)
- **Kaggle training**: Completed on GPU (T4)
- **Model artifacts**:
  - `outputs/models/best_model.pt` - Trained model + label encoders + config (3.5GB, also on Kaggle)
  - `outputs/models/test_metrics.json` - Stage 1 metrics

### 5. XGBoost Hybrid (DONE)
- **Script**: `src/models/stage2.py` — run on Kaggle T4
- **Approach**: Frozen RoBERTa CLS embeddings (768-dim) + 4 categorical features → XGBoost per task
- **Model artifacts**:
  - `outputs/models/stage2_metrics.json` - Stage 1 vs Stage 2 comparison + feature importance
  - `outputs/models/stage2_models/` - Saved XGBoost classifiers (joblib) + label encoders
- **Key finding**: ~99% of predictive gain comes from embeddings; categorical metadata contributes marginally
- **Results** (F1): Segment 86.5, Lever 66.2, Type 90.4, Inclusion 71.4, EnviTarget 82.4, DietHealth 73.8

### 6. Conference Abstract (DONE)
- **Conference**: CS2Italy2026 (May 19-21, 2026, Torino)
- **Submission type**: Extended abstract (2 pages max, non-archival)
- **Location**: `abstract/cs2italy_template/fspd_abstract.tex`
- **Status**: Updated with full Stage 1 + Stage 2 results table; methodology in past tense
- **Key framing**: Methodology is transferable to any expert-curated social science database with text+metadata

## Current Status
- **Stage 1 (RoBERTa)**: DONE
- **Stage 2 (XGBoost)**: DONE
- **Abstract**: DONE — results filled in, ready to submit

**Planned architecture**: Extract 768-dim CLS embeddings from trained RoBERTa → concatenate with categorical features → train XGBoost classifiers (one per task) → compare performance gains vs text-only baseline.

## What's Next

### Production Pipeline
1. **Data ingestion** - FAPDA, GIFNA and PINE fetchers implemented (`fetch_*_data.py`)
2. **Schema mapping** - Transform source DB schemas to FSPD format
3. **Deduplication** - Detect duplicate policies across sources
4. **Database** - Storage for versioned data
5. **REST API** - FastAPI for data access
6. **Web interface** - Browse/search/filter policies, export data
7. **GitHub Actions** - Monthly automated updates

### Hosting Plan
- Frontend: GitHub Pages or Hostinger
- Data: Mendeley Data (mirrors)
- API: Hostinger (user has simple hosting)
- Updates: Monthly via GitHub Actions

## Key Commands

### Test pipeline
```bash
python test_training.py
```

### Train locally (CPU, slow)
```bash
python train_model.py --epochs 5 --batch_size 8
```

### Predict on new data
```bash
python predict_policies.py \
  --model_path outputs/models/best_model.pt \
  --input data/new_policies.csv \
  --output predictions.csv
```

### Fetch FAPDA data
```bash
python fetch_fapda_data.py --resource both --output_dir data/raw/fapda
```

### Fetch GIFNA data
```bash
python fetch_gifna_data.py --output_dir data/raw/gifna
```

### Fetch PINE data
```bash
python fetch_pine_data.py --output_dir data/raw/pine
```

### Kaggle training
Upload `kaggle_training.ipynb` to Kaggle with GPU enabled.

## Data Schema (Key Columns)
- `policydecision_details`: Main text for classification
- `segment`, `lever`, `itype`: Classification targets
- `inclusion`, `envitarget`, `diethealth`: Binary objectives
- `db`: Source database (FAPDA, FAPDA_F, Nourishing, PINE)
- `country`, `iso`: Geographic info
- `year`, `initialdate`: Temporal info

## Questions User Asked (Important Context)
1. **Class imbalance?** YES - handled via inverse frequency weights
2. **Source imbalance?** NO - not currently handled
3. **What else considered?** Multi-task learning, multilingual support, early stopping, gradient clipping, task-specific weights
4. **Categorical data?** NOT handled - text-only currently (future: add categorical features)

## Session Notes
- User prefers CONCISE documentation (not verbose)
- No emojis in communication
- uv environment already set up (use `uv pip install`)
- User wants to write a paper on this work - track insights in `notes-paper.md`
- Original FSPD paper: Lowder et al. (2025), Global Food Security
- Conference abstract drafted for CS2Italy2026 (submission deadline TBD)

## Next Session Priorities
1. Submit abstract to CS2Italy2026 (check submission deadline)
2. Build production pipeline: ingestion → schema mapping → deduplication → API
3. Deploy with monthly GitHub Actions automation
4. Domain expert validation of initial predictions
