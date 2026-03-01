# Quick Start

## Train Model
```bash
python train_model.py
```

## Make Predictions
```bash
python predict_policies.py \
  --model_path outputs/models/best_model.pt \
  --input data/new_policies.csv \
  --output predictions.csv
```

## Configuration
Edit `src/models/config.py` to customize training parameters.

## Output
Predictions include confidence scores and `needs_review` flag for low-confidence predictions (default threshold: 0.7).
