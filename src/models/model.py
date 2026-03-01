"""
Multi-task transformer model for FSPD classification.
"""
import torch
import torch.nn as nn
from transformers import AutoModel, AutoConfig
from typing import Dict, Optional


class FSPDMultiTaskModel(nn.Module):
    """
    Multi-task classification model for food system policies.

    Predicts:
    - Segment (multi-class classification)
    - Lever (multi-class classification)
    - Type (multi-class classification)
    - Inclusion (binary classification)
    - Envitarget (binary classification)
    - Diethealth (binary classification)
    """

    def __init__(
        self,
        model_name: str,
        num_segments: int,
        num_levers: int,
        num_types: int,
        dropout_rate: float = 0.1
    ):
        """
        Args:
            model_name: Name of pretrained transformer model
            num_segments: Number of segment classes
            num_levers: Number of lever classes
            num_types: Number of type classes
            dropout_rate: Dropout probability
        """
        super().__init__()

        # Load pretrained transformer
        config = AutoConfig.from_pretrained(model_name)
        self.transformer = AutoModel.from_pretrained(model_name, config=config)
        hidden_size = config.hidden_size

        # Dropout
        self.dropout = nn.Dropout(dropout_rate)

        # Classification heads
        # Multi-class tasks
        self.segment_classifier = nn.Linear(hidden_size, num_segments)
        self.lever_classifier = nn.Linear(hidden_size, num_levers)
        self.type_classifier = nn.Linear(hidden_size, num_types)

        # Binary classification tasks
        self.inclusion_classifier = nn.Linear(hidden_size, 1)
        self.envitarget_classifier = nn.Linear(hidden_size, 1)
        self.diethealth_classifier = nn.Linear(hidden_size, 1)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        return_hidden: bool = False
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass.

        Args:
            input_ids: Token IDs [batch_size, seq_len]
            attention_mask: Attention mask [batch_size, seq_len]
            return_hidden: Whether to return hidden states

        Returns:
            Dictionary with logits for each task
        """
        # Get transformer outputs
        outputs = self.transformer(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        # Use [CLS] token representation (first token)
        pooled_output = outputs.last_hidden_state[:, 0, :]  # [batch_size, hidden_size]
        pooled_output = self.dropout(pooled_output)

        # Compute logits for each task
        segment_logits = self.segment_classifier(pooled_output)
        lever_logits = self.lever_classifier(pooled_output)
        type_logits = self.type_classifier(pooled_output)
        inclusion_logits = self.inclusion_classifier(pooled_output).squeeze(-1)
        envitarget_logits = self.envitarget_classifier(pooled_output).squeeze(-1)
        diethealth_logits = self.diethealth_classifier(pooled_output).squeeze(-1)

        result = {
            'segment_logits': segment_logits,
            'lever_logits': lever_logits,
            'type_logits': type_logits,
            'inclusion_logits': inclusion_logits,
            'envitarget_logits': envitarget_logits,
            'diethealth_logits': diethealth_logits,
        }

        if return_hidden:
            result['hidden_states'] = pooled_output

        return result

    def predict(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        return_confidence: bool = True
    ) -> Dict[str, torch.Tensor]:
        """
        Make predictions with confidence scores.

        Args:
            input_ids: Token IDs
            attention_mask: Attention mask
            return_confidence: Whether to return confidence scores

        Returns:
            Dictionary with predictions and optionally confidence scores
        """
        self.eval()
        with torch.no_grad():
            outputs = self.forward(input_ids, attention_mask)

            # Multi-class predictions (argmax)
            segment_probs = torch.softmax(outputs['segment_logits'], dim=-1)
            lever_probs = torch.softmax(outputs['lever_logits'], dim=-1)
            type_probs = torch.softmax(outputs['type_logits'], dim=-1)

            segment_preds = torch.argmax(segment_probs, dim=-1)
            lever_preds = torch.argmax(lever_probs, dim=-1)
            type_preds = torch.argmax(type_probs, dim=-1)

            # Binary predictions (sigmoid)
            inclusion_probs = torch.sigmoid(outputs['inclusion_logits'])
            envitarget_probs = torch.sigmoid(outputs['envitarget_logits'])
            diethealth_probs = torch.sigmoid(outputs['diethealth_logits'])

            inclusion_preds = (inclusion_probs > 0.5).long()
            envitarget_preds = (envitarget_probs > 0.5).long()
            diethealth_preds = (diethealth_probs > 0.5).long()

            result = {
                'segment': segment_preds,
                'lever': lever_preds,
                'type': type_preds,
                'inclusion': inclusion_preds,
                'envitarget': envitarget_preds,
                'diethealth': diethealth_preds,
            }

            if return_confidence:
                # Confidence = max probability for multi-class, probability for binary
                result['segment_confidence'] = torch.max(segment_probs, dim=-1)[0]
                result['lever_confidence'] = torch.max(lever_probs, dim=-1)[0]
                result['type_confidence'] = torch.max(type_probs, dim=-1)[0]
                result['inclusion_confidence'] = torch.where(
                    inclusion_preds == 1,
                    inclusion_probs,
                    1 - inclusion_probs
                )
                result['envitarget_confidence'] = torch.where(
                    envitarget_preds == 1,
                    envitarget_probs,
                    1 - envitarget_probs
                )
                result['diethealth_confidence'] = torch.where(
                    diethealth_preds == 1,
                    diethealth_probs,
                    1 - diethealth_probs
                )

            return result


class MultiTaskLoss(nn.Module):
    """
    Combined loss for multi-task learning.
    """

    def __init__(
        self,
        segment_weight: float = 1.0,
        lever_weight: float = 1.0,
        type_weight: float = 1.0,
        inclusion_weight: float = 0.5,
        envitarget_weight: float = 0.5,
        diethealth_weight: float = 0.5,
        segment_class_weights: Optional[torch.Tensor] = None,
        lever_class_weights: Optional[torch.Tensor] = None,
        type_class_weights: Optional[torch.Tensor] = None,
    ):
        """
        Args:
            *_weight: Weight for each task in the combined loss
            *_class_weights: Class weights for handling imbalance
        """
        super().__init__()

        self.segment_weight = segment_weight
        self.lever_weight = lever_weight
        self.type_weight = type_weight
        self.inclusion_weight = inclusion_weight
        self.envitarget_weight = envitarget_weight
        self.diethealth_weight = diethealth_weight

        # Loss functions
        self.segment_loss_fn = nn.CrossEntropyLoss(weight=segment_class_weights)
        self.lever_loss_fn = nn.CrossEntropyLoss(weight=lever_class_weights)
        self.type_loss_fn = nn.CrossEntropyLoss(weight=type_class_weights)
        self.binary_loss_fn = nn.BCEWithLogitsLoss()

    def forward(
        self,
        outputs: Dict[str, torch.Tensor],
        labels: Dict[str, torch.Tensor]
    ) -> tuple[torch.Tensor, Dict[str, float]]:
        """
        Calculate combined loss.

        Args:
            outputs: Model outputs (logits)
            labels: Ground truth labels

        Returns:
            Tuple of (total_loss, individual_losses_dict)
        """
        # Multi-class losses
        segment_loss = self.segment_loss_fn(
            outputs['segment_logits'],
            labels['segment_label']
        )
        lever_loss = self.lever_loss_fn(
            outputs['lever_logits'],
            labels['lever_label']
        )
        type_loss = self.type_loss_fn(
            outputs['type_logits'],
            labels['type_label']
        )

        # Binary losses
        inclusion_loss = self.binary_loss_fn(
            outputs['inclusion_logits'],
            labels['inclusion_label']
        )
        envitarget_loss = self.binary_loss_fn(
            outputs['envitarget_logits'],
            labels['envitarget_label']
        )
        diethealth_loss = self.binary_loss_fn(
            outputs['diethealth_logits'],
            labels['diethealth_label']
        )

        # Weighted combination
        total_loss = (
            self.segment_weight * segment_loss +
            self.lever_weight * lever_loss +
            self.type_weight * type_loss +
            self.inclusion_weight * inclusion_loss +
            self.envitarget_weight * envitarget_loss +
            self.diethealth_weight * diethealth_loss
        )

        # Individual losses for logging
        individual_losses = {
            'segment': segment_loss.item(),
            'lever': lever_loss.item(),
            'type': type_loss.item(),
            'inclusion': inclusion_loss.item(),
            'envitarget': envitarget_loss.item(),
            'diethealth': diethealth_loss.item(),
        }

        return total_loss, individual_losses
