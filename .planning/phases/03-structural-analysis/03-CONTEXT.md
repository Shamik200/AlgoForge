# Phase 3: Structural Analysis (S/R + Trendlines) - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Build algorithmic detection of support/resistance levels and trendline construction on configurable timeframes. S/R detection uses fractal-based swing point identification with volume-weighted strength scoring. Trendlines connect actual swing points (2-3+ touches). System determines bigger trend direction (UP/DOWN/UNCLEAR) and identifies ascending/descending channels. Broken trendlines are invalidated in real-time. This phase produces the structural analysis that Phase 4 (Regime Detection) and Phase 5 (Primary Strategy) depend on.

</domain>

<decisions>
## Implementation Decisions

### S/R Detection Algorithm
- **D-01:** Fractal-based detection using Williams 5-bar fractal pattern (2 bars before + 2 bars after the swing point)
- **D-02:** Volume confirmation — S/R levels weighted by volume traded at/near the level (higher volume = stronger level)
- **D-03:** Strength scoring combines: touch count, recency (exponential decay), volume weight, and price reaction magnitude
- **D-04:** S/R levels detected on higher timeframes per TIMEFRAME_CONFIG (1D/1H for intraday, 1M/1Y for swing)
- **D-05:** Cluster merging — nearby S/R levels within 0.5% of each other merged into zones (avoids 50 levels at ±$0.01)
- **D-06:** Maximum 10 active S/R levels per symbol/timeframe (top by strength score)

### Trendline Construction
- **D-07:** Direct swing-point connection — trendlines pass through actual fractal swing highs (resistance) and swing lows (support)
- **D-08:** Minimum 2 touch points required, 3+ preferred. Lines with 3+ touches scored higher.
- **D-09:** Trendline validation: price must respect the line (not violated for >2 consecutive candles)
- **D-10:** Multiple valid trendlines ranked by: touch count > recency of last touch > line age
- **D-11:** Trendlines on mid timeframes per TIMEFRAME_CONFIG (15min/5min for intraday, 1W/1D for swing)
- **D-12:** Maximum 4 active trendlines per symbol/timeframe (2 upper + 2 lower)

### Trend Direction Logic
- **D-13:** Primary method: Higher-highs/higher-lows (HH/HL) pattern detection for UP trend; lower-highs/lower-lows (LH/LL) for DOWN trend
- **D-14:** Confirmation: EMA alignment check (EMA-5 > EMA-21 > EMA-50 = UP, reverse = DOWN)
- **D-15:** Both HH/HL pattern AND EMA alignment must agree for UP/DOWN. If they conflict → UNCLEAR
- **D-16:** Trend direction uses at least 3 recent swing points to determine pattern

### Channel Detection
- **D-17:** Independent upper + lower trendline fit — not parallel offset
- **D-18:** Channel identified when both upper trendline (through swing highs) and lower trendline (through swing lows) exist with similar slope direction
- **D-19:** Channel type: ascending (both lines slope up), descending (both slope down), horizontal (both roughly flat)
- **D-20:** Channel validity requires each boundary to have ≥2 touch points

### Invalidation & Real-time Updates
- **D-21:** Trendline broken when close price violates the line by > 1× ATR
- **D-22:** Broken trendlines removed from active set immediately (within 1 candle)
- **D-23:** S/R levels that are broken (close through level with volume) get demoted but not removed — they can act as resistance-turned-support or vice versa
- **D-24:** All structural analysis recomputed on each new candle arrival via event bus subscription

### Architecture
- **D-25:** `SRDetector` class — finds and scores support/resistance levels
- **D-26:** `TrendlineBuilder` class — constructs and validates trendlines from swing points
- **D-27:** `TrendAnalyzer` class — determines trend direction and channel identification
- **D-28:** `StructuralEngine` orchestrator — coordinates all three, subscribes to IndicatorUpdateEvent, publishes StructuralUpdateEvent
- **D-29:** Pydantic models: `SRLevel`, `Trendline`, `Channel`, `TrendDirection`, `StructuralSnapshot`

### Agent's Discretion
- Fractal lookback window size (2-bar vs 3-bar Williams fractal)
- Exact exponential decay rate for recency weighting
- Slope similarity threshold for channel detection
- Performance optimizations (caching swing points across updates)
- Test data generation for validation (synthetic trends, ranges, channels)

</decisions>

<canonical_refs>
## Canonical References

### Phase 2 (built — indicators available)
- `src/algoforge/technical/engine.py` — IndicatorEngine, IndicatorSnapshot, compute()
- `src/algoforge/technical/ema.py` — EMA for trend confirmation
- `src/algoforge/technical/atr.py` — ATR for trendline break threshold
- `src/algoforge/technical/indicator_base.py` — Indicator ABC, IndicatorResult model

### Phase 1 (built — data layer)
- `src/algoforge/core/models.py` — OHLCV, OHLCVSeries
- `src/algoforge/core/event_bus.py` — EventBus pub/sub
- `src/algoforge/core/constants.py` — Timeframe, TIMEFRAME_CONFIG

### Requirements
- `.planning/REQUIREMENTS.md` §STRU-01 to STRU-06

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OHLCVSeries.highs` / `.lows` / `.closes` — For swing point detection
- `IndicatorEngine.compute()` → `IndicatorSnapshot.get("ema")` — EMA values for trend confirmation
- `IndicatorSnapshot.get("atr")` — ATR values for break thresholds
- `EventBus` — Subscribe to `IndicatorUpdateEvent`, publish `StructuralUpdateEvent`

### Integration Points
- Phase 4 (Regime Detection) reads S/R levels, trendlines, trend direction
- Phase 5 (Primary Strategy) uses trendline touches as entry signals, S/R for SL/TP placement

</code_context>

<deferred>
## Deferred Ideas

- ML-based S/R detection (CNN on price charts) — evaluate in Phase 13
- Dynamic fractal window size (adapt to volatility) — revisit after backtesting
- Multi-timeframe S/R confluence scoring — evaluate in Phase 11

</deferred>

---

*Phase: 03-structural-analysis*
*Context gathered: 2026-04-18*
*Priority: Accuracy first, speed second*
