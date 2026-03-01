"""
Training script for FSPD multi-task classification model.
"""
import os
import argparse
import pandas as pd
import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, get_linear_schedule_with_warmup
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report
from tqdm.auto import tqdm
import json

from config import ModelConfig, DataConfig
from dataset import FSPDDataset
from model import FSPDMultiTaskModel, MultiTaskLoss


def set_seed(seed: int):
    """Set random seed for reproducibility."""
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)


def prepare_data(config: DataConfig, model_config: ModelConfig):
    """Load and split data."""
    print("Loading data...")
    df = pd.read_csv(config.data_path, low_memory=False)

    # Filter rows with valid data
    df = df[df[config.text_column].notna()].copy()
    df = df[df[config.segment_column].notna()]
    df = df[df[config.lever_column].notna()]
    df = df[df[config.type_column].notna()]

    # Fill binary targets
    for col in [config.inclusion_column, config.envitarget_column, config.diethealth_column]:
        df[col] = df[col].fillna(0).astype(int)

    # Filter by minimum text length
    df = df[df[config.text_column].str.len() >= config.min_text_length]

    print(f"Total samples: {len(df)}")

    # Split data
    train_df, temp_df = train_test_split(
        df,
        test_size=(1 - model_config.train_split),
        random_state=model_config.random_seed,
        stratify=df[config.segment_column]
    )

    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.5,
        random_state=model_config.random_seed,
        stratify=temp_df[config.segment_column]
    )

    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    return train_df, val_df, test_df


def create_dataloaders(
    train_df, val_df, test_df,
    tokenizer, config: DataConfig, model_config: ModelConfig
):
    """Create PyTorch DataLoaders."""
    print("Creating datasets...")

    # Create training dataset (fit encoders here)
    train_dataset = FSPDDataset(
        train_df,
        tokenizer,
        config.text_column,
        model_config.max_length,
        is_training=True
    )

    # Create val/test datasets (use fitted encoders)
    val_dataset = FSPDDataset(
        val_df,
        tokenizer,
        config.text_column,
        model_config.max_length,
        segment_encoder=train_dataset.segment_encoder,
        lever_encoder=train_dataset.lever_encoder,
        type_encoder=train_dataset.type_encoder,
        is_training=False
    )

    test_dataset = FSPDDataset(
        test_df,
        tokenizer,
        config.text_column,
        model_config.max_length,
        segment_encoder=train_dataset.segment_encoder,
        lever_encoder=train_dataset.lever_encoder,
        type_encoder=train_dataset.type_encoder,
        is_training=False
    )

    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=model_config.batch_size,
        shuffle=True,
        num_workers=4
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=model_config.batch_size,
        shuffle=False,
        num_workers=4
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=model_config.batch_size,
        shuffle=False,
        num_workers=4
    )

    return train_loader, val_loader, test_loader, train_dataset


def train_epoch(model, loader, optimizer, scheduler, loss_fn, device):
    """Train for one epoch."""
    model.train()
    total_loss = 0
    individual_losses = {
        'segment': 0, 'lever': 0, 'type': 0,
        'inclusion': 0, 'envitarget': 0, 'diethealth': 0
    }

    progress_bar = tqdm(loader, desc="Training")

    for batch in progress_bar:
        # Move to device
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = {k: v.to(device) for k, v in batch.items() if k.endswith('_label')}

        # Forward pass
        outputs = model(input_ids, attention_mask)
        loss, ind_losses = loss_fn(outputs, labels)

        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        # Track losses
        total_loss += loss.item()
        for k, v in ind_losses.items():
            individual_losses[k] += v

        progress_bar.set_postfix({'loss': loss.item()})

    avg_loss = total_loss / len(loader)
    avg_ind_losses = {k: v / len(loader) for k, v in individual_losses.items()}

    return avg_loss, avg_ind_losses


