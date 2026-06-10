#!/usr/bin/env python3
"""
OpenFPD two-stage policy classifier (CPU inference).

=============================================================================
WARNING: DO NOT RUN THIS SCRIPT ON A LOCAL DEVELOPMENT MACHINE.
It loads a 1.1 GB transformer checkpoint and runs inference. It is intended
to be executed ONLY in CI (GitHub Actions) or on Kaggle, after downloading
the model artifacts from the private Hugging Face repo
ncerutti/openfpd-classifier. See docs/models.md.
=============================================================================

Pipeline (mirrors src/models/stage2.py preprocessing exactly):
  1. Stage 1: FSPDMultiTaskModel (XLM-RoBERTa-base) extracts 768-dim [CLS]
     embeddings from the `policydecision_details` text column.
  2. Categorical metadata (region_wb, income_group, db, country) is
     ordinal-encoded with the saved OrdinalEncoder (cat_encoder.joblib;
     fillna('Unknown'), unseen values -> -1).
  3. Stage 2: per-task XGBoost classifiers (stage2_models/*.joblib) predict
     segment, lever, type (multiclass) and inclusion, envitarget, diethealth
     (binary). Multiclass labels are decoded with label_encoders.joblib.

Confidences are computed from raw booster margins (softmax for multiclass,
sigmoid for binary) so they are valid regardless of the training objective
(multi:softmax does not expose calibrated predict_proba).

Usage:
  python classify_new.py \
      --model_dir models/ \
      --input data/new_policies.parquet \
      --output data/new_policies_classified.parquet

model_dir layout (as downloaded from the HF repo):
  best_model_slim.pt
  cat_encoder.joblib
  stage2_models/{segment,lever,type,inclusion,envitarget,diethealth}.joblib
  stage2_models/label_encoders.joblib
"""
import argparse
import os
import sys

import joblib
import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer

# Make src/ importable when run from the repo root (CI checkout)
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, 'src', 'models'))

from src.models.model import FSPDMultiTaskModel  # noqa: E402
from src.models.config import ModelConfig  # noqa: E402

MULTICLASS_TASKS = ['segment', 'lever', 'type']
BINARY_TASKS = ['inclusion', 'envitarget', 'diethealth']
CAT_FEATURES = ['region_wb', 'income_group', 'db', 'country']
TEXT_COLUMN = 'policydecision_details'
CONFIDENCE_THRESHOLD = 0.7


