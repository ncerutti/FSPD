"""
Dataset class for FSPD policy classification.
"""
import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import PreTrainedTokenizer
from typing import Dict, Any
from sklearn.preprocessing import LabelEncoder
import numpy as np


class FSPDDataset(Dataset):
    """
    Dataset for multi-task classification of food system policies.

    Predicts:
    - Segment (multi-class)
    - Lever (multi-class)
    - Type (multi-class)
    - Inclusion (binary)
    - Envitarget (binary)
    - Diethealth (binary)
    """

    def __init__(
        self,
        dataframe: pd.DataFrame,
        tokenizer: PreTrainedTokenizer,
        text_column: str,
        max_length: int = 512,
        segment_encoder: LabelEncoder = None,
        lever_encoder: LabelEncoder = None,
        type_encoder: LabelEncoder = None,
        is_training: bool = True
    ):
        """
        Args:
            dataframe: DataFrame with policy data
            tokenizer: HuggingFace tokenizer
            text_column: Name of column containing policy text
            max_length: Maximum sequence length
            segment_encoder: Fitted LabelEncoder for segments (if None, will fit)
            lever_encoder: Fitted LabelEncoder for levers (if None, will fit)
            type_encoder: Fitted LabelEncoder for types (if None, will fit)
            is_training: Whether this is training data (for fitting encoders)
        """
        self.dataframe = dataframe.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.text_column = text_column
        self.max_length = max_length

        # Initialize or use provided label encoders
        self.segment_encoder = segment_encoder or LabelEncoder()
        self.lever_encoder = lever_encoder or LabelEncoder()
        self.type_encoder = type_encoder or LabelEncoder()

        # Fit encoders on training data
        if is_training and segment_encoder is None:
            self.segment_encoder.fit(self.dataframe['segment'])
            self.lever_encoder.fit(self.dataframe['lever'])
            self.type_encoder.fit(self.dataframe['itype'])

        # Encode labels
        self.dataframe['segment_encoded'] = self.segment_encoder.transform(
            self.dataframe['segment']
        )
        self.dataframe['lever_encoded'] = self.lever_encoder.transform(
            self.dataframe['lever']
        )
        self.dataframe['type_encoded'] = self.type_encoder.transform(
            self.dataframe['itype']
        )

    def __len__(self) -> int:
        return len(self.dataframe)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """Get a single training example."""
        row = self.dataframe.iloc[idx]

        # Get text and tokenize
        text = str(row[self.text_column])
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        # Prepare item
        item = {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'segment_label': torch.tensor(row['segment_encoded'], dtype=torch.long),
            'lever_label': torch.tensor(row['lever_encoded'], dtype=torch.long),
            'type_label': torch.tensor(row['type_encoded'], dtype=torch.long),
            'inclusion_label': torch.tensor(row['inclusion'], dtype=torch.float),
            'envitarget_label': torch.tensor(row['envitarget'], dtype=torch.float),
            'diethealth_label': torch.tensor(row['diethealth'], dtype=torch.float),
        }

        return item

    @property
    def num_segments(self) -> int:
        """Number of unique segments."""
        return len(self.segment_encoder.classes_)

    @property
    def num_levers(self) -> int:
        """Number of unique levers."""
        return len(self.lever_encoder.classes_)

    @property
    def num_types(self) -> int:
        """Number of unique types."""
        return len(self.type_encoder.classes_)

    def get_class_weights(self, task: str = 'segment') -> torch.Tensor:
        """
        Calculate class weights for handling imbalance.

        Args:
            task: One of 'segment', 'lever', 'type'

        Returns:
            Tensor of class weights
        """
        if task == 'segment':
            labels = self.dataframe['segment_encoded']
            n_classes = self.num_segments
        elif task == 'lever':
            labels = self.dataframe['lever_encoded']
            n_classes = self.num_levers
        elif task == 'type':
            labels = self.dataframe['type_encoded']
            n_classes = self.num_types
        else:
            raise ValueError(f"Unknown task: {task}")

        # Calculate weights: inverse frequency
        class_counts = np.bincount(labels, minlength=n_classes)
        class_weights = 1.0 / (class_counts + 1)  # Add 1 to avoid division by zero
        class_weights = class_weights / class_weights.sum() * n_classes  # Normalize

        return torch.FloatTensor(class_weights)
