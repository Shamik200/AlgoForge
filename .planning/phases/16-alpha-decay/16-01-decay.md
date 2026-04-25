---
gap_closure: false
---

# Plan 16-01: Alpha Decay Monitoring

## Objective
Build the Alpha Decay monitor to compute rolling Sharpe, evaluate statistical hit rate degradation, and dynamically throttle Signal Combination conviction weights via a `health_multiplier`.

## Tasks

- [ ] **1. Decay Models & Baseline**
  - Create `src/algoforge/decay/models.py`.
  - Define `BaselineManifest` (hit_rate, average_r, sharpe, std_dev).
  - Define `HealthStatus` enum (HEALTHY, DEGRADED, PAUSED).

- [ ] **2. Monitor Logic**
  - Create `src/algoforge/decay/monitor.py`.
  - Implement `evaluate_family_health(trades, baseline) -> float`.
  - Check 30-day Sharpe (< 0 = 0.5 multiplier).
  - Check Average R (< 0.5R = 0.0 multiplier).
  - Check Hit Rate Z-score (> 2σ decay = 0.0 multiplier).

- [ ] **3. Combination Engine Update**
  - Modify `src/algoforge/combination/engine.py` to accept a `health_multipliers` dict.
  - Apply multiplier *after* Softmax weighting, then re-normalize.

- [ ] **4. Integration & Testing**
  - Create `src/algoforge/decay/__init__.py`.
  - Create `tests/unit/test_decay.py`.
  - Test health multiplier generation and Combination Engine re-normalization.
