"""Stage 2: XGBoost classifiers using XLM-RoBERTa CLS embeddings + categorical metadata."""
import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder
from sklearn.metrics import accuracy_score, f1_score
import xgboost as xgb
from tqdm.auto import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import FSPDMultiTaskModel
from config import ModelConfig, DataConfig

IS_KAGGLE = os.path.exists('/kaggle/working')

MULTICLASS_TASKS = ['segment', 'lever', 'type']
BINARY_TASKS = ['inclusion', 'envitarget', 'diethealth']
CAT_FEATURES = ['region_wb', 'income_group', 'db', 'country']

STAGE1_METRICS = {
    'segment':    {'acc': 0.8326, 'f1': 0.8387},
    'lever':      {'acc': 0.6359, 'f1': 0.6374},
    'type':       {'acc': 0.8637, 'f1': 0.8702},
    'inclusion':  {'acc': 0.8576, 'f1': 0.6541},
    'envitarget': {'acc': 0.9594, 'f1': 0.8278},
    'diethealth': {'acc': 0.8430, 'f1': 0.7093},
}


def prepare_data(config: DataConfig, model_config: ModelConfig):
    """Reproduce exact same split as Stage 1 (seed=42, stratify=segment)."""
    df = pd.read_csv(config.data_path, low_memory=False)
    df = df[df[config.text_column].notna()].copy()
    df = df[df[config.segment_column].notna()]
    df = df[df[config.lever_column].notna()]
    df = df[df[config.type_column].notna()]
    for col in [config.inclusion_column, config.envitarget_column, config.diethealth_column]:
        df[col] = df[col].fillna(0).astype(int)
    df = df[df[config.text_column].str.len() >= config.min_text_length]

    train_df, temp_df = train_test_split(
        df, test_size=(1 - model_config.train_split),
        random_state=model_config.random_seed, stratify=df[config.segment_column]
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.5,
        random_state=model_config.random_seed, stratify=temp_df[config.segment_column]
    )
    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


def extract_embeddings(model, texts, tokenizer, max_length, device, batch_size=32):
    """Extract [CLS] embeddings from XLM-RoBERTa in batches. Returns (N, 768) array."""
    model.eval()
    all_embeddings = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Extracting embeddings"):
        batch = texts[i:i + batch_size]
        enc = tokenizer(batch, max_length=max_length, padding='max_length',
                        truncation=True, return_tensors='pt')
        with torch.no_grad():
            out = model(enc['input_ids'].to(device), enc['attention_mask'].to(device),
                        return_hidden=True)
        all_embeddings.append(out['hidden_states'].cpu().numpy())
    return np.vstack(all_embeddings)


def encode_categoricals(train_df, val_df, test_df):
    """Ordinal-encode categorical metadata. Fit on train, apply to val/test."""
    dfs = [train_df, val_df, test_df]
    for df in dfs:
        for col in CAT_FEATURES:
            df[col] = df[col].fillna('Unknown')
    enc = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
    enc.fit(train_df[CAT_FEATURES])
    return (
        enc.transform(train_df[CAT_FEATURES]),
        enc.transform(val_df[CAT_FEATURES]),
        enc.transform(test_df[CAT_FEATURES]),
        enc,
    )


def get_labels(df, task, label_encoders):
    col_map = {'segment': 'segment', 'lever': 'lever', 'type': 'itype'}
    enc_map = {'segment': 'segment_encoder', 'lever': 'lever_encoder', 'type': 'type_encoder'}
    if task in MULTICLASS_TASKS:
        return label_encoders[enc_map[task]].transform(df[col_map[task]])
    return df[task].values


def train_classifier(X_train, y_train, X_val, y_val, task):
    """Train a single XGBoost classifier with early stopping."""
    common = dict(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        verbosity=0, early_stopping_rounds=30,
    )
    if task in BINARY_TASKS:
        pos = y_train.sum()
        clf = xgb.XGBClassifier(
            objective='binary:logistic', eval_metric='logloss',
            scale_pos_weight=(len(y_train) - pos) / max(pos, 1),
            **common
        )
    else:
        classes, counts = np.unique(y_train, return_counts=True)
        freq = dict(zip(classes, counts))
        sample_weights = np.array([1.0 / freq[y] for y in y_train])
        clf = xgb.XGBClassifier(
            objective='multi:softmax', eval_metric='mlogloss', **common
        )
        clf.fit(X_train, y_train, sample_weight=sample_weights,
                eval_set=[(X_val, y_val)], verbose=False)
        return clf
    clf.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return clf


def evaluate(clf, X_test, y_test, task):
    preds = clf.predict(X_test)
    avg = 'binary' if task in BINARY_TASKS else 'weighted'
    return {
        'acc': round(float(accuracy_score(y_test, preds)), 4),
        'f1':  round(float(f1_score(y_test, preds, average=avg, zero_division=0)), 4),
    }


