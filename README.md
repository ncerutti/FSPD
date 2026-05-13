# Living Food System Policy Database (FSPD)

Automated ML pipeline that transforms the static FSPD into a living database via transformer-based policy classification.

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

## Data

15,592 policies from 195 countries, sourced from FAPDA, PINE, GIfNA, and Nourishing. Split 80/10/10, stratified by segment, seed=42.

## Reference

Lowder, S.K., Ruggeri Laderchi, C., Cerutti, N., Parsons, K. (2025). Food System Policies: a Global Snapshot from the Food System Policy Database (FSPD). Global Food Security. https://doi.org/10.1016/j.gfs.2025.100894
