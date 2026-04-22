---
gap_closure: false
---

# Plan 12-01: Multi-Target Exits & Tranches

## Objective
Implement dynamic multi-target exits. Split trades into 3 tranches (50/30/20) with staggered R-multiple take profits, time-based breakeven tightening, and a candle-close trailing stop for the runner.

## Tasks

- [ ] **1. Position Data Model Updates**
  - Update `ActivePosition` in `src/algoforge/risk/models.py`.
  - Add `parent_trade_id` (str), `tranche_id` (int: 1,2,3), `elapsed_candles` (int), and `is_breakeven` (bool).
  - Add `trailing_step` (float | None) for the runner.

- [ ] **2. Initial Stop Loss Calculator**
  - Create `src/algoforge/exits/stops.py`.
  - Implement `calculate_initial_stop(entry, direction, atr, regime)`.
  - Trending = 1.5 ATR. Ranging = 1.0 ATR.

- [ ] **3. Tranche Splitter**
  - Create `src/algoforge/exits/tranches.py`.
  - Implement `split_into_tranches(parent_trade_id, total_size, entry, initial_sl)`.
  - Generate TP1 (50% size, 1.5R), TP2 (30% size, 2.5R), and TP3 (20% size, None TP).

- [ ] **4. Exit Manager (Tick/Candle Evaluator)**
  - Create `src/algoforge/exits/manager.py`.
  - Implement `ExitManager.evaluate_candle_close(positions, atr)`.
  - Increment `elapsed_candles`.
  - Enforce Time-based Breakeven (e.g. if `elapsed_candles >= time_limit` and TP1 not hit, move SL to Entry).
  - Update Trailing Stop for TP3 (ratchet forward by 2x ATR).

- [ ] **5. Integration & API**
  - Create `src/algoforge/exits/__init__.py`.
  - Export public classes and functions.

- [ ] **6. Testing & Verification**
  - Create `tests/unit/test_exits.py`.
  - Test tranche math (volume splitting and R-multiple TP levels).
  - Test time-based breakeven triggers correctly.
  - Test trailing stop ratchets only forward, never backwards.
