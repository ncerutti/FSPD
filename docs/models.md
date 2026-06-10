# OpenFPD model hosting and inference

## Where the models live

All trained model artifacts are hosted in a private Hugging Face Hub model repo:

**`ncerutti/openfpd-classifier`** (https://huggingface.co/ncerutti/openfpd-classifier)

Contents:

| File | Description |
|---|---|
| `best_model_slim.pt` | Stage 1 checkpoint (1.1 GB): XLM-RoBERTa-base multi-task weights (`model_state_dict`), the three sklearn LabelEncoders (`segment_encoder`, `lever_encoder`, `type_encoder`), validation metrics and training config. No optimizer state (the full 3.3 GB `best_model.pt` stays on Kaggle and locally only). |
| `stage2_models/*.joblib` | Six XGBoost classifiers (`segment`, `lever`, `type`, `inclusion`, `envitarget`, `diethealth`), trained on Stage 1 CLS embeddings + 4 categorical features. |
| `stage2_models/label_encoders.joblib` | Fresh LabelEncoders for decoding the three multiclass Stage 2 outputs. |
| `cat_encoder.joblib` | OrdinalEncoder for the categorical features (`region_wb`, `income_group`, `db`, `country`), fitted on the seed-42 training split of `FSPD.csv`. Unseen/missing values map to -1 / "Unknown". |

## No local execution

Model code (torch.load, inference, embedding extraction, training) must NEVER
be run on the development laptop — it cannot handle it. All inference runs in
GitHub Actions or on Kaggle. Local operations are limited to plain file
uploads/downloads.

## How CI downloads the models

Store the Hugging Face token as the `HF_TOKEN` repository secret in GitHub
Actions. Then:

```yaml
- name: Download models
  env:
    HF_TOKEN: ${{ secrets.HF_TOKEN }}
  run: |
    pip install huggingface_hub
    python -c "from huggingface_hub import snapshot_download; \
               snapshot_download('ncerutti/openfpd-classifier', local_dir='models')"
```

(`snapshot_download` picks up `HF_TOKEN` from the environment automatically.)

## Running inference

`classify_new.py` (repo root) is the CPU inference entry point. It mirrors the
Stage 2 preprocessing exactly: text column `policydecision_details`, batched
768-dim CLS embeddings from `FSPDMultiTaskModel(return_hidden=True)`, then
ordinal-encoded categoricals appended before the XGBoost classifiers.

```bash
pip install torch transformers xgboost scikit-learn joblib pandas pyarrow
python classify_new.py \
    --model_dir models \
    --input data/new_policies.parquet \
    --output data/new_policies_classified.parquet
```

Input: parquet or CSV as produced by `src/pipeline/transform.py` (must contain
`policydecision_details`; `region_wb`, `income_group`, `db`, `country` are
used if present, otherwise encoded as "Unknown").

Output: input columns plus, per task, `pred_<task>` and `<task>_confidence`,
and a `needs_review` flag set when any task confidence is below 0.7 (or the
text is shorter than 10 characters). Confidences come from raw booster margins
(softmax/sigmoid), since the multiclass models were trained with
`multi:softmax` which has no usable `predict_proba`.

## Version notes

- Stage 2 joblibs were trained/saved with the Kaggle Python image (xgboost
  installed via pip at run time); use a recent xgboost (>= 2.x) in CI to
  unpickle them.
- The Stage 1 checkpoint embeds sklearn 1.8.0 LabelEncoders; any sklearn 1.x
  loads them.
- Loading the checkpoint requires `torch.load(..., weights_only=False)`
  because it contains sklearn objects; the file comes from our own private
  repo only.

## Verification

Verified remotely on 10 June 2026 (Kaggle CPU kernel `ncerutti/openfpd-verify`):
downloaded all artifacts from the HF repo, loaded the slim checkpoint, and ran
`classify_new.py` end-to-end on 3 synthetic samples plus 5 held-out test rows.
Results: 4/5 segment matches (consistent with test F1 0.865), exact lever and
type predictions on French and Spanish policies, all confidences plausible.
The Stage 2 models were recovered by re-running `src/models/stage2.py` on
Kaggle (kernel `ncerutti/fspd-stage2-rerun`, T4); metrics reproduce
`outputs/models/stage2_metrics.json` exactly (Segment F1 0.8648, Lever 0.6619,
Type 0.9038, Inclusion 0.7140, EnviTarget 0.8239, DietHealth 0.7376).

Note: the encoders were pickled with sklearn 1.8.0; loading under 1.6.1 emits
an InconsistentVersionWarning but works. Pin sklearn>=1.8 in CI to silence it.
