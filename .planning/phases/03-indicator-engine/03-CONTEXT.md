# Phase 3: Orthogonal Indicator Engine (7 Indicators) - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Restructure the existing 14-indicator engine into a 7 orthogonal indicator engine (zero redundancy) plus 3 optional supporting tools. Each core indicator measures a unique dimension of market behavior. Add KAMA and ROC (new). Remove MACD, Stochastic, Supertrend, Ichimoku, EMA from the active engine. Keep removed indicators in codebase for future use.

</domain>

<decisions>
## Implementation Decisions

### Engine Restructuring (D-01)
- **D-01:** Use **two-tier architecture** — 7 core orthogonal indicators always computed on every `compute()` call. 3 supporting tools (Donchian, Keltner, VolumeProfile) are optional and configurable. Old indicators (MACD, Stochastic, Supertrend, Ichimoku, EMA) stay in codebase files but are removed from the default IndicatorEngine constructor. Engine constructor accepts `include_tools: list[str]` parameter to toggle supporting tools.

### Core 7 Orthogonal Indicators
1. **KAMA (10, 2, 30)** — Adaptive trend direction (replaces 6 static EMAs) — **NEW, must implement**
2. **ADX/DMI (14)** — Trend strength measurement — EXISTS in `adx.py`
3. **ROC (14)** — Pure momentum (Rate of Change) — **NEW, must implement**
4. **ATR (14)** — Volatility state — EXISTS in `atr.py`
5. **Bollinger %B (20, 2σ)** — Volatility extremes — EXISTS in `bollinger.py` (add %B output)
6. **OBV** — Volume-price divergence — EXISTS in `obv.py`
7. **VWAP** — Institutional fair value — EXISTS in `vwap.py`
8. **RSI (14)** — Used ONLY for divergence detection — EXISTS in `rsi.py`

Note: Success criteria lists 7 indicators but RSI (item 6) plus ATR+Bollinger (item 4) means 8 indicator implementations. All 8 are "core" — always computed.

### Supporting Tools (Optional)
- Donchian Channels (20) — EXISTS in `donchian.py`
- Keltner Channels (20, 1.5×ATR) — EXISTS in `keltner.py`
- Volume Profile — EXISTS in `volume_profile.py`

### Implementation Approach (D-02)
- **D-02:** Use **Pure NumPy** for KAMA and ROC — consistent with all existing indicators. No new dependencies (no ta-lib, no pandas-ta). KAMA formula: Efficiency Ratio → adaptive smoothing constant → recursive computation. ROC formula: `(close - close_n) / close_n * 100`. If performance becomes a bottleneck at scale, ta-lib can be swapped in behind the Indicator ABC.

### Caching Strategy (D-03)
- **D-03:** Keep **unlimited in-memory cache** — current v1 pattern. 600 entries (100 instruments × 6 timeframes) is trivial memory. Engine recomputes on every new candle so cache is always fresh. Existing `clear_cache(symbol)` method handles manual cleanup.

### Agent's Discretion
- KAMA implementation details (seed value, edge case handling)
- ROC edge case handling (division by zero when close_n == 0)
- Bollinger %B output format (add to existing BollingerBands or separate indicator)
- IndicatorEngine constructor API for tool selection
- Test reference values for KAMA/ROC validation
- Performance benchmark approach for the 100×6 within 1 second target

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Design
- `refined_trading_system_prompt.md` — §Indicator selection rationale, orthogonality requirements
- `.planning/ROADMAP.md` — Phase 3 success criteria (10 items)

### Existing Code (upgrade base)
- `src/algoforge/technical/engine.py` — v1 IndicatorEngine with 14 indicators, IndicatorSnapshot, caching, batch compute
- `src/algoforge/technical/indicator_base.py` — Indicator ABC, IndicatorResult Pydantic model, ema_calc(), true_range() helpers
- `src/algoforge/technical/adx.py` — Existing ADX/DMI (keep)
- `src/algoforge/technical/atr.py` — Existing ATR (keep)
- `src/algoforge/technical/bollinger.py` — Existing BollingerBands (keep, add %B)
- `src/algoforge/technical/obv.py` — Existing OBV (keep)
- `src/algoforge/technical/vwap.py` — Existing VWAP (keep)
- `src/algoforge/technical/rsi.py` — Existing RSI (keep)
- `src/algoforge/technical/donchian.py` — Supporting tool (keep, make optional)
- `src/algoforge/technical/keltner.py` — Supporting tool (keep, make optional)
- `src/algoforge/technical/volume_profile.py` — Supporting tool (keep, make optional)

### Prior Phase Context
- `.planning/phases/01-foundation-data/01-CONTEXT.md` — Incremental upgrade approach (D-06)
- `.planning/phases/02-async-event-bus/02-CONTEXT.md` — Pydantic events for IndicatorUpdateEvent

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `indicator_base.py`: Indicator ABC + IndicatorResult model — all new indicators inherit from this
- `indicator_base.py`: `ema_calc()` helper — reusable for KAMA's adaptive EMA computation
- `indicator_base.py`: `true_range()` helper — used by ATR/ADX/Keltner
- `engine.py`: IndicatorSnapshot, compute(), compute_batch(), caching — upgrade in place
- All 14 existing indicator implementations — 5 removed from engine, kept as files

### Established Patterns
- Every indicator: `compute(closes, highs, lows, volumes, opens) -> IndicatorResult`
- IndicatorResult: `{name, values: {series_name: [float]}, params, timestamp, metadata}`
- Engine: register indicators in __init__, iterate in compute(), cache by `symbol:timeframe`
- NumPy arrays as input, NaN-padded arrays as output

### Integration Points
- `engine.py` compute() → used by strategies (future phases)
- IndicatorSnapshot → consumed by signal families (Phases 6-9)
- Event bus → IndicatorUpdateEvent can be published after compute (Phase 2 integration)

</code_context>

<specifics>
## Specific Ideas

- KAMA replaces ALL 6 static EMAs (5, 9, 21, 50, 100, 200) — this is the key architectural decision from the v2 prompt
- RSI is kept but repurposed: ONLY for divergence detection, NOT for overbought/oversold signals
- ROC replaces RSI/Stochastic/MACD for momentum signals — simpler, more direct
- Bollinger %B = (price - lower) / (upper - lower) — measures where price sits within the bands (0-1 scale)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-indicator-engine*
*Context gathered: 2026-04-19*
