# Stage 2 on Kaggle — 1 March 2026

This notebook runs Stage 2 of the FSPD automated classification pipeline.
Stage 1 (already complete) fine-tuned XLM-RoBERTa-base on ~12,500 food policies using multi-task learning across 6 targets: segment (11 classes), lever (113 classes), type (9 classes), and three binary objectives (inclusion, envitarget, diethealth).
Stage 2 extracts 768-dimensional [CLS] embeddings from the frozen Stage 1 model, concatenates them with 4 categorical metadata features (region_wb, income_group, db, country), and trains one XGBoost classifier per task.
The data split (80/10/10, seed=42, stratified by segment) is reproduced exactly so Stage 1 and Stage 2 test sets are identical and metrics are directly comparable.
The embedding extraction is the only GPU-heavy step — XGBoost training is CPU-only and fast.
Inputs needed: (1) FSPD.csv from the `fspd` dataset, (2) best_model.pt from the Stage 1 training output — check the exact input path and update `--model_path` in the script accordingly.
The three source files (stage2.py, model.py, config.py) must all be uploaded to the notebook.
Run with batch_size=64 (the default on Kaggle); the script auto-detects Kaggle and sets paths accordingly.
Output is `stage2_metrics.json` in `/kaggle/working/`, containing per-task accuracy and F1 for both stages plus feature importance (embedding % vs. categorical %).
Stage 1 baselines to beat: Segment F1=0.84, Lever F1=0.64, Type F1=0.87, Inclusion F1=0.65, EnviTarget F1=0.83, DietHealth F1=0.71.
