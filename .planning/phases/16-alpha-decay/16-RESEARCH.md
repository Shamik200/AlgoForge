# Phase 16: Alpha Decay Monitoring System - Research

## Context
Signal strategies inevitably degrade. The Alpha Decay monitor sits above the Signal Combination Engine to continuously track live performance metrics against static backtest baselines. If statistical decay is detected, the monitor gracefully throttles or completely pauses the strategy's conviction weight.

## Technical Findings

1. **Metrics Required:**
   - **Rolling Sharpe (30-day and 90-day):** Needs daily PnL vectors for each strategy.
   - **Hit Rate Deviation:** Uses a standard Z-score check `(live_hit_rate - baseline_hit_rate) / baseline_std_dev`. If deviation > 2σ (negative), it's failing statistically.
   - **Average R Check:** Tracks the average return per trade relative to initial risk. If `< 0.5R`, the strategy is broken.

2. **Integration with Engine:**
   - Instead of hard-removing strategies, the Decay Monitor calculates a `health_multiplier` (0.0 to 1.0) for each signal family.
   - The Signal Combination Engine (`engine.py` from Phase 11) will be modified to accept these multipliers and scale the Softmax output weights.

3. **Baseline Architecture:**
   - Creates a `BaselineManifest` dataclass to parse the JSON files output by Phase 15.

## Implementation Path
- Create `src/algoforge/decay/models.py` for health state and baseline manifest.
- Create `src/algoforge/decay/monitor.py` containing the `AlphaDecayMonitor` class.
- Update `src/algoforge/combination/engine.py` to apply health multipliers.
- Create `tests/unit/test_decay.py`.
