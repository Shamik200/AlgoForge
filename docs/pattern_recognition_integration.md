# Pattern Recognition Integration

## Overview

This document describes the integration of the PatternRecognizer into the signal generation flow, implementing Requirements 3.2, 3.4, and 3.5 from the AlgoForge System Integration specification.

## Implementation

### Location

The pattern recognition integration is implemented in:
- **Module**: `src/algoforge/engine/live_handler.py`
- **Function**: `_compute_signal_families()`

### How It Works

#### 1. Pattern Detection (Requirement 3.2)

On every bar, the PatternRecognizer is invoked to detect candlestick patterns:

```python
from algoforge.structural.pattern_recognizer import PatternRecognizer

pattern_recognizer = PatternRecognizer()

# Extract OHLC arrays for pattern recognition
opens = np.array([c.open for c in series.candles], dtype=np.float64)
highs = np.array([c.high for c in series.candles], dtype=np.float64)
lows = np.array([c.low for c in series.candles], dtype=np.float64)
closes = np.array([c.close for c in series.candles], dtype=np.float64)

# Recognize patterns in recent bars
detected_patterns = pattern_recognizer.recognize_patterns(
    opens=opens,
    highs=highs,
    lows=lows,
    closes=closes,
    lookback=5,
)
```

#### 2. S/R Level Confluence Check

Detected patterns are checked for proximity to Support/Resistance levels:

```python
if detected_patterns and structure and hasattr(structure, 'support_resistance_levels'):
    current_price = closes[-1]
    sr_levels = structure.support_resistance_levels
    
    # Check proximity to S/R levels (within 0.5% tolerance)
    for pattern in detected_patterns:
        for level in sr_levels:
            level_price = level.price if hasattr(level, 'price') else level
            if abs(current_price - level_price) / level_price < 0.005:
                pattern.at_sr_level = True
                pattern.confluence_boost = 0.2  # 20% boost
                break
```

#### 3. Conviction Adjustments

After all signal families generate their signals, pattern-based conviction adjustments are applied:

##### Boost at S/R Level (Requirement 3.2)

When a pattern forms at a high-confluence S/R level and aligns with the signal direction:

```python
if pattern.at_sr_level and pattern_dir != "neutral":
    # Check if pattern direction aligns with signal
    if (signal_direction_str == "long" and pattern_dir == "bullish") or \
       (signal_direction_str == "short" and pattern_dir == "bearish"):
        signal.score = signal.score * 1.20  # 20% boost
```

**Example**: A long signal with score 0.5 becomes 0.6 when a bullish hammer forms at a support level.

##### Reduction on Reversal Conflict (Requirement 3.4)

When a reversal pattern conflicts with the signal direction:

```python
reversal_patterns = ["engulfing", "hammer", "shooting_star", "morning_star", "evening_star", "piercing", "dark_cloud"]

if pattern.pattern_type in reversal_patterns:
    # Check if pattern direction conflicts with signal
    if (signal_direction_str == "long" and pattern_dir == "bearish") or \
       (signal_direction_str == "short" and pattern_dir == "bullish"):
        signal.score = signal.score * 0.70  # 30% reduction
```

**Example**: A long signal with score 0.8 becomes 0.56 when a bearish evening star pattern forms.

#### 4. Metadata Tracking

Pattern adjustments are tracked in signal metadata:

```python
if adjustment_applied:
    if not hasattr(signal, 'metadata') or signal.metadata is None:
        signal.metadata = {}
    signal.metadata['pattern_adjustments'] = adjustment_reason
    signal.metadata['original_score'] = original_score
```

## Supported Patterns

The PatternRecognizer detects 10 major candlestick patterns:

### Single-Candle Patterns
1. **Hammer** (bullish) - Small body at top, long lower shadow
2. **Shooting Star** (bearish) - Small body at bottom, long upper shadow
3. **Doji** (neutral) - Very small body

### Two-Candle Patterns
4. **Engulfing** (bullish/bearish) - Second candle engulfs first
5. **Piercing Line** (bullish) - Bullish candle closes above midpoint of bearish
6. **Dark Cloud Cover** (bearish) - Bearish candle closes below midpoint of bullish
7. **Harami** (bullish/bearish) - Small candle inside large candle

### Three-Candle Patterns
8. **Morning Star** (bullish) - Bearish → small body → bullish
9. **Evening Star** (bearish) - Bullish → small body → bearish
10. **Three White Soldiers** (bullish) - Three consecutive bullish candles
11. **Three Black Crows** (bearish) - Three consecutive bearish candles

## Design Principles (Requirement 3.5)

Pattern recognition is used as a **confirmation filter**, not a standalone signal generator:

- Patterns **modify** existing signal conviction scores
- Patterns **do not create** new signals
- Patterns **do not change** signal direction or family
- Patterns provide **additional context** for decision-making

## Configuration

The PatternRecognizer can be configured with:

```python
PatternRecognizer(
    body_ratio=0.3,        # Minimum body/range ratio for significant candles
    doji_ratio=0.1,        # Maximum body/range ratio for doji patterns
    confluence_boost=0.2,  # Conviction boost at S/R level (20%)
)
```

## Logging

Pattern detection and adjustments are logged for observability:

```python
logger.debug(
    "patterns_detected",
    count=len(detected_patterns),
    patterns=[p.pattern_type for p in detected_patterns],
)

logger.debug(
    "pattern_conviction_boost",
    family=signal.family_name,
    pattern=pattern.pattern_type,
    original_score=round(original_score, 3),
    adjusted_score=round(signal.score, 3),
)

logger.debug(
    "pattern_conviction_reduction",
    family=signal.family_name,
    pattern=pattern.pattern_type,
    original_score=round(original_score, 3),
    adjusted_score=round(signal.score, 3),
)
```

## Error Handling

Pattern recognition failures are handled gracefully:

```python
try:
    # Pattern recognition logic
    detected_patterns = pattern_recognizer.recognize_patterns(...)
except Exception as e:
    logger.warning("pattern_recognition_error", error=str(e))
    # Continue with empty patterns list
```

The system continues operating even if pattern recognition fails, ensuring robustness.

## Testing

### Unit Tests
- `tests/unit/test_pattern_recognizer.py` - 28 tests covering all pattern types

### Integration Tests
- `tests/integration/test_pattern_signal_integration.py` - 10 tests covering:
  - Pattern detection with OHLC arrays
  - Conviction boost at S/R levels
  - Conviction reduction on reversal conflicts
  - Metadata tracking
  - Multiple pattern adjustments
  - Requirements validation

## Performance Considerations

- Pattern recognition runs on every bar for all active instruments
- Lookback window is limited to 5 bars to minimize computation
- Pattern detection is vectorized using NumPy for efficiency
- S/R level proximity checks use simple distance calculations

## Future Enhancements

Potential improvements for future iterations:

1. **Multi-timeframe patterns** - Detect patterns on higher timeframes
2. **Pattern strength weighting** - Adjust conviction based on pattern strength
3. **Pattern confirmation** - Require multiple bars to confirm pattern validity
4. **Adaptive thresholds** - Learn optimal boost/reduction percentages from historical performance
5. **Pattern combinations** - Detect compound patterns (e.g., double bottom with hammer)

## References

- **Requirements**: AlgoForge System Integration - Requirements 3.1, 3.2, 3.3, 3.4, 3.5
- **Design**: AlgoForge System Integration - Design Section 4 (PatternRecognizer)
- **Tasks**: AlgoForge System Integration - Tasks 4.5, 4.6
