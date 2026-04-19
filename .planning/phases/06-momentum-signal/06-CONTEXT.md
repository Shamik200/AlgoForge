# Phase 6: Signal Family 1 — Momentum - Context

**Gathered:** 2026-04-19
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement the Momentum signal family (cross-sectional, time-series, dual momentum) with intraday VWAP adaptation, KAMA/ROC confirmations, and a regime-aligned composite z-score output.
</domain>

<decisions>
## Implementation Decisions

### Cross-Sectional Architecture
- **D-01:** Emit raw scores. The individual momentum signal instance for a given asset will compute its own raw momentum scores (e.g., 1M/3M/6M/12M returns). A central coordinator (to be built in Phase 11: Signal Combination) will handle the cross-asset ranking to derive the cross-sectional momentum percentiles. This prevents the signal from needing a global lock on all asset states.

### Intraday Adaptation Logic
- **D-02:** Rely on `IndicatorEngine` snapshots. The signal will not compute 1H/4H indicators from raw 1min data. Instead, it expects the `IndicatorEngine` to provide multi-timeframe snapshots. However, VWAP will be computed dynamically within the signal or via the engine's lower-level tick/1m data since it requires high-frequency intra-bar volume weighting.

### Composite Z-Score Normalization
- **D-03:** Equal-weighting with post-regime boost. The individual momentum sub-signals (time-series, cross-sectional, intraday) will be normalized to [-1, 1] and equal-weighted to form a base composite score. If the `RegimeEngine` (Phase 5) indicates `TREND_UP` or `TREND_DOWN`, a 1.3x multiplier is applied, hard-clipping the final output strictly to the [-1.0, 1.0] range.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 6 success criteria
</canonical_refs>
