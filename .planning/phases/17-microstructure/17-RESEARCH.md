# Phase 17: Signal Family 5 — Microstructure / Order Flow - Research

## Context
This signal family reads the internal dynamics of price action: where volume clusters, whether informed traders are stepping in (VPIN), and when price deviates from fair value (VWAP). It must gracefully degrade from L2 tick data down to OHLCV candles and self-disable on non-intraday timeframes.

## Technical Findings

1. **VWAP (Volume Weighted Average Price):**
   - Formula: `VWAP = Σ(Price × Volume) / Σ(Volume)` — cumulative, resets each session.
   - Deviation signal: When `(Price - VWAP) / VWAP_StdDev > threshold`, the price is extended.
   - Trade: Mean-reversion back to VWAP when deviation exceeds ±1.5σ.

2. **Volume Imbalance:**
   - On L2 data: Compare bid volume vs ask volume at current price level.
   - On OHLCV fallback: Approximate using `(Close - Low) / (High - Low)` as a buying pressure proxy (similar to Chaikin Money Flow).
   - Signal fires when imbalance ratio exceeds 0.65 (configurable).

3. **VPIN (Volume-Synchronized Probability of Informed Trading):**
   - Requires tick-level trade data to classify trades as buy or sell initiated.
   - Groups trades into volume buckets (not time buckets). Each bucket sums buy and sell volume.
   - VPIN = `Σ|Vbuy - Vsell| / (n × V_bucket)` — higher values indicate toxic flow (informed traders present).
   - **L1 Fallback:** When tick data is unavailable, use OBV divergence as a proxy for informed flow.

4. **OBV Divergence (L1 Fallback):**
   - OBV accumulates volume positively on up-closes and negatively on down-closes.
   - Divergence: If price makes a new high but OBV does not → bearish divergence signal.
   - If price makes a new low but OBV does not → bullish divergence signal.

5. **Intraday Guard:**
   - The family checks `timeframe` from config. If >= "1d", `generate()` returns `is_valid=False`.

## Implementation Path
- Create `src/algoforge/signals/microstructure/vwap.py` — VWAPTracker + deviation signal.
- Create `src/algoforge/signals/microstructure/volume.py` — Volume imbalance + OBV divergence.
- Create `src/algoforge/signals/microstructure/family.py` — MicrostructureFamily orchestrator with mode selection and timeframe guard.
- Create `src/algoforge/signals/microstructure/__init__.py`.
- Create `tests/unit/test_microstructure.py`.
