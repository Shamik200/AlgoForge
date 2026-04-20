# Phase 9: Signal Family 4 — Structural Confluence - Research

## Context
Building the Structural Confluence Signal Family. This signal relies heavily on the `StructuralSnapshot` output from Phase 4. It triggers when price tests high-conviction support/resistance zones and displays localized candlestick rejection (wicks and volume spikes), outputting a normalized `[-1.0, 1.0]` composite score.

## Technical Findings

1. **"Approaches" Proximity Threshold:**
   - A structural level is "tested" if the current bar's Low or High enters the zone defined by `LevelPrice +/- (0.5 * ATR(14))`.
   - If multiple levels fall into this band, the one with the highest `confluence_score` is evaluated.

2. **Reversal Micro-Structure (Candlesticks):**
   - **Bullish Rejection:** 
     - Price tests a Support level.
     - Lower Wick = `min(Open, Close) - Low`.
     - Wick Ratio = `Lower Wick / (High - Low)`.
     - Condition: `Wick Ratio > 0.5` AND `Volume > 1.5 * SMA(Volume, 20)`.
   - **Bearish Rejection:**
     - Price tests a Resistance level.
     - Upper Wick = `High - max(Open, Close)`.
     - Wick Ratio = `Upper Wick / (High - Low)`.
     - Condition: `Wick Ratio > 0.5` AND `Volume > 1.5 * SMA(Volume, 20)`.

3. **Multi-Timeframe (MTF) Alignment:**
   - The signal takes an optional `list[StructuralSnapshot]` for HTF data.
   - For the tested LTF level, scan the HTF snapshots. If an HTF level exists within `0.5 * ATR` of the LTF level, a `1.5x` multiplier is applied to the base conviction score.

4. **Direction & Regime Guard:**
   - Direction is primarily dictated by the rejection type (Bullish Rejection -> LONG, Bearish Rejection -> SHORT).
   - **Trend Dampening:** If the `RegimeProbabilities` indicates a strong trend (e.g. `trend_up > 0.5`) AND the momentum score agrees, counter-trend structural rejections are heavily penalized (multiplier `0.3x`).
   - **Range Boosting:** If regime is `mean_revert > 0.5`, structural rejections are boosted (multiplier `1.3x`).

5. **Score Calculation:**
   - Base Score = `min(1.0, confluence_score / 5.0)` (assuming a score of 5 is max conviction).
   - Apply MTF multiplier (1.5x).
   - Apply Regime multiplier (0.3x or 1.3x).
   - Hard clip to `[-1.0, 1.0]`.

## Implementation Path
- Create `src/algoforge/signals/structural/`
- Implement `microstructure.py` for Wick and Volume climax detection.
- Implement `proximity.py` to find intersecting levels from `StructuralSnapshot` objects.
- Create `StructuralConfluenceSignal` class that ties the snapshot, ATR, and microstructure together.
- Unit tests focusing on wick math, proximity bounds, and MTF multipliers.
