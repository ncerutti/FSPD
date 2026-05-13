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

## Fetch FAPDA Data (ETL)
```bash
python fetch_fapda_data.py --resource both --output_dir data/raw/fapda
```

Useful options:
- `--resource decisions` (or `frameworks`)
- `--limit 500` for a small sample run
- `--no_csv` to export JSONL only

## Fetch All Sources (ETL)
```bash
python fetch_all_data.py
```

Useful options:
- `--output_dir data` to set the base folder
- `--no_csv` to skip CSV for every source
- `--fapda_limit 500` for a quick smoke run
- `--pine_flow_id DSD_CAPMF@DF_CAPMF` (repeatable)

## Fetch GIFNA Data (ETL)
```bash
python fetch_gifna_data.py --output_dir data/raw/gifna
```

Useful options:
- `--skip_boundaries` to skip WHO boundary extraction
- `--no_csv` to export JSON/JSONL only

## Fetch PINE Data (ETL)
```bash
python fetch_pine_data.py --output_dir data/raw/pine
```

Useful options:
- `--list_flows` to see available OECD.ENV.EPI flow IDs
- `--flow_id DSD_CAPMF@DF_CAPMF` (repeatable)
- `--start_period 2010 --end_period 2025`
- `--no_csv` to export JSON/JSONL only

## Configuration
Edit `src/models/config.py` to customize training parameters.

## Output
Predictions include confidence scores and `needs_review` flag for low-confidence predictions (default threshold: 0.7).
