# Phase 11: Signal Combination & Conviction Framework - Context

**Gathered:** 2026-04-22
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement the Signal Combination & Conviction Framework. This engine sits above the individual signal families (Momentum, Mean Reversion, Breakout, Structural). It normalizes their raw scores, evaluates their pairwise correlation to prevent overexposure to redundant signals, weights them adaptively based on rolling Sharpe ratios, and produces a single Master Composite Signal `[-1.0, 1.0]`.
</domain>

<decisions>
## Implementation Decisions

### Signal Z-Score Normalization Window
- **D-01:** 100-Period Rolling Window. To convert raw family scores into standard z-scores, the combination engine will maintain a rolling 100-period queue of historical scores for each family. This ensures the normalization adapts to recent market volatility and structural shifts.

### Adaptive Weighting Function
- **D-02:** Softmax Weighting. The engine will convert the rolling Sharpe ratios of the signal families into proportional weights using a Softmax function. This guarantees that weights sum exactly to 1.0, handles varying score ranges gracefully, and heavily penalizes negative Sharpe ratios.

### Decorrelation Tie-Breaker Routing
- **D-03:** Softmax Recalculation. If two signal families exceed a rolling correlation threshold of `0.7`, the family with the lower Sharpe ratio will be dropped (weight set to 0.0). To maintain a valid composite weighting, the Softmax function will simply be re-calculated over the remaining active families to proportionally distribute the dropped weight to the survivors.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 11 success criteria
</canonical_refs>
