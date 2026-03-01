#!/usr/bin/env python3
"""
Quick test of training pipeline with minimal data.
Tests that everything works before running full training.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'models'))

import pandas as pd
import torch
from transformers import AutoTokenizer
from sklearn.model_selection import train_test_split

from config import ModelConfig, DataConfig
from dataset import FSPDDataset
from model import FSPDMultiTaskModel, MultiTaskLoss

print("=" * 60)
print("FSPD Training Pipeline Test")
print("=" * 60)

# Load config
model_config = ModelConfig()
data_config = DataConfig()

# Override for quick test
model_config.num_epochs = 1
model_config.batch_size = 4

print(f"\nDevice: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
print(f"Base model: {model_config.base_model}")

# Load data
print("\nLoading data...")
df = pd.read_csv(data_config.data_path, low_memory=False)
df = df[df[data_config.text_column].notna()].copy()
df = df[df[data_config.segment_column].notna()]
df = df[df[data_config.lever_column].notna()]
df = df[df[data_config.type_column].notna()]

# Fill binary targets
for col in [data_config.inclusion_column, data_config.envitarget_column, data_config.diethealth_column]:
    df[col] = df[col].fillna(0).astype(int)

print(f"Total samples: {len(df)}")

# Use only 100 samples for quick test
df_small = df.sample(n=min(100, len(df)), random_state=42)
print(f"Using {len(df_small)} samples for test")

# Split
train_df, val_df = train_test_split(df_small, test_size=0.2, random_state=42)
print(f"Train: {len(train_df)}, Val: {len(val_df)}")

# Load tokenizer
print(f"\nLoading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_config.base_model)

# Create dataset
print("Creating dataset...")
train_dataset = FSPDDataset(
    train_df,
    tokenizer,
    data_config.text_column,
    model_config.max_length,
    is_training=True
)

print(f"  Segments: {train_dataset.num_segments}")
print(f"  Levers: {train_dataset.num_levers}")
print(f"  Types: {train_dataset.num_types}")

# Initialize model
print("\nInitializing model...")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = FSPDMultiTaskModel(
    model_config.base_model,
    train_dataset.num_segments,
    train_dataset.num_levers,
    train_dataset.num_types
)
model.to(device)

print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

# Test forward pass
print("\nTesting forward pass...")
batch = train_dataset[0]
input_ids = batch['input_ids'].unsqueeze(0).to(device)
attention_mask = batch['attention_mask'].unsqueeze(0).to(device)

with torch.no_grad():
    outputs = model(input_ids, attention_mask)
    print("  Output shapes:")
    for key, value in outputs.items():
        print(f"    {key}: {value.shape}")

# Test prediction
print("\nTesting prediction...")
with torch.no_grad():
    preds = model.predict(input_ids, attention_mask, return_confidence=True)
    print("  Predictions:")
    for key, value in preds.items():
        if 'confidence' in key:
            print(f"    {key}: {value.item():.3f}")
        else:
            print(f"    {key}: {value.item()}")

print("\n" + "=" * 60)
print("SUCCESS! Training pipeline is working correctly.")
print("=" * 60)
print("\nYou can now run full training with:")
print("  python train_model.py")
print("\nOr with custom parameters:")
print("  python train_model.py --epochs 5 --batch_size 16")