def evaluate(model, loader, loss_fn, device):
    """Evaluate model."""
    model.eval()
    total_loss = 0

    # Collect predictions and labels
    all_preds = {
        'segment': [], 'lever': [], 'type': [],
        'inclusion': [], 'envitarget': [], 'diethealth': []
    }
    all_labels = {
        'segment': [], 'lever': [], 'type': [],
        'inclusion': [], 'envitarget': [], 'diethealth': []
    }

    with torch.no_grad():
        for batch in tqdm(loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = {k: v.to(device) for k, v in batch.items() if k.endswith('_label')}

            outputs = model(input_ids, attention_mask)
            loss, _ = loss_fn(outputs, labels)
            total_loss += loss.item()

            # Get predictions
            preds = model.predict(input_ids, attention_mask, return_confidence=False)

            # Collect for metrics
            all_preds['segment'].extend(preds['segment'].cpu().numpy())
            all_preds['lever'].extend(preds['lever'].cpu().numpy())
            all_preds['type'].extend(preds['type'].cpu().numpy())
            all_preds['inclusion'].extend(preds['inclusion'].cpu().numpy())
            all_preds['envitarget'].extend(preds['envitarget'].cpu().numpy())
            all_preds['diethealth'].extend(preds['diethealth'].cpu().numpy())

            all_labels['segment'].extend(labels['segment_label'].cpu().numpy())
            all_labels['lever'].extend(labels['lever_label'].cpu().numpy())
            all_labels['type'].extend(labels['type_label'].cpu().numpy())
            all_labels['inclusion'].extend(labels['inclusion_label'].cpu().numpy())
            all_labels['envitarget'].extend(labels['envitarget_label'].cpu().numpy())
            all_labels['diethealth'].extend(labels['diethealth_label'].cpu().numpy())

    # Calculate metrics
    metrics = {}
    for task in ['segment', 'lever', 'type', 'inclusion', 'envitarget', 'diethealth']:
        acc = accuracy_score(all_labels[task], all_preds[task])
        f1 = f1_score(all_labels[task], all_preds[task], average='weighted' if task in ['segment', 'lever', 'type'] else 'binary')
        metrics[f'{task}_acc'] = acc
        metrics[f'{task}_f1'] = f1

    avg_loss = total_loss / len(loader)

    return avg_loss, metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--epochs', type=int, default=None)
    parser.add_argument('--batch_size', type=int, default=None)
    parser.add_argument('--lr', type=float, default=None)
    args = parser.parse_args()

    # Load configs
    model_config = ModelConfig()
    data_config = DataConfig()

    # Override with command line args
    if args.epochs:
        model_config.num_epochs = args.epochs
    if args.batch_size:
        model_config.batch_size = args.batch_size
    if args.lr:
        model_config.learning_rate = args.lr

    # Set seed
    set_seed(model_config.random_seed)

    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Prepare data
    train_df, val_df, test_df = prepare_data(data_config, model_config)

    # Load tokenizer
    print(f"Loading tokenizer: {model_config.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(model_config.base_model)

    # Create dataloaders
    train_loader, val_loader, test_loader, train_dataset = create_dataloaders(
        train_df, val_df, test_df, tokenizer, data_config, model_config
    )

    # Initialize model
    print("Initializing model...")
    model = FSPDMultiTaskModel(
        model_config.base_model,
        train_dataset.num_segments,
        train_dataset.num_levers,
        train_dataset.num_types
    )
    model.to(device)

    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Get class weights if enabled
    segment_weights = None
    lever_weights = None
    type_weights = None

    if model_config.use_class_weights:
        segment_weights = train_dataset.get_class_weights('segment').to(device)
        lever_weights = train_dataset.get_class_weights('lever').to(device)
        type_weights = train_dataset.get_class_weights('type').to(device)

    # Loss function
    loss_fn = MultiTaskLoss(
        segment_weight=model_config.segment_weight,
        lever_weight=model_config.lever_weight,
        type_weight=model_config.type_weight,
        inclusion_weight=model_config.inclusion_weight,
        envitarget_weight=model_config.envitarget_weight,
        diethealth_weight=model_config.diethealth_weight,
        segment_class_weights=segment_weights,
        lever_class_weights=lever_weights,
        type_class_weights=type_weights
    )

    # Optimizer and scheduler
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=model_config.learning_rate,
        weight_decay=model_config.weight_decay
    )

    total_steps = len(train_loader) * model_config.num_epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=model_config.warmup_steps,
        num_training_steps=total_steps
    )

    # Training loop
    best_val_loss = float('inf')
    patience_counter = 0

    os.makedirs(model_config.output_dir, exist_ok=True)

    print("\nStarting training...")
    for epoch in range(model_config.num_epochs):
        print(f"\nEpoch {epoch + 1}/{model_config.num_epochs}")

        # Train
        train_loss, train_ind_losses = train_epoch(
            model, train_loader, optimizer, scheduler, loss_fn, device
        )
        print(f"Train Loss: {train_loss:.4f}")
        print(f"  Individual: {', '.join([f'{k}: {v:.4f}' for k, v in train_ind_losses.items()])}")

        # Validate
        val_loss, val_metrics = evaluate(model, val_loader, loss_fn, device)
        print(f"Val Loss: {val_loss:.4f}")
        print(f"  Accuracies: {', '.join([f'{k}: {v:.3f}' for k, v in val_metrics.items() if k.endswith('_acc')])}")
        print(f"  F1 Scores: {', '.join([f'{k}: {v:.3f}' for k, v in val_metrics.items() if k.endswith('_f1')])}")

        # Early stopping
        if val_loss < best_val_loss - model_config.min_delta:
            best_val_loss = val_loss
            patience_counter = 0
            # Save best model
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': val_loss,
                'val_metrics': val_metrics,
                'segment_encoder': train_dataset.segment_encoder,
                'lever_encoder': train_dataset.lever_encoder,
                'type_encoder': train_dataset.type_encoder,
            }, os.path.join(model_config.output_dir, 'best_model.pt'))
            print("  -> Saved best model")
        else:
            patience_counter += 1
            if patience_counter >= model_config.patience:
                print(f"Early stopping triggered after {epoch + 1} epochs")
                break

    # Test evaluation
    print("\nEvaluating on test set...")
    checkpoint = torch.load(os.path.join(model_config.output_dir, 'best_model.pt'))
    model.load_state_dict(checkpoint['model_state_dict'])
    test_loss, test_metrics = evaluate(model, test_loader, loss_fn, device)

    print(f"\nTest Results:")
    print(f"  Loss: {test_loss:.4f}")
    for k, v in test_metrics.items():
        print(f"  {k}: {v:.3f}")

    # Save test metrics
    with open(os.path.join(model_config.output_dir, 'test_metrics.json'), 'w') as f:
        json.dump(test_metrics, f, indent=2)

    print(f"\nTraining complete! Model saved to {model_config.output_dir}")


if __name__ == '__main__':
    main()
