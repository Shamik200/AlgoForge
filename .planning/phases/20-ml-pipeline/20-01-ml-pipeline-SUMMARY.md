# Plan 20-01: ML Pipeline

## Outcome
Implemented an HFT-grade ML enhancement layer with 44-feature engineering, ATR-adaptive label generation, purged walk-forward cross-validation (López de Prado), LightGBM wrappers with sklearn fallback, and a two-layer stacking ensemble (classifier + regressor → logistic meta-model).

## Self-Check: PASSED
- [x] All tasks executed
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/ml/features.py
- src/algoforge/ml/labels.py
- src/algoforge/ml/validation.py
- src/algoforge/ml/models.py
- src/algoforge/ml/ensemble.py
- src/algoforge/ml/pipeline.py
- src/algoforge/ml/__init__.py
- tests/unit/test_ml.py

## Technical Notes
- Feature engineering produces 44 features across 7 categories. This is intentionally the heaviest component — features matter more than model choice in quant finance.
- The purge gap in walk-forward CV equals the forward return horizon, preventing label leakage — the gold standard from López de Prado's methodology.
- LightGBM is preferred but the system gracefully falls back to sklearn's GradientBoosting when LightGBM isn't installed.
- The stacking ensemble uses Layer 1 outputs (3 class probabilities + 1 return prediction = 4 meta-features) as input to a logistic regression meta-model.
