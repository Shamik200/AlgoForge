# Phase 8: Signal Family 3 — Breakout / Volatility Expansion - Context

**Gathered:** 2026-04-19
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement the Breakout signal family, which capitalizes on volatility compression releases. Evaluates standard Volatility Squeezes (Bollinger Bands within Keltner Channels), volume-confirmed Donchian breakouts, and Opening Range Breakouts (ORB), with a robust pattern for detecting and reversing failed breakouts.
</domain>

<decisions>
## Implementation Decisions

### Breakout Failure Reversal
- **D-01:** Stateless Pattern Recognition. The signal evaluator will not hold internal memory ("state") across ticks. A failed breakout will be detected statelessly by comparing recent history (e.g., Previous Close > Donchian High AND Current Close < Donchian High + N-candle lookback). This ensures the pure functional nature of our signal generators remains intact. The actual order/position reversal state will be managed safely by the Portfolio Manager later.

### Keltner Channel Math
- **D-02:** EMA(20) and 1.5x ATR(14). For detecting the "Squeeze" (when Bollinger Bands contract inside Keltner Channels), we will standardize the Keltner Channel calculation. The centerline will be a 20-period EMA, and the upper/lower bands will be placed at +/- 1.5 * ATR(14). This pairs perfectly with our standard Bollinger Band parameters (20-period SMA, 2.0 StdDev).

### Opening Range Breakout (ORB) Architecture
- **D-03:** Split Architecture. Because ORB requires strict intraday time boundary logic (e.g., first 30 minutes of the session) while the Volatility Squeeze operates purely on bar sequence regardless of timeframe, we will separate them. We will create two distinct classes: `VolatilityBreakoutSignal` and `ORBSignal`. The overarching `SignalCombiner` will aggregate them.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 8 success criteria
</canonical_refs>
