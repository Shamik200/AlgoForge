# Phase 11: Signal Combination Framework - Research

## Context
Building the core edge of the trading system. The Combination Engine ingests signals from the Momentum, Mean Reversion, Breakout, and Structural families. It normalizes their raw scores, evaluates their pairwise correlation to prevent overexposure to redundant signals, weights them adaptively using a Softmax function on rolling Sharpe ratios, and produces a single Master Composite Signal bounded by `[-1.0, 1.0]`.

## Technical Findings

1. **Signal Z-Score Normalization:**
   - Raw scores from different signal families have different ranges and distributions.
   - We must maintain a rolling queue of the last 100 scores for each signal family.
   - `z_score = (current_score - rolling_mean) / rolling_std`.
   - The z-score is then compressed/clipped to `[-1.0, 1.0]` via `tanh(z_score / 2)` or strict clipping. Given we want a clean conviction scale, clipping to `[-1.0, 1.0]` after dividing by `3` (since 99% of z-scores fall between -3 and 3) is effective: `clipped_score = clip(z_score / 3.0, -1.0, 1.0)`.

2. **Rolling Sharpe Calculation:**
   - Each signal family needs its historical performance tracked to calculate its weight.
   - We will simulate or track the daily/trade PnL generated *specifically* by that signal family.
   - `Sharpe = Mean(Returns) / StdDev(Returns) * sqrt(252)` (or equivalent period scaler).
   - If a signal family has no trades or < N trades, it defaults to a neutral Sharpe (e.g., 0.0).

3. **Adaptive Softmax Weighting:**
   - Let `S` be the list of Sharpe ratios for families `[Momentum, Reversion, Breakout, Structural]`.
   - `Weights = Softmax(S) = exp(S_i) / sum(exp(S))`.
   - This ensures all weights sum to `1.0`. A negative Sharpe results in a fractional exp(), gracefully minimizing its weight without breaking the math.

4. **Decorrelation Matrix Tie-Breaker:**
   - We must calculate the pairwise Pearson correlation of the recent normalized scores (e.g. over the last 30 periods).
   - If `Correlation(Family_A, Family_B) > 0.7`:
     - Compare `Sharpe(Family_A)` and `Sharpe(Family_B)`.
     - Set the weight of the loser to `0.0` (exclude it from the final composition).
   - After culling redundant signals, re-run the Softmax weighting on the remaining active families so their weights sum to 1.0.

5. **Composite Calculation:**
   - `Composite Signal = sum(normalized_score_i * weight_i)`.
   - The result is guaranteed to be in `[-1.0, 1.0]` because the individual normalized scores are bounded, and the weights sum to 1.0.

## Implementation Path
- Create `src/algoforge/combination/`
- Implement `normalization.py` (Rolling window queues, z-score, clipping).
- Implement `weighting.py` (Sharpe trackers, Softmax calculation).
- Implement `correlation.py` (Pairwise signal correlation, culling logic).
- Implement `engine.py` (`CombinationEngine` orchestrator).
- Unit tests focusing on softmax math, tie-breaker culling, and z-score bounds.
