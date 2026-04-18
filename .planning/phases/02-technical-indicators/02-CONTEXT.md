# Phase 2: Technical Indicator Engine - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement all 14 technical indicators (INDI-01 through INDI-14) with configurable parameters, computed efficiently across multiple timeframes. Each indicator must compute correctly against reference values, update incrementally as new candles arrive, and be cached to avoid redundant recalculation. The indicator engine must process 100 instruments × 6 timeframes within 1 second. This phase produces the computed indicator values that Phase 3 (S/R + Trendlines), Phase 4 (Regime Detection), and Phase 5+ (Strategies) consume.

</domain>

<decisions>
## Implementation Decisions

### Computation Library
- **D-01:** Pure NumPy implementations for all 14 indicators — no TA-Lib or pandas-ta dependency
- **D-02:** Zero external C library dependencies — avoids Windows compilation issues and keeps the stack pure Python + NumPy
- **D-03:** Each indicator implemented as a standalone function that takes NumPy arrays (closes, highs, lows, volumes) and returns NumPy arrays
- **D-04:** Reference verification against TA-Lib values in tests (pip install TA-Lib only in test extras, not runtime)

### Indicator Output Model
- **D-05:** Single unified `IndicatorResult` Pydantic model for all 14 indicators — `name`, `values` (dict[str, list[float]]), `timestamp`, `params` (dict), `metadata`
- **D-06:** Multi-value indicators (MACD, Bollinger, Ichimoku) return multiple named series in the `values` dict (e.g., MACD → `{"macd": [...], "signal": [...], "histogram": [...]}`)
- **D-07:** Single-value indicators (EMA, RSI, ATR) return one series (e.g., `{"ema_21": [...]}`)
- **D-08:** `IndicatorResult` includes the indicator parameters used for computation (for audit/reproducibility)

### Caching & Update Strategy
- **D-09:** Incremental update mode — maintain rolling buffers per indicator, recompute only from the last N candles needed by the indicator's lookback window
- **D-10:** Each indicator declares its `lookback_period` (e.g., EMA-200 needs 200 candles, RSI-14 needs 15, Ichimoku needs 52)
- **D-11:** `IndicatorEngine` class orchestrates computation for all indicators on a given symbol/timeframe — single entry point
- **D-12:** Computed values cached in-memory (dict keyed by `{symbol}:{timeframe}:{indicator_name}:{params}`) — refreshed on new candle arrival
- **D-13:** Optional Redis persistence of indicator values for cross-process sharing — but in-memory is the primary path for speed

### Event Publishing
- **D-14:** Batched event publishing — one `IndicatorUpdateEvent` per symbol/timeframe after ALL indicators for that pair are computed
- **D-15:** Event contains the full indicator snapshot (all 14 results) so downstream consumers get a consistent view
- **D-16:** IndicatorEngine subscribes to `MarketDataEvent` on the event bus and auto-computes on new candle arrival

### Indicator Architecture
- **D-17:** Base `Indicator` abstract class with `compute(candles) → IndicatorResult` and `lookback_period` property
- **D-18:** Each of the 14 indicators is a concrete class inheriting from `Indicator`
- **D-19:** Indicators are stateless computational units — state (rolling buffers, caches) lives in the `IndicatorEngine`
- **D-20:** All indicator parameters configurable via `settings.yaml` under `strategy.ema_periods`, `strategy.rsi_period`, etc. (already defined in Phase 1 config)

