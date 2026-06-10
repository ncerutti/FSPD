# OpenFPD Research Notes

## Core Contribution
OpenFPD (Open Food Policy Database): a harmonized, continuously updated database of food policies from FAPDA, GIFNA, and PINE, with transformer-based ML classification and community contribution.

## Key Points

### Innovation
- First automated food policy classification system
- Transformer-based multi-task learning (segment, lever, type, 3 objectives)
- Full pipeline: ingestion → classification → dissemination

### Challenges
- Class imbalance in policy categories (~135 levers, 10 segments)
- Schema mapping from heterogeneous sources (FAPDA, PINE, GIfNA)
- Confidence calibration for automated vs manual review
- Deduplication across sources

### Metrics
- Target: >85% accuracy on main categories
- Report per-class F1, confusion matrices
- Include confidence scores with predictions
- Validate sample with domain experts

### Architecture
- Monthly GitHub Actions updates
- Transformer models (BERT/RoBERTa fine-tuned)
- FastAPI backend, static frontend
- PostgreSQL/SQLite storage
- Open source: GitHub + Mendeley Data

### Paper Structure
1. Problem: Policy databases quickly outdated
2. Method: Transformer classification + automated pipeline
3. Results: Model performance, system validation
4. Impact: Accessible, up-to-date resource for research and policy

## Open Questions
- Confidence thresholds for flagging?
- Handle multi-segment policies?
- User-submitted corrections?
- Retraining frequency?

## Timeline
- Done: Project setup, EDA, model architecture, Stage 1 training, Stage 2 training
- Next: Pipeline development (ingestion, schema mapping, deduplication, API, automation)
- Then: Web interface, Mendeley Data release, paper submission

---

## Results Summary (Stage 1 vs Stage 2)

| Task | S1 Acc | S1 F1 | S2 Acc | S2 F1 | ΔF1 |
|---|---|---|---|---|---|
| Segment | 83.3 | 83.9 | 86.5 | 86.5 | +2.6 |
| Lever | 63.6 | 63.7 | 66.0 | 66.2 | +2.5 |
| Type | 86.4 | 87.0 | 90.4 | 90.4 | +3.4 |
| Inclusion | 85.8 | 65.4 | 87.1 | 71.4 | +6.0 |
| EnviTarget | 95.9 | 82.8 | 95.7 | 82.4 | −0.4 |
| DietHealth | 84.3 | 70.9 | 84.9 | 73.8 | +2.8 |

Feature importance: ~99% embeddings across all tasks — categorical metadata (region, income group, db, country) contributes marginally, suggesting policy text already encodes geographic/institutional context.

## Log

**2025-12-27**: Project start. EDA findings:
- Dataset: 15,592 policies (not 42,810 - need to clarify discrepancy with paper)
- Sources: FAPDA (10,491), FAPDA_F (3,719 frameworks), Nourishing (784), PINE (598)
- Coverage: 195 countries, 11 segments, 113 levers, 9 types
- Text: Mean 603 chars, median 421 chars, range 3-7,234
- Class imbalance: Segment 23:1, Lever 246:1, Type 518:1
- Objectives: inclusion (23%), envitarget (20%), diethealth (35%)
- Multilingual data detected (Spanish, French, English)
- Missing data: 598 policies without descriptions, most missing year field
- Challenge: High imbalance on Lever classification may require hierarchical approach
