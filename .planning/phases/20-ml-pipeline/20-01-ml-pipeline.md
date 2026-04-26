---
gap_closure: false
---

# Plan 20-01: ML/DL/RL Pipeline

## Objective
Build a production-grade ML enhancement layer with HFT-quality feature engineering, LightGBM classification, purged walk-forward validation, and a two-layer stacking ensemble.

## Tasks

- [ ] **1. Feature Engineering**
  - Create `src/algoforge/ml/features.py`.
  - Implement `FeatureBuilder.build(signal_scores, regime_probs, price_data, time_info)`.
  - ~50 features across 7 categories.

- [ ] **2. Label Engineering**
  - Create `src/algoforge/ml/labels.py`.
  - Implement `generate_labels(prices, forward_bars, atr_threshold_mult)`.
  - 3-class target: LONG(+1), FLAT(0), SHORT(-1).

- [ ] **3. Purged Walk-Forward Validation**
  - Create `src/algoforge/ml/validation.py`.
  - Implement `purged_walk_forward_split(n_samples, train_size, test_size, purge_gap)`.

- [ ] **4. LightGBM Model Wrapper**
  - Create `src/algoforge/ml/models.py`.
  - Implement `GBMClassifier` with HFT-optimized hyperparameters.
  - Implement `GBMRegressor` for return magnitude prediction.

- [ ] **5. Two-Layer Stacking Ensemble**
  - Create `src/algoforge/ml/ensemble.py`.
  - Layer 1: GBMClassifier + GBMRegressor.
  - Layer 2: Logistic regression meta-model.
  - Output: signal score in [-1.0, +1.0].

- [ ] **6. Pipeline Orchestrator**
  - Create `src/algoforge/ml/pipeline.py`.
  - Implement `MLPipeline.train()` and `.predict()`.
  - Wire feature builder → models → ensemble.

- [ ] **7. Integration & Testing**
  - Create `src/algoforge/ml/__init__.py`.
  - Create `tests/unit/test_ml.py`.
  - Test feature generation, label engineering, purged CV splits, and ensemble output.
