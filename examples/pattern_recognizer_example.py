"""Example usage of PatternRecognizer for candlestick pattern detection.

This example demonstrates how to use the PatternRecognizer class to detect
candlestick patterns from price data.

Requirements: 3.1, 3.3
"""

import numpy as np

from algoforge.structural import CandlestickPattern, PatternRecognizer


def main() -> None:
    """Demonstrate PatternRecognizer usage."""
    print("=== PatternRecognizer Example ===\n")

    # Initialize the recognizer
    recognizer = PatternRecognizer(
        body_ratio=0.3,  # Minimum body/range ratio for significant candles
        doji_ratio=0.1,  # Maximum body/range ratio for doji patterns
        confluence_boost=0.2,  # Conviction boost when pattern at S/R level
    )

    # Example 1: Detect hammer pattern
    print("Example 1: Hammer Pattern")
    print("-" * 50)
    opens = np.array([100.0, 100.0, 100.0, 95.0])
    highs = np.array([101.0, 101.0, 101.0, 96.5])
    lows = np.array([99.0, 99.0, 99.0, 90.0])
    closes = np.array([100.5, 100.5, 100.5, 96.0])

    patterns = recognizer.recognize_patterns(opens, highs, lows, closes)
    print(f"Detected {len(patterns)} pattern(s):")
    for pattern in patterns:
        direction, strength = recognizer.classify_pattern(pattern)
        print(f"  - {pattern.pattern_type}: {direction} ({strength})")
        print(f"    Bars involved: {pattern.bars_involved}")
        print(f"    Timestamp: {pattern.timestamp}")
    print()

    # Example 2: Detect bullish engulfing pattern
    print("Example 2: Bullish Engulfing Pattern")
    print("-" * 50)
    opens = np.array([100.0, 100.0, 102.0, 98.0])
    highs = np.array([101.0, 101.0, 103.0, 104.0])
    lows = np.array([99.0, 99.0, 98.0, 97.0])
    closes = np.array([100.5, 100.5, 98.5, 103.0])

    patterns = recognizer.recognize_patterns(opens, highs, lows, closes)
    print(f"Detected {len(patterns)} pattern(s):")
    for pattern in patterns:
        direction, strength = recognizer.classify_pattern(pattern)
        print(f"  - {pattern.pattern_type}: {direction} ({strength})")
        print(f"    Bars involved: {pattern.bars_involved}")
        print(f"    Timestamp: {pattern.timestamp}")
    print()

    # Example 3: Detect three white soldiers pattern
    print("Example 3: Three White Soldiers Pattern")
    print("-" * 50)
    opens = np.array([100.0, 100.0, 100.0, 102.0, 104.0])
    highs = np.array([101.0, 101.0, 103.0, 105.0, 107.0])
    lows = np.array([99.0, 99.0, 99.5, 101.5, 103.5])
    closes = np.array([100.5, 100.5, 102.5, 104.5, 106.5])

    patterns = recognizer.recognize_patterns(opens, highs, lows, closes)
    print(f"Detected {len(patterns)} pattern(s):")
    for pattern in patterns:
        direction, strength = recognizer.classify_pattern(pattern)
        print(f"  - {pattern.pattern_type}: {direction} ({strength})")
        print(f"    Bars involved: {pattern.bars_involved}")
        print(f"    Timestamp: {pattern.timestamp}")
    print()

    # Example 4: Pattern at S/R level with confluence boost
    print("Example 4: Pattern at S/R Level")
    print("-" * 50)
    pattern_at_sr = CandlestickPattern(
        pattern_type="hammer",
        direction="bullish",
        strength="moderate",
        bars_involved=1,
        timestamp=10,
        at_sr_level=True,
        confluence_boost=0.2,
    )
    print(f"Pattern: {pattern_at_sr.pattern_type}")
    print(f"Direction: {pattern_at_sr.direction}")
    print(f"Strength: {pattern_at_sr.strength}")
    print(f"At S/R Level: {pattern_at_sr.at_sr_level}")
    print(f"Confluence Boost: {pattern_at_sr.confluence_boost * 100}%")
    print()

    # Example 5: Using lookback parameter
    print("Example 5: Lookback Parameter")
    print("-" * 50)
    # Create 20 bars with patterns at different positions
    opens = np.array([100.0] * 20)
    highs = np.array([101.0] * 20)
    lows = np.array([99.0] * 20)
    closes = np.array([100.5] * 20)

    # Add doji at index 5
    closes[5] = 100.05

    # Add doji at index 15
    closes[15] = 100.05

    # With lookback=5, should only detect recent patterns
    patterns = recognizer.recognize_patterns(opens, highs, lows, closes, lookback=5)
    print(f"Detected {len(patterns)} pattern(s) with lookback=5:")
    for pattern in patterns:
        print(f"  - {pattern.pattern_type} at timestamp {pattern.timestamp}")
    print()

    print("=== Pattern Recognition Complete ===")


if __name__ == "__main__":
    main()
