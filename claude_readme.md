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
- **Kaggle training**: Completed on GPU
- **Model artifacts**:
  - `outputs/models/best_model.pt` - Trained model + label encoders + config
  - `outputs/models/test_metrics.json` - Performance metrics on held-out test set
- **Performance**: [User has metrics from training - to be filled in when implementing XGBoost]

### 5. Conference Abstract (DONE)
- **Conference**: CS2Italy2026 (May 19-21, 2026, Torino)
- **Submission type**: Extended abstract (2 pages max, non-archival)
- **Location**: `abstract/cs2italy_template/`
  - `fspd_abstract_v1.tex`: RoBERTa-only, mentions XGBoost as future work
  - `fspd_abstract_v2.tex`: Two-stage hybrid (RoBERTa→XGBoost) presented as implemented
- **Key framing**: Methodology is transferable to any expert-curated social science database with text+metadata
- **Focus**: Balanced method + application, emphasizing the classification pipeline itself as a contribution

## Current Status of Two-Stage Approach
- **Stage 1 (RoBERTa)**: DONE - Text-only classification with multi-task learning
- **Stage 2 (XGBoost)**: TODO - Integrate embeddings + categorical features (country, region, income_group, year, source DB)

**Planned architecture**: Extract 768-dim CLS embeddings from trained RoBERTa → concatenate with categorical features → train XGBoost classifiers (one per task) → compare performance gains vs text-only baseline.

## Current Limitations (Stage 1 only)
1. **Text-only**: RoBERTa uses `policydecision_details` only, doesn't leverage categorical features that likely carry predictive signal
2. **Source imbalance**: Not stratifying by source database in train/val/test splits
3. **Binary objectives**: Standard BCE loss, no special handling for imbalance (23%, 20%, 35% positive rates)

## What's Next

### Immediate: Implement Stage 2 (XGBoost)
1. **Extract embeddings**: Modify predict.py to output 768-dim CLS embeddings for all samples
2. **Prepare features**: Concatenate embeddings + categorical features (country, region, income_group, year, db)
3. **Train XGBoost**: One classifier per task (6 total), handle class imbalance with scale_pos_weight
4. **Evaluate gains**: Compare Stage 2 performance vs Stage 1 baseline
5. **Feature importance**: Analyze which features (text vs categorical) drive predictions per task
6. **Update abstract**: Fill in performance numbers in v2 abstract for CS2Italy2026 submission

### Then: Production Pipeline
1. **Data ingestion** - Fetch new policies from FAPDA, PINE, GIfNA
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
1. Implement Stage 2 (XGBoost) to integrate categorical features
2. Evaluate performance gains from two-stage approach
3. Generate feature importance analysis (which features drive which tasks)
4. Fill in performance numbers in abstract v2 for conference submission
5. Consider whether to submit v1 (RoBERTa-only) or v2 (hybrid) depending on XGBoost results
