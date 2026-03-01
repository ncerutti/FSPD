"""
Configuration for FSPD classification models.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelConfig:
    """Configuration for transformer-based classification models."""

    # Model architecture
    base_model: str = "xlm-roberta-base"  # SOTA multilingual model (100 languages)
    max_length: int = 512  # Maximum sequence length

    # Training parameters
    batch_size: int = 16
    learning_rate: float = 2e-5
    num_epochs: int = 10
    warmup_steps: int = 500
    weight_decay: float = 0.01

    # Data splits
    train_split: float = 0.8
    val_split: float = 0.1
    test_split: float = 0.1
    random_seed: int = 42

    # Class weighting (to handle imbalance)
    use_class_weights: bool = True

    # Multi-task learning weights
    segment_weight: float = 1.0
    lever_weight: float = 1.0
    type_weight: float = 1.0
    inclusion_weight: float = 0.5
    envitarget_weight: float = 0.5
    diethealth_weight: float = 0.5

    # Early stopping
    patience: int = 3
    min_delta: float = 0.001

    # Confidence thresholds
    confidence_threshold: float = 0.7  # Flag predictions below this for review

    # Output paths
    output_dir: str = "outputs/models"
    checkpoint_dir: str = "outputs/models/checkpoints"

    # Logging
    log_every_n_steps: int = 50
    eval_every_n_steps: int = 500


@dataclass
class DataConfig:
    """Configuration for data processing."""

    # File paths
    data_path: str = "data/FSPD.csv"
    ml_ready_path: str = "data/FSPD_ml_ready.csv"

    # Text column
    text_column: str = "policydecision_details"

    # Target columns
    segment_column: str = "segment"
    lever_column: str = "lever"
    type_column: str = "itype"
    inclusion_column: str = "inclusion"
    envitarget_column: str = "envitarget"
    diethealth_column: str = "diethealth"

    # Preprocessing
    min_text_length: int = 10  # Filter out very short texts
    clean_text: bool = True
    lowercase: bool = False  # Keep case for better entity recognition
