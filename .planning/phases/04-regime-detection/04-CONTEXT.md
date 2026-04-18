# Phase 4: Market Regime Detection - Context

**Gathered:** 2026-04-18
**Status:** Ready for execution

<domain>
## Phase Boundary

Classify each instrument's current market condition into one of 5 regimes (Trending, Range/Sideways, Breakout, Reversal, Liquidity Trap). Outputs probabilities for all 5 regimes (not just a label). Classification runs BEFORE any strategy is activated (mandatory gate). Uses ADX, Bollinger Band width, ATR expansion, volume, and divergence metrics.

</domain>

<decisions>
## Implementation Decisions

### Classification Approach
- **D-01:** Rule-based multi-factor scoring — each regime gets a probability score based on weighted indicator signals
- **D-02:** ADX is primary trend strength metric: ADX > 25 → Trending signal, ADX < 20 → Range signal
- **D-03:** Bollinger Band width for volatility state: squeeze (BB inside KC) → Breakout imminent, wide → Trending/Breakout active
- **D-04:** ATR expansion/contraction: rising ATR → Breakout/Trending, falling ATR → Range
- **D-05:** Volume analysis: volume spike (>2× average) + price move → Breakout; volume spike + reversal pattern → Reversal
- **D-06:** RSI divergence: bullish/bearish divergence at extremes → Reversal signal

### Regime Probability Output
- **D-07:** Output is dict of 5 probabilities summing to 1.0: {trending: 0.4, range: 0.3, breakout: 0.15, reversal: 0.1, liquidity_trap: 0.05}
- **D-08:** Primary regime is the one with highest probability
- **D-09:** Confidence = primary probability - second highest probability (higher gap = more confident)
- **D-10:** Minimum confidence threshold configurable — below threshold the regime is "uncertain"

### Liquidity Trap Detection
- **D-11:** False breakout pattern: price breaks S/R → reverses within 2-3 bars → volume spike on reversal
- **D-12:** Requires structural analysis data (S/R levels) from Phase 3

### Architecture
- **D-13:** `RegimeClassifier` class with `classify(indicators, structural) → RegimeResult`
- **D-14:** `RegimeResult` Pydantic model: probabilities, primary regime, confidence, contributing factors
- **D-15:** Must run before any strategy — enforced by strategy orchestrator checking regime result exists
- **D-16:** Regime changes logged with timestamps for analysis

### Agent's Discretion
- Exact weight tuning for each factor
- Smoothing of regime transitions (avoid flickering between regimes)
- Lookback window for volume spike detection
- Test data generation for each regime type

</decisions>

---

*Phase: 04-regime-detection*
*Context gathered: 2026-04-18*
