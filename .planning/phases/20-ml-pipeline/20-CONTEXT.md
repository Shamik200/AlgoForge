# Phase 20: ML/DL/RL Pipeline - Context

**Gathered:** 2026-04-26
**Status:** Completed (HFT-grade architecture selected)

<domain>
## Phase Boundary

Build a production-grade ML enhancement layer that real quantitative trading firms use. Focus on feature engineering depth, gradient-boosted trees (the workhorse of quant finance), and stacking ensembles. The ML layer enhances — not replaces — the rule-based signal families.
</domain>

<decisions>
## Implementation Decisions

### Feature Engineering Architecture
- **D-01:** Multi-Source Feature Builder. A `FeatureBuilder` class that constructs 5 feature categories from the current system state:
  1. **Signal Features:** All 6 signal family scores + their rolling means/stds
  2. **Regime Features:** HMM state probabilities, regime transition recency
  3. **Microstructure Features:** VWAP deviation, volume imbalance, OBV divergence
  4. **Cross-Asset Features:** Rolling correlations between instruments, relative strength
  5. **Time Features:** Hour-of-day (cyclical sin/cos), day-of-week, month, days-to-expiry
  - Total: ~50+ engineered features per bar. This is the real alpha — features matter more than model choice.

### Model Selection (HFT-Grade)
- **D-02:** LightGBM as Primary Classifier. LightGBM (not XGBoost) is what most modern quant funds use. It's faster, handles categorical features natively, and has better regularization. The model predicts a 3-class target: {-1: SHORT, 0: FLAT, +1: LONG} using the next N-bar forward return as the label.
- **D-03:** Purged Walk-Forward Validation. Standard k-fold is ILLEGAL in time series — it leaks future data. We use purged walk-forward: train on [0, T], PURGE gap of G bars (to prevent label leakage), test on [T+G, T+G+test_size]. The purge gap equals the forward-return horizon.

### Ensemble Architecture
- **D-04:** Two-Layer Stacking. Layer 1: LightGBM classifier + LightGBM regressor (predicting return magnitude). Layer 2: A logistic regression meta-model that combines Layer 1 outputs. This is the standard "stacking" approach used by Kaggle grandmasters and quant firms alike.

### Model Interface Contract
- **D-05:** All ML models implement `predict(features: np.ndarray) -> float` returning a score in [-1.0, +1.0]. This matches the signal family contract and plugs directly into the Combination Engine as a 7th "signal family."

### Feature Importance
- **D-06:** Built-in LightGBM feature importance (gain-based). SHAP is deferred to a future iteration — gain importance is sufficient for initial feature selection and is 100x faster.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 20 success criteria
- `.planning/phases/15-backtesting/15-CONTEXT.md` — Walk-forward validation
- `.planning/phases/11-signal-combination/11-CONTEXT.md` — Signal output contract
</canonical_refs>
