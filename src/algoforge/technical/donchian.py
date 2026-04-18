"""Donchian Channels.

N-period high/low breakout channels.
Upper = highest high over N periods, Lower = lowest low.

Requirements: INDI-11
Default: period=20
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class DonchianChannels(Indicator):
    """Donchian Channels for breakout detection.

    Usage:
        dc = DonchianChannels(period=20)
        result = dc.compute(closes, highs, lows)
        # result.values = {"upper": [...], "lower": [...], "middle": [...]}
    """

    def __init__(self, period: int = 20) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return "donchian"

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
        """Compute Donchian Channels."""
        if highs is None or lows is None:
            msg = "Donchian Channels requires highs and lows arrays"
            raise ValueError(msg)

        n = len(closes)
        upper = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        middle = np.full(n, np.nan)

        for i in range(self._period - 1, n):
            window_highs = highs[i - self._period + 1 : i + 1]
            window_lows = lows[i - self._period + 1 : i + 1]
            upper[i] = np.max(window_highs)
            lower[i] = np.min(window_lows)
            middle[i] = (upper[i] + lower[i]) / 2.0

        return IndicatorResult(
            name=self.name,
            values={
                "upper": upper.tolist(),
                "lower": lower.tolist(),
                "middle": middle.tolist(),
            },
            params={"period": self._period},
        )
