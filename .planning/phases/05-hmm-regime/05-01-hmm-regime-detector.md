---
gap_closure: false
---

# Plan 05-01: HMM Probabilistic Regime Detector

## Objective
Implement a 4-state Hidden Markov Model using `hmmlearn` to classify market regimes as continuous probability vectors, along with cross-asset alignment and a weekly offline retraining pipeline.

## Tasks

- [ ] **1. Define Data Models**
  - Create `src/algoforge/regime/models.py`.
  - Define `RegimeState` Enum (TREND_UP, TREND_DOWN, MEAN_REVERT, CRISIS).
  - Define `RegimeProbabilities` Pydantic model storing the 4-state probability vector and the boolean `uncertainty_flag`.

- [ ] **2. Implement Feature Preprocessor**
  - Create `src/algoforge/regime/features.py`.
  - Implement `build_features` to compute returns, realized volatility, volume ratio, ATR percentile, and cross-asset correlations (VIX, Yields, DXY).
  - Implement `forward_fill_cross_asset` to correctly align cross-asset data without lookahead bias.
  - Implement `smooth_features` using a fast EMA (e.g., period=5) to ensure smooth probability shifts.

- [ ] **3. Implement the Offline Retraining Pipeline**
  - Create `src/algoforge/regime/trainer.py`.
  - Implement `HMMTrainer` class using `hmmlearn.hmm.GaussianHMM` (n_components=4, covariance_type='diag').
  - Ensure data is scaled using `StandardScaler` prior to training.
  - Serialize the trained model to disk (e.g., `.pkl` or `.joblib`).
  - Create a CLI entrypoint or script to run this weekly over a rolling 252-day window.

- [ ] **4. Implement the Runtime Inference Engine**
  - Create `src/algoforge/regime/engine.py`.
  - Implement `RegimeEngine` which loads the pre-trained HMM model from disk.
  - Implement `compute` which takes the latest OHLCV and preprocessed features, scales them using the saved scaler, and calls `hmm.predict_proba()` to get the probability vector.
  - Implement the `uncertainty_flag` calculation (using probability entropy $> 1.2$ or conflicts with a VIX threshold $> 30$).

- [ ] **5. Testing & Verification**
  - Create `tests/unit/test_regime_engine.py`.
  - Mock `hmmlearn` outputs to verify that the `RegimeEngine` correctly maps probabilities to the `RegimeProbabilities` model.
  - Test the entropy calculation and uncertainty flag logic.
  - Verify that the `smooth_features` function correctly applies the EMA and `forward_fill_cross_asset` correctly propagates the last known value.
