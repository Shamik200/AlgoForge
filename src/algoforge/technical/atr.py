"""ATR — Average True Range.

Measures market volatility. Used for stop-loss sizing,
position sizing, and as a building block in Keltner Channels and Supertrend.

Requirements: INDI-04
Default: period=14
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import (
    Indicator,
    IndicatorResult,
    true_range,
)


class ATR(Indicator):
    """Average True Range volatility indicator.

    Uses Wilder's smoothing for the ATR calculation.

    Usage:
        atr = ATR(period=14)
        result = atr.compute(closes, highs, lows)
        # result.values = {"atr": [...]}
    """

    def __init__(self, period: int = 14) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return "atr"

    @property
    def lookback_period(self) -> int:
        return self._period

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute ATR values."""
        if highs is None or lows is None:
            msg = "ATR requires highs and lows arrays"
            raise ValueError(msg)

        self._validate_input(closes)

        tr = true_range(highs, lows, closes)
        n = len(closes)
        atr = np.full(n, np.nan)

        # First ATR is SMA of first N true ranges
        atr[self._period - 1] = np.mean(tr[:self._period])

        # Wilder's smoothing
        for i in range(self._period, n):
            atr[i] = (atr[i - 1] * (self._period - 1) + tr[i]) / self._period

        return IndicatorResult(
            name=self.name,
            values={"atr": atr.tolist()},
            params={"period": self._period},
        )
