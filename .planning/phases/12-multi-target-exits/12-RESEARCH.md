# Phase 12: Multi-Target Exits - Research

## Context
Replacing rigid single-target exits with dynamic, multi-tranche exits to optimize risk-adjusted returns and capture outlier moves. The system splits a single conceptual trade into three independent `ActivePosition` tranches, each with distinct exit rules: fixed R-multiple take profits, a trailing stop runner, and time-based breakeven tightening.

## Technical Findings

1. **ATR-Anchored Initial Stop Loss:**
   - Instead of static percentage drops, the initial stop loss is anchored to the Average True Range (ATR).
   - If the current HMM Regime is `Trending`, the SL is set at `Entry - (1.5 * ATR)` for longs.
   - If the HMM Regime is `Ranging`, the SL is tighter: `Entry - (1.0 * ATR)`.
   - The "Risk Distance" `R` is defined as `abs(Entry - Initial_SL)`.

2. **Tranche Split Architecture:**
   - A single approved trade will spawn three separate `ActivePosition` objects in the ledger, all sharing a `parent_trade_id`.
   - **Tranche 1 (50% Volume):** Take Profit set at `Entry + (1.5 * R)`.
   - **Tranche 2 (30% Volume):** Take Profit set at `Entry + (2.5 * R)`.
   - **Tranche 3 (20% Volume):** No hard Take Profit. It uses a dynamic trailing stop.

3. **Time-Based Tightening (Breakeven):**
   - For all active tranches, we track the number of `elapsed_candles`.
   - If `elapsed_candles >= time_limit` (e.g. 5 days for swing) AND Tranche 1 has *not* hit its Take Profit, the trade is stalling.
   - Action: Move the Stop Loss of all remaining tranches to `Entry Price` (Breakeven) plus a tiny slippage buffer.

4. **Trailing Stop Logic (Tranche 3 Runner):**
   - Tranche 3 is designed to capture outlier, multi-sigma moves.
   - The trailing stop distance is set to `2.0 * ATR`.
   - **Ratchet Rule:** The trailing stop only evaluates at candle close. If `Close - (2.0 * ATR)` > `Current_SL`, then `Current_SL` is updated.
   - The stop can only move forward, never backward.

## Implementation Path
- Modify `ActivePosition` model in `src/algoforge/risk/models.py` to support `parent_trade_id`, `tranche_id`, `elapsed_candles`, and `is_breakeven`.
- Create `src/algoforge/exits/` module.
- Implement `stops.py` to handle ATR-based initial SL calculation and HMM regime integration.
- Implement `tranches.py` to handle splitting an approved trade into the three 50/30/20 active positions.
- Implement `manager.py` (ExitManager) that runs every candle to evaluate trailing stops and time-based tightening.
- Update tests to ensure tranches trigger correctly and the trailing stop only ratchets on closed candles.
