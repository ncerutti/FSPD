# Living Food System Policy Database (FSPD)

An automated system for maintaining and expanding the Food System Policy Database using machine learning classification.

## Project Overview

The Food System Policy Database (FSPD) contains approximately 11,900 policies and 3,700 frameworks covering 192 countries and eight regional groups. This project transforms the FSPD from a static snapshot into a living database that automatically:

1. Ingests new policies from source databases (FAPDA, PINE, GIfNA)
2. Classifies them using transformer-based ML models
3. Updates the database with confidence scores
4. Makes data available through a web interface and API

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

## Project Structure

```
FSPD/
├── data/                      # Raw and processed data
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

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for detailed instructions.

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

### Run Analysis
```bash
jupyter notebook notebooks/01_exploratory_analysis.ipynb
```

## Model Architecture

- **Base Model**: XLM-RoBERTa (multilingual, 100 languages)
- **Multi-task Learning**: 6 simultaneous predictions
  - Segment (11 classes)
  - Lever (113 classes)
  - Type (9 classes)
  - Inclusion (binary)
  - Environmental target (binary)
  - Diet health (binary)
- **Confidence Scores**: Each prediction includes calibrated confidence
- **Auto-flagging**: Low-confidence predictions marked for review

## References

Lowder, S.K., Ruggeri Laderchi, C., Cerutti, N., Parsons, K. (2025). Food System Policies: a Global Snapshot from the Food System Policy Database (FSPD). Global Food Security. https://doi.org/10.1016/j.gfs.2025.100894

## License

(To be determined)
