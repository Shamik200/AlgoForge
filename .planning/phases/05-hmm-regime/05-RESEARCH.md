# Phase 5: HMM Probabilistic Regime Detector - Research

## Context
Building a 4-state Hidden Markov Model using `hmmlearn` to classify market regimes into continuous probability vectors rather than binary labels.

## Technical Findings

1. **hmmlearn implementation:**
   - Use `hmmlearn.hmm.GaussianHMM` for continuous feature spaces (returns, vol, etc.).
   - Number of components `n_components=4`.
   - Covariance type should typically be `'full'` or `'diag'` depending on feature correlation. Since features include returns, vol, volume ratio, cross-asset correlations, and ATR percentile, `'diag'` is safer against overfitting, but `'full'` captures interactions better. Given rolling 252-day window (small N relative to features), `'diag'` is heavily recommended.

2. **Feature Preprocessing (D-01):**
   - EMA smoothing: Applying a 5-9 period EMA *before* fitting the HMM reduces noise. However, one must ensure this doesn't introduce excessive lag.
   - Standardization: `StandardScaler` is absolutely required before feeding data to `GaussianHMM` to ensure volatility doesn't dominate returns purely due to scale differences.

3. **Cross-Asset Data Alignment (D-02):**
   - Forward-fill (`ffill` in pandas) is the correct approach to prevent lookahead bias when merging daily DXY/Yields/VIX with higher-frequency target asset data.

4. **Retraining Pipeline (D-03):**
   - Weekly offline retraining means the model parameters (transition matrix, means, covariances) are fixed during the week. 
   - We must serialize the trained model using `joblib` or `pickle` and load it at runtime.

5. **Uncertainty Flag (D-04):**
   - Entropy calculation: $H(P) = -\sum P_i \log(P_i)$. Max entropy for 4 states is $\log(4) \approx 1.38$. A threshold of e.g. 1.2 can flag "uncertainty".
   - VIX Conflict: E.g., if HMM says P(Trending-Up) > 0.8 but VIX > 30 (extreme fear), trigger the flag.

## Implementation Path
- Create data models for Regime vectors.
- Build the HMM training pipeline offline script.
- Build the runtime HMM inference engine (which loads the pickled model).
- Integrate cross-asset fetching/forward-filling into the feature builder.
