"""RSI — Relative Strength Index.

Momentum oscillator measuring speed/magnitude of price changes.
Values range 0-100. Overbought > 70, Oversold < 30.

Requirements: INDI-02
Default: period=14
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class RSI(Indicator):
    """Relative Strength Index.

    Uses Wilder's smoothing (exponential with alpha = 1/period).

    Usage:
        rsi = RSI(period=14)
        result = rsi.compute(closes)
        # result.values = {"rsi": [...]}
    """

    def __init__(self, period: int = 14) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return "rsi"

    @property
    def lookback_period(self) -> int:
        return self._period + 1  # Need period+1 prices for period changes

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute RSI values."""
        self._validate_input(closes)
        n = len(closes)

        # Price changes
        deltas = np.diff(closes)

        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Initial average gain/loss (SMA of first period)
        avg_gain = np.mean(gains[:self._period])
        avg_loss = np.mean(losses[:self._period])

        rsi = np.full(n, np.nan)

        # First RSI value
        if avg_loss == 0:
            rsi[self._period] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[self._period] = 100.0 - (100.0 / (1.0 + rs))

        # Subsequent values using Wilder's smoothing
        for i in range(self._period + 1, n):
            idx = i - 1  # Index into gains/losses (which are diff'd, so 1 shorter)
            avg_gain = (avg_gain * (self._period - 1) + gains[idx]) / self._period
            avg_loss = (avg_loss * (self._period - 1) + losses[idx]) / self._period

            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100.0 - (100.0 / (1.0 + rs))

        return IndicatorResult(
            name=self.name,
            values={"rsi": rsi.tolist()},
            params={"period": self._period},
        )
