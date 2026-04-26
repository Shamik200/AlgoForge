# Phase 20: ML Pipeline - Research

## Context
This is the ML enhancement layer that real quant funds use. The key insight from industry: **features matter more than model choice**. A LightGBM with 50 well-engineered features beats a Transformer with raw prices every time on tabular financial data.

## Technical Findings

1. **Feature Engineering (The Alpha Generator):**
   - **Signal Features (12):** 6 family scores + 6 rolling 20-bar stds of those scores
   - **Lagged Signal Features (12):** 6 family scores lagged by 5 bars + lagged by 10 bars
   - **Regime Features (4):** HMM bull/bear/sideways probabilities + bars-since-transition
   - **Microstructure Features (4):** VWAP deviation, volume imbalance, OBV score, volume ratio (current / 20-bar avg)
   - **Price Action Features (8):** Returns (1/5/10/20 bar), volatility (5/20 bar), ATR ratio, momentum (close - EMA20)
   - **Cross-Asset Features (4):** Rolling 20-bar correlation with benchmark, relative strength vs sector, spread z-score
   - **Time Features (6):** Hour sin/cos, day-of-week sin/cos, month sin/cos
   - **Total: ~50 features**

2. **Label Engineering:**
   - Target: Forward N-bar return (e.g., N=5)
   - Classification: Return > +threshold → LONG (+1), Return < -threshold → SHORT (-1), else FLAT (0)
   - Threshold: 0.5× ATR to filter noise

3. **LightGBM Configuration (HFT-Optimized):**
   - `objective`: `multiclass` (3 classes)
   - `num_leaves`: 31 (prevent overfitting)
   - `min_child_samples`: 100 (HFT-grade: require statistical significance)
   - `feature_fraction`: 0.7 (random feature selection per tree)
   - `bagging_fraction`: 0.7 (random sample selection per tree)
   - `lambda_l1`: 0.1, `lambda_l2`: 0.1 (regularization)
   - `n_estimators`: 500, `early_stopping_rounds`: 50

4. **Purged Walk-Forward Cross-Validation:**
   - Purge gap = forward return horizon (5 bars)
   - Embargo: Additional 1-bar buffer after test set before next train fold
   - This is the gold standard from Marcos López de Prado's "Advances in Financial Machine Learning"

5. **Two-Layer Stacking Ensemble:**
   - Layer 1 Model A: LightGBM Classifier → P(long), P(short), P(flat)
   - Layer 1 Model B: LightGBM Regressor → predicted return magnitude
   - Layer 2: Logistic Regression on [P(long), P(short), P(flat), pred_return] → final signal [-1, +1]

## Implementation Path
- Create `src/algoforge/ml/features.py` — FeatureBuilder
- Create `src/algoforge/ml/labels.py` — Label engineering with ATR threshold
- Create `src/algoforge/ml/models.py` — LightGBM wrapper with HFT config
- Create `src/algoforge/ml/ensemble.py` — Two-layer stacking
- Create `src/algoforge/ml/validation.py` — Purged walk-forward CV
- Create `src/algoforge/ml/pipeline.py` — MLPipeline orchestrator
- Create `tests/unit/test_ml.py`