def feature_importance_summary(clf, task):
    """Aggregate feature importance: embedding block vs individual categorical features."""
    imp = clf.get_booster().get_score(importance_type='gain')
    embed_imp = sum(v for k, v in imp.items() if int(k[1:]) < 768)
    cat_imp = {CAT_FEATURES[i]: imp.get(f'f{768 + i}', 0.0) for i in range(len(CAT_FEATURES))}
    total = embed_imp + sum(cat_imp.values()) or 1.0
    return {
        'embedding_pct': round(100 * embed_imp / total, 1),
        'categorical': {k: round(100 * v / total, 1) for k, v in cat_imp.items()},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_path',
                        default='/kaggle/input/fspd-stage1/models/best_model.pt' if IS_KAGGLE
                                else 'outputs/models/best_model.pt',
                        help='Path to Stage 1 best_model.pt (on Kaggle: verify the dataset slug)')
    parser.add_argument('--output_dir',
                        default='/kaggle/working' if IS_KAGGLE else 'outputs/models')
    parser.add_argument('--batch_size', type=int,
                        default=64 if IS_KAGGLE else 32,
                        help='Batch size for embedding extraction')
    parser.add_argument('--device', default=None)
    args = parser.parse_args()

    config = DataConfig()
    if IS_KAGGLE:
        config.data_path = '/kaggle/input/fspd/FSPD.csv'
    model_config = ModelConfig()

    device = torch.device(args.device or ('cuda' if torch.cuda.is_available() else 'cpu'))
    print(f"Device: {device}")

    # --- Data ---
    train_df, val_df, test_df = prepare_data(config, model_config)

    # --- Load RoBERTa ---
    print(f"Loading RoBERTa from {args.model_path}")
    checkpoint = torch.load(args.model_path, map_location='cpu', weights_only=False)
    label_encoders = {
        'segment_encoder': checkpoint['segment_encoder'],
        'lever_encoder':   checkpoint['lever_encoder'],
        'type_encoder':    checkpoint['type_encoder'],
    }
    tokenizer = AutoTokenizer.from_pretrained(model_config.base_model)
    roberta = FSPDMultiTaskModel(
        model_config.base_model,
        len(label_encoders['segment_encoder'].classes_),
        len(label_encoders['lever_encoder'].classes_),
        len(label_encoders['type_encoder'].classes_),
    )
    roberta.load_state_dict(checkpoint['model_state_dict'])
    roberta.to(device)

    # --- Embeddings ---
    splits = {'train': train_df, 'val': val_df, 'test': test_df}
    embeddings = {}
    for split, df in splits.items():
        texts = df[config.text_column].fillna('').tolist()
        print(f"Extracting embeddings: {split} ({len(texts)} samples)")
        embeddings[split] = extract_embeddings(
            roberta, texts, tokenizer, model_config.max_length, device, args.batch_size
        )

    # --- Categorical features ---
    X_cat_train, X_cat_val, X_cat_test, _ = encode_categoricals(train_df, val_df, test_df)
    X = {
        'train': np.hstack([embeddings['train'], X_cat_train]),
        'val':   np.hstack([embeddings['val'],   X_cat_val]),
        'test':  np.hstack([embeddings['test'],  X_cat_test]),
    }
    print(f"\nFeature matrix: {X['train'].shape[1]} dims "
          f"(768 embeddings + {len(CAT_FEATURES)} categorical)")

    # --- Train & evaluate ---
    results = {}
    importances = {}
    for task in MULTICLASS_TASKS + BINARY_TASKS:
        print(f"\n[{task}] Training XGBoost...")
        y = {s: get_labels(splits[s], task, label_encoders) for s in ['train', 'val', 'test']}
        clf = train_classifier(X['train'], y['train'], X['val'], y['val'], task)
        results[task] = evaluate(clf, X['test'], y['test'], task)
        importances[task] = feature_importance_summary(clf, task)
        s1, s2 = STAGE1_METRICS[task], results[task]
        print(f"  F1: {s1['f1']:.4f} (Stage 1) → {s2['f1']:.4f} (Stage 2) "
              f"({s2['f1'] - s1['f1']:+.4f})")

    # --- Save ---
    out_path = os.path.join(args.output_dir, 'stage2_metrics.json')
    with open(out_path, 'w') as f:
        json.dump({'stage2': results, 'stage1': STAGE1_METRICS, 'importance': importances}, f, indent=2)
    print(f"\nSaved to {out_path}")

    # --- Comparison table ---
    print("\n=== Stage 1 vs Stage 2 ===")
    print(f"{'Task':<20} {'S1 Acc':>8} {'S2 Acc':>8} {'ΔAcc':>7} {'S1 F1':>8} {'S2 F1':>8} {'ΔF1':>7}")
    print("-" * 70)
    for task in MULTICLASS_TASKS + BINARY_TASKS:
        s1, s2 = STAGE1_METRICS[task], results[task]
        print(f"{task:<20} {s1['acc']:>8.4f} {s2['acc']:>8.4f} {s2['acc']-s1['acc']:>+7.4f}"
              f" {s1['f1']:>8.4f} {s2['f1']:>8.4f} {s2['f1']-s1['f1']:>+7.4f}")

    print("\n=== Feature Importance (% gain) ===")
    print(f"{'Task':<20} {'Embed%':>8} " + "  ".join(f"{c:>12}" for c in CAT_FEATURES))
    print("-" * 80)
    for task in MULTICLASS_TASKS + BINARY_TASKS:
        imp = importances[task]
        cat_vals = "  ".join(f"{imp['categorical'][c]:>11.1f}%" for c in CAT_FEATURES)
        print(f"{task:<20} {imp['embedding_pct']:>7.1f}%  {cat_vals}")


if __name__ == '__main__':
    main()
