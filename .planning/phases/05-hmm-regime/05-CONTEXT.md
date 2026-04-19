# Phase 5: HMM Probabilistic Regime Detector - Context

**Gathered:** 2026-04-19
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Build 4-state Hidden Markov Model for market regime classification. Outputs continuous probability vectors — not binary labels — for adaptive signal family weighting.
</domain>

<decisions>
## Implementation Decisions

### Feature Preprocessing
- **D-01:** Pre-smoothed inputs. Apply a fast EMA (e.g., 5 or 9 period) to the raw features (returns, volatility, volume) before feeding them to the HMM to ensure smooth probability shifts and prevent rapid flip-flopping.

### Cross-Asset Data Alignment
- **D-02:** Forward-fill last known value for missing cross-asset data (VIX, bond yields, DXY). This handles asynchronous market hours and prevents lookahead bias in the feature set.

### Retraining Pipeline
- **D-03:** Offline scheduled job. The rolling 252-day window will be retrained weekly by a background offline process that drops a new model file for the engine to hot-load. This prevents latency spikes during live trading execution.

### Defining the Uncertainty Flag
- **D-04:** Probability entropy threshold. The uncertainty flag is triggered if the HMM probabilities are too evenly spread (high entropy) or if the top HMM state directly contradicts the absolute VIX threshold heuristic.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 5 success criteria
</canonical_refs>
