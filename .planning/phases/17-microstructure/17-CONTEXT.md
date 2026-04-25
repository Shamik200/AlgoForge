# Phase 17: Signal Family 5 — Microstructure / Order Flow - Context

**Gathered:** 2026-04-25
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement a new signal family focused on market microstructure: VWAP deviation trading, volume imbalance detection, and VPIN (Volume-Synchronized Probability of Informed Trading). The family gracefully degrades when Level 2 data is unavailable and self-disables on non-intraday timeframes.
</domain>

<decisions>
## Implementation Decisions

### VWAP Calculation Architecture
- **D-01:** VWAPTracker Class. A dedicated `VWAPTracker` class accumulates `(price × volume)` and `volume` throughout the intraday session, resetting at the configured session open time. It exposes a `deviation_pct` property. Signals fire when the deviation exceeds ±1.5σ (configurable), trading reversion back toward VWAP.

### Graceful Degradation Strategy (No L2 Data)
- **D-02:** Automatic Mode Selection. The signal family checks data availability at initialization. If tick-level or L2 order book data is present, it runs in "full mode" using VPIN and volume imbalance. If only OHLCV candles are available, it falls back to "L1 mode" using OBV (On-Balance Volume) divergence and Volume-at-Price clustering as proxy indicators. Mode selection is logged but requires no user intervention.

### Intraday-Only Activation Guard
- **D-03:** Timeframe Self-Disabling. The signal family inspects the candle timeframe from the data feed configuration at init time. If the timeframe resolution is >= 1D (daily, weekly, monthly), the family's `generate()` method immediately returns `is_valid=False` on every invocation, gracefully silencing itself without external logic.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 17 success criteria
- `.planning/phases/11-signal-combination/11-CONTEXT.md` — Signal family output contract
</canonical_refs>
