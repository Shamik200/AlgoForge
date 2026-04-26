"""Label engineering for supervised ML models.

Uses forward returns with ATR-based thresholds to create 3-class targets.
This avoids the noise of small returns and focuses on statistically significant moves.
"""

import numpy as np


def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Average True Range.

    Args:
        highs: Array of high prices.
        lows: Array of low prices.
        closes: Array of close prices.
        period: ATR lookback period.

    Returns:
        Array of ATR values (same length as input, NaN-padded at start).
    """
    n = len(closes)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]

    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )

    atr = np.full(n, np.nan)
    if n >= period:
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


def generate_labels(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    forward_bars: int = 5,
    atr_threshold_mult: float = 0.5,
    atr_period: int = 14,
) -> np.ndarray:
    """Generate 3-class labels from forward returns with ATR-based thresholds.

    Class mapping:
        +1 = LONG  (forward return > +threshold)
         0 = FLAT  (forward return within ±threshold)
        -1 = SHORT (forward return < -threshold)

    The threshold = atr_threshold_mult × ATR, which adapts to the instrument's
    current volatility regime. In low-vol markets, the threshold shrinks;
    in high-vol markets, it expands. This is critical for avoiding noise trades.

    Args:
        closes: Array of close prices.
        highs: Array of high prices.
        lows: Array of low prices.
        forward_bars: Number of bars forward for the return calculation.
        atr_threshold_mult: Multiplier for ATR to set the threshold.
        atr_period: Period for ATR calculation.

    Returns:
        Array of labels {-1, 0, +1} (NaN at end where forward return unavailable).
    """
    n = len(closes)
    labels = np.full(n, np.nan)

    atr = calculate_atr(highs, lows, closes, atr_period)

    for i in range(n - forward_bars):
        if np.isnan(atr[i]):
            continue

        forward_return = (closes[i + forward_bars] - closes[i]) / closes[i]
        threshold = atr_threshold_mult * (atr[i] / closes[i])  # Normalize ATR to percentage

        if forward_return > threshold:
            labels[i] = 1.0   # LONG
        elif forward_return < -threshold:
            labels[i] = -1.0  # SHORT
        else:
            labels[i] = 0.0   # FLAT

    return labels
