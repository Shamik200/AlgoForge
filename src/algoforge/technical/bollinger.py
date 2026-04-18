"""Bollinger Bands.

Volatility bands placed above and below a moving average.
Squeeze detection: when bandwidth contracts, a breakout is imminent.

Requirements: INDI-06
Default: period=20, std_dev=2.0
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class BollingerBands(Indicator):
    """Bollinger Bands with squeeze detection.

    Usage:
        bb = BollingerBands(period=20, std_dev=2.0)
        result = bb.compute(closes)
        # result.values = {"upper": [...], "middle": [...], "lower": [...],
        #                   "bandwidth": [...], "pct_b": [...]}
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0) -> None:
        self._period = period
        self._std_dev = std_dev

    @property
    def name(self) -> str:
        return "bollinger"

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
        """Compute Bollinger Bands."""
        self._validate_input(closes)
        n = len(closes)

        middle = np.full(n, np.nan)
        upper = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        bandwidth = np.full(n, np.nan)
        pct_b = np.full(n, np.nan)

        for i in range(self._period - 1, n):
            window = closes[i - self._period + 1 : i + 1]
            sma = np.mean(window)
            std = np.std(window, ddof=0)  # Population std dev (standard for BB)

            middle[i] = sma
            upper[i] = sma + self._std_dev * std
            lower[i] = sma - self._std_dev * std

            # Bandwidth = (upper - lower) / middle
            if sma > 0:
                bandwidth[i] = (upper[i] - lower[i]) / middle[i]

            # %B = (close - lower) / (upper - lower)
            band_width = upper[i] - lower[i]
            if band_width > 0:
                pct_b[i] = (closes[i] - lower[i]) / band_width

        return IndicatorResult(
            name=self.name,
            values={
                "upper": upper.tolist(),
                "middle": middle.tolist(),
                "lower": lower.tolist(),
                "bandwidth": bandwidth.tolist(),
                "pct_b": pct_b.tolist(),
            },
            params={"period": self._period, "std_dev": self._std_dev},
        )
