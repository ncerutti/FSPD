"""
Inference script for FSPD classification model.
"""
import torch
from transformers import AutoTokenizer
import pandas as pd
from typing import List, Dict
import argparse
import os

from model import FSPDMultiTaskModel
from config import ModelConfig


class FSPDPredictor:
    """Class for making predictions on new policies."""

    def __init__(self, model_path: str, device: str = None):
        """
        Args:
            model_path: Path to saved model checkpoint
            device: Device to run on ('cuda' or 'cpu')
        """
        # Load checkpoint
        print(f"Loading model from {model_path}")
        checkpoint = torch.load(model_path, map_location='cpu')

        # Get encoders
        self.segment_encoder = checkpoint['segment_encoder']
        self.lever_encoder = checkpoint['lever_encoder']
        self.type_encoder = checkpoint['type_encoder']

        # Initialize model
        config = ModelConfig()
        self.tokenizer = AutoTokenizer.from_pretrained(config.base_model)

        self.model = FSPDMultiTaskModel(
            config.base_model,
            len(self.segment_encoder.classes_),
            len(self.lever_encoder.classes_),
            len(self.type_encoder.classes_)
        )

        # Load weights
        self.model.load_state_dict(checkpoint['model_state_dict'])

        # Set device
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()

        self.max_length = config.max_length
        self.confidence_threshold = config.confidence_threshold

        print(f"Model loaded on {self.device}")

    def predict(self, texts: List[str]) -> pd.DataFrame:
        """
        Make predictions for a list of policy texts.

        Args:
            texts: List of policy descriptions

        Returns:
            DataFrame with predictions and confidence scores
        """
        results = []

        for text in texts:
            # Tokenize
            encoding = self.tokenizer(
                text,
                max_length=self.max_length,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )

            input_ids = encoding['input_ids'].to(self.device)
            attention_mask = encoding['attention_mask'].to(self.device)

            # Predict
            with torch.no_grad():
                preds = self.model.predict(input_ids, attention_mask, return_confidence=True)

            # Decode predictions
            segment_idx = preds['segment'].item()
            lever_idx = preds['lever'].item()
            type_idx = preds['type'].item()

            segment = self.segment_encoder.inverse_transform([segment_idx])[0]
            lever = self.lever_encoder.inverse_transform([lever_idx])[0]
            type_pred = self.type_encoder.inverse_transform([type_idx])[0]

            # Get confidence scores
            segment_conf = preds['segment_confidence'].item()
            lever_conf = preds['lever_confidence'].item()
            type_conf = preds['type_confidence'].item()

            # Binary predictions
            inclusion = preds['inclusion'].item()
            envitarget = preds['envitarget'].item()
            diethealth = preds['diethealth'].item()

            inclusion_conf = preds['inclusion_confidence'].item()
            envitarget_conf = preds['envitarget_confidence'].item()
            diethealth_conf = preds['diethealth_confidence'].item()

            # Overall confidence (minimum across tasks)
            overall_conf = min(segment_conf, lever_conf, type_conf)

            # Flag for manual review
            needs_review = overall_conf < self.confidence_threshold

            results.append({
                'text': text[:100] + '...' if len(text) > 100 else text,
                'segment': segment,
                'lever': lever,
                'type': type_pred,
                'inclusion': inclusion,
                'envitarget': envitarget,
                'diethealth': diethealth,
                'segment_confidence': segment_conf,
                'lever_confidence': lever_conf,
                'type_confidence': type_conf,
                'inclusion_confidence': inclusion_conf,
                'envitarget_confidence': envitarget_conf,
                'diethealth_confidence': diethealth_conf,
                'overall_confidence': overall_conf,
                'needs_review': needs_review
            })

        return pd.DataFrame(results)

    def predict_dataframe(self, df: pd.DataFrame, text_column: str = 'policydecision_details') -> pd.DataFrame:
        """
        Make predictions for a DataFrame of policies.

        Args:
            df: DataFrame with policy data
            text_column: Name of column containing policy text

        Returns:
            Original DataFrame with added prediction columns
        """
        texts = df[text_column].fillna('').tolist()
        predictions = self.predict(texts)

        # Add predictions to original dataframe
        result_df = df.copy()
        for col in predictions.columns:
            if col != 'text':
                result_df[f'pred_{col}'] = predictions[col].values

        return result_df


def main():
    parser = argparse.ArgumentParser(description='Make predictions with trained FSPD model')
    parser.add_argument('--model_path', type=str, required=True, help='Path to model checkpoint')
    parser.add_argument('--input', type=str, required=True, help='Input CSV file')
    parser.add_argument('--output', type=str, required=True, help='Output CSV file')
    parser.add_argument('--text_column', type=str, default='policydecision_details', help='Text column name')
    parser.add_argument('--device', type=str, default=None, help='Device (cuda/cpu)')
    args = parser.parse_args()

    # Load predictor
    predictor = FSPDPredictor(args.model_path, args.device)

    # Load data
    print(f"Loading data from {args.input}")
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} policies")

    # Make predictions
    print("Making predictions...")
    results = predictor.predict_dataframe(df, args.text_column)

    # Save results
    results.to_csv(args.output, index=False)
    print(f"Predictions saved to {args.output}")

    # Print summary
    needs_review = results['pred_needs_review'].sum()
    print(f"\nSummary:")
    print(f"  Total policies: {len(results)}")
    print(f"  Flagged for review: {needs_review} ({needs_review/len(results)*100:.1f}%)")
    print(f"  Mean overall confidence: {results['pred_overall_confidence'].mean():.3f}")


if __name__ == '__main__':
    main()
