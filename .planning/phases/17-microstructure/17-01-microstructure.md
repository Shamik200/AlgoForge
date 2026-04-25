---
gap_closure: false
---

# Plan 17-01: Signal Family 5 — Microstructure / Order Flow

## Objective
Implement a new signal family that generates microstructure-based trading signals from VWAP deviation, volume imbalance, and OBV divergence. Self-disables on non-intraday timeframes and gracefully degrades when L2 data is unavailable.

## Tasks

- [ ] **1. VWAP Tracker**
  - Create `src/algoforge/signals/microstructure/vwap.py`.
  - Implement `VWAPTracker` with cumulative `(price × volume)` and session reset.
  - Implement `deviation_score()` returning [-1, +1] based on distance from VWAP in σ units.

- [ ] **2. Volume Indicators**
  - Create `src/algoforge/signals/microstructure/volume.py`.
  - Implement `calculate_volume_imbalance(high, low, close)` (L1 buying pressure proxy).
  - Implement `detect_obv_divergence(prices, volumes, window)` for L1 fallback mode.

- [ ] **3. Microstructure Family Orchestrator**
  - Create `src/algoforge/signals/microstructure/family.py`.
  - Implement `MicrostructureFamily.generate(candle_data)` returning a `SignalResult`.
  - Add timeframe guard: return `is_valid=False` for >= 1D.
  - Mode selection: detect L2 availability, fall back to L1 indicators.

- [ ] **4. Integration & Testing**
  - Create `src/algoforge/signals/microstructure/__init__.py`.
  - Create `tests/unit/test_microstructure.py`.
  - Test VWAP deviation signals.
  - Test volume imbalance calculation.
  - Test OBV divergence detection.
  - Test timeframe guard self-disabling.