def load_stage1(model_dir: str):
    """Load the slim Stage 1 checkpoint (weights + label encoders + config)."""
    ckpt_path = os.path.join(model_dir, 'best_model_slim.pt')
    print(f'Loading Stage 1 checkpoint: {ckpt_path}')
    checkpoint = torch.load(ckpt_path, map_location='cpu', weights_only=False)

    config = ModelConfig()
    base_model = checkpoint.get('config', {}).get('base_model', config.base_model)
    model = FSPDMultiTaskModel(
        base_model,
        len(checkpoint['segment_encoder'].classes_),
        len(checkpoint['lever_encoder'].classes_),
        len(checkpoint['type_encoder'].classes_),
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    return model, tokenizer, config.max_length


def extract_embeddings(model, tokenizer, texts, max_length, batch_size):
    """Batched CPU extraction of 768-dim [CLS] embeddings."""
    all_embeddings = []
    n_batches = (len(texts) + batch_size - 1) // batch_size
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        enc = tokenizer(batch, max_length=max_length, padding=True,
                        truncation=True, return_tensors='pt')
        with torch.no_grad():
            out = model(enc['input_ids'], enc['attention_mask'], return_hidden=True)
        all_embeddings.append(out['hidden_states'].numpy())
        done = i // batch_size + 1
        if done % 10 == 0 or done == n_batches:
            print(f'  embeddings: batch {done}/{n_batches}')
    return np.vstack(all_embeddings)


def encode_categoricals(df: pd.DataFrame, model_dir: str) -> np.ndarray:
    """Mirror stage2.py: fillna('Unknown'), OrdinalEncoder, unseen -> -1."""
    cats = pd.DataFrame(index=df.index)
    for col in CAT_FEATURES:
        cats[col] = df[col].fillna('Unknown') if col in df.columns else 'Unknown'
        if col not in df.columns:
            print(f'  WARNING: column {col!r} missing from input; using "Unknown"')
    enc_path = os.path.join(model_dir, 'cat_encoder.joblib')
    if os.path.exists(enc_path):
        enc = joblib.load(enc_path)
        return enc.transform(cats[CAT_FEATURES])
    print('  WARNING: cat_encoder.joblib not found; encoding all categoricals as -1 '
          '(embeddings carry ~99% of feature importance, impact is marginal)')
    return np.full((len(df), len(CAT_FEATURES)), -1.0)


def softmax(margins: np.ndarray) -> np.ndarray:
    z = margins - margins.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def predict_stage2(model_dir: str, X: np.ndarray) -> pd.DataFrame:
    """Run all six XGBoost classifiers; return labels + per-task confidence."""
    stage2_dir = os.path.join(model_dir, 'stage2_models')
    label_encoders = joblib.load(os.path.join(stage2_dir, 'label_encoders.joblib'))

    out = pd.DataFrame()
    for task in MULTICLASS_TASKS + BINARY_TASKS:
        clf = joblib.load(os.path.join(stage2_dir, f'{task}.joblib'))
        margins = clf.predict(X, output_margin=True)
        if task in MULTICLASS_TASKS:
            probs = softmax(margins)
            idx = probs.argmax(axis=1)
            out[f'pred_{task}'] = label_encoders[task].inverse_transform(idx)
            out[f'{task}_confidence'] = probs.max(axis=1)
        else:
            probs = 1.0 / (1.0 + np.exp(-margins.ravel()))
            preds = (probs > 0.5).astype(int)
            out[f'pred_{task}'] = preds
            out[f'{task}_confidence'] = np.where(preds == 1, probs, 1.0 - probs)
        print(f'  {task}: done')
    return out


def main():
    parser = argparse.ArgumentParser(description='Classify new OpenFPD policies (CI/Kaggle only)')
    parser.add_argument('--model_dir', required=True,
                        help='Directory with best_model_slim.pt, cat_encoder.joblib, stage2_models/')
    parser.add_argument('--input', required=True, help='Input parquet/csv of new policies')
    parser.add_argument('--output', required=True, help='Output parquet/csv with predictions')
    parser.add_argument('--text_column', default=TEXT_COLUMN)
    parser.add_argument('--batch_size', type=int, default=16)
    parser.add_argument('--threshold', type=float, default=CONFIDENCE_THRESHOLD,
                        help='needs_review flag when any task confidence is below this')
    args = parser.parse_args()

    read = pd.read_parquet if args.input.endswith('.parquet') else pd.read_csv
    df = read(args.input)
    print(f'Loaded {len(df)} policies from {args.input}')
    if args.text_column not in df.columns:
        sys.exit(f'ERROR: text column {args.text_column!r} not in input columns')

    texts = df[args.text_column].fillna('').astype(str).tolist()

    model, tokenizer, max_length = load_stage1(args.model_dir)
    print('Extracting embeddings (CPU)...')
    embeddings = extract_embeddings(model, tokenizer, texts, max_length, args.batch_size)

    print('Encoding categorical metadata...')
    X_cat = encode_categoricals(df, args.model_dir)
    X = np.hstack([embeddings, X_cat])
    print(f'Feature matrix: {X.shape}')

    print('Running Stage 2 classifiers...')
    preds = predict_stage2(args.model_dir, X)

    conf_cols = [c for c in preds.columns if c.endswith('_confidence')]
    preds['needs_review'] = (preds[conf_cols] < args.threshold).any(axis=1)
    # Empty/near-empty text cannot be classified reliably
    short_text = pd.Series(texts).str.len() < 10
    preds.loc[short_text.values, 'needs_review'] = True

    result = pd.concat([df.reset_index(drop=True), preds.reset_index(drop=True)], axis=1)
    if args.output.endswith('.parquet'):
        result.to_parquet(args.output, index=False)
    else:
        result.to_csv(args.output, index=False)

    n_review = int(preds['needs_review'].sum())
    print(f'\nSaved {len(result)} rows to {args.output}')
    print(f'Flagged for review: {n_review} ({100 * n_review / max(len(result), 1):.1f}%)')


if __name__ == '__main__':
    main()
