# Living FSPD Research Notes

## Core Contribution
Automated ML system to transform static FSPD into continuously updated database using transformer models for policy classification.

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
- Done: Project setup, EDA, model architecture (XLM-RoBERTa multi-task)
- Next: Model training and evaluation
- Then: Pipeline development, API, web interface, automation

---

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