### The 14 Indicators
- **D-21:** Exact implementations required (matching REQUIREMENTS.md):
  1. EMA (5, 9, 21, 50, 100, 200) — INDI-01
  2. RSI (14) — INDI-02
  3. ADX/DMI (14) — INDI-03
  4. ATR (14) — INDI-04
  5. MACD (12, 26, 9) — INDI-05
  6. Bollinger Bands (20, 2σ) — INDI-06
  7. Keltner Channels (20, 1.5×ATR) — INDI-07
  8. VWAP (session-based) — INDI-08
  9. Supertrend (10, 3.0) — INDI-09
  10. Stochastic (14, 3, 3) — INDI-10
  11. Donchian Channels (20) — INDI-11
  12. Volume Profile (POC, VAH, VAL) — INDI-12
  13. OBV (cumulative) — INDI-13
  14. Ichimoku Cloud (9, 26, 52) — INDI-14

### Agent's Discretion
- NumPy array optimization details (vectorized operations, memory layout)
- Exact rolling buffer implementation (deque, circular buffer, or array slicing)
- Test reference value sources (manual calculation or TA-Lib comparison)
- Module structure within `src/algoforge/technical/` (flat vs grouped by indicator type)
- Error handling for edge cases (insufficient data, all-NaN series)
- Squeeze detection logic for Bollinger/Keltner (boolean signal when BB inside KC)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 Foundation (built)
- `src/algoforge/core/models.py` — OHLCV, OHLCVSeries models with `.closes`, `.highs`, `.lows`, `.volumes` properties
- `src/algoforge/core/event_bus.py` — EventBus with `MarketDataEvent` for subscribing to new candle data
- `src/algoforge/core/config.py` — Settings with `strategy.ema_periods`, `strategy.rsi_period`, `strategy.adx_period`, `strategy.atr_period`
- `src/algoforge/core/constants.py` — Timeframe enum, TIMEFRAME_CONFIG mapping per mode
- `src/algoforge/data/storage/redis_store.py` — Redis OHLCV storage for fetching candle history

### Requirements
- `.planning/REQUIREMENTS.md` §INDI-01 to INDI-14 — All 14 indicator specifications with exact parameters

### Architecture
- `.planning/research/ARCHITECTURE.md` — System data flow
- `GEMINI.md` — Code style, type hints, docstrings, async patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OHLCVSeries.closes` / `.highs` / `.lows` / `.volumes` — Ready-made NumPy-convertible lists for indicator input
- `EventBus.subscribe("market_data", handler)` — Hook for auto-compute on new candle
- `StrategyConfig.ema_periods`, `.rsi_period`, `.adx_period`, `.atr_period` — Already defined config parameters
- `RedisStore.get_candles()` — Fetch historical candles for initial indicator seeding

### Established Patterns
- Pydantic models for all data structures (follow for IndicatorResult)
- Async event handlers on EventBus (follow for IndicatorEngine)
- Abstract base class pattern (DataFeed ABC → follow for Indicator ABC)
- structlog for all logging

### Integration Points
- Phase 3 (S/R + Trendlines) will read EMA, ATR values to detect structural levels
- Phase 4 (Regime Detection) will read ADX, BB width, ATR, divergence metrics
- Phase 5 (Primary Strategy) will read EMA alignment, RSI, ADX for signal confirmation
- Phase 6 (Risk Management) will read ATR for stop-loss sizing

</code_context>

<specifics>
## Specific Ideas

- Performance target: 100 instruments × 6 timeframes processed in < 1 second
- Incremental updates are critical — strategies need real-time indicator values, not batch-recomputed historical series
- Volume Profile (INDI-12) is the most complex — needs price binning, POC/VAH/VAL calculation
- VWAP (INDI-08) is session-based — needs market hours from constants to reset daily
- Squeeze detection (BB inside KC) is a derived signal used by Phase 4 regime detection

</specifics>

<deferred>
## Deferred Ideas

- GPU-accelerated indicator computation (cupy) — evaluate only if 1-second target is not met with NumPy
- Indicator visualization/charting — defer to Phase 14 (Dashboard)
- Custom indicator framework for user-defined indicators — defer to v2
- TA-Lib as optional runtime backend — keep as test-only reference for now

</deferred>

---

*Phase: 02-technical-indicators*
*Context gathered: 2026-04-18*
