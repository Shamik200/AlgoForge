"""VWAP (Volume Weighted Average Price) tracker and deviation signals."""

import math
from collections import deque


class VWAPTracker:
    """Tracks cumulative VWAP within an intraday session.

    VWAP = Σ(TypicalPrice × Volume) / Σ(Volume)
    where TypicalPrice = (High + Low + Close) / 3

    The tracker resets when `reset_session()` is called (at session open).
    """

    def __init__(self, deviation_threshold: float = 1.5) -> None:
        """Initialize the VWAP tracker.

        Args:
            deviation_threshold: Number of standard deviations from VWAP
                                 before a signal fires. Default 1.5σ.
        """
        self.deviation_threshold = deviation_threshold
        self._cumulative_tp_volume: float = 0.0
        self._cumulative_volume: float = 0.0
        self._squared_deviations: list[float] = []
        self._prices: list[float] = []

    def reset_session(self) -> None:
        """Reset all accumulators for a new trading session."""
        self._cumulative_tp_volume = 0.0
        self._cumulative_volume = 0.0
        self._squared_deviations = []
        self._prices = []

    def update(self, high: float, low: float, close: float, volume: float) -> None:
        """Feed a new candle into the VWAP accumulator.

        Args:
            high: Candle high price.
            low: Candle low price.
            close: Candle close price.
            volume: Candle volume.
        """
        if volume <= 0:
            return

        typical_price = (high + low + close) / 3.0
        self._cumulative_tp_volume += typical_price * volume
        self._cumulative_volume += volume
        self._prices.append(close)

        # Track squared deviation for standard deviation calculation
        vwap = self.current_vwap
        if vwap > 0:
            self._squared_deviations.append((close - vwap) ** 2)

    @property
    def current_vwap(self) -> float:
        """Get the current session VWAP."""
        if self._cumulative_volume == 0:
            return 0.0
        return self._cumulative_tp_volume / self._cumulative_volume

    @property
    def standard_deviation(self) -> float:
        """Get the standard deviation of price deviations from VWAP."""
        if len(self._squared_deviations) < 2:
            return 0.0
        mean_sq = sum(self._squared_deviations) / len(self._squared_deviations)
        return math.sqrt(mean_sq)

    def deviation_score(self, current_price: float) -> float:
        """Calculate a normalized deviation score from VWAP.

        Returns a value in [-1.0, +1.0]:
        - Positive: price is above VWAP (extended long)
        - Negative: price is below VWAP (extended short)
        - Magnitude indicates strength of deviation relative to threshold

        A reversion signal fires when |score| approaches 1.0.

        Args:
            current_price: The current market price.

        Returns:
            Normalized deviation score bounded to [-1.0, 1.0].
        """
        vwap = self.current_vwap
        std = self.standard_deviation

        if vwap == 0 or std == 0:
            return 0.0

        # How many standard deviations away from VWAP
        z_score = (current_price - vwap) / std

        # Normalize: at threshold (e.g. 1.5σ), score = ±1.0
        # For mean reversion, we INVERT: extended UP → signal SHORT (negative)
        raw_score = -z_score / self.deviation_threshold

        return max(-1.0, min(1.0, raw_score))
