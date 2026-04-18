"""Stochastic Oscillator.

Momentum indicator comparing close to its price range over a period.
%K < 20 = oversold, %K > 80 = overbought.

Requirements: INDI-10
Default: k_period=14, d_period=3, smooth=3
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class Stochastic(Indicator):
    """Stochastic Oscillator (%K and %D).

    Usage:
        stoch = Stochastic(k_period=14, d_period=3, smooth=3)
        result = stoch.compute(closes, highs, lows)
        # result.values = {"k": [...], "d": [...]}
    """

    def __init__(
        self, k_period: int = 14, d_period: int = 3, smooth: int = 3
    ) -> None:
        self._k_period = k_period
        self._d_period = d_period
        self._smooth = smooth

    @property
    def name(self) -> str:
        return "stochastic"

    @property
    def lookback_period(self) -> int:
        return self._k_period + self._d_period

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute Stochastic %K and %D."""
        if highs is None or lows is None:
            msg = "Stochastic requires highs and lows arrays"
            raise ValueError(msg)

        self._validate_input(closes)
        n = len(closes)

        # Fast %K
        fast_k = np.full(n, np.nan)
        for i in range(self._k_period - 1, n):
            window_high = np.max(highs[i - self._k_period + 1 : i + 1])
            window_low = np.min(lows[i - self._k_period + 1 : i + 1])
            hl_range = window_high - window_low
            if hl_range > 0:
                fast_k[i] = 100.0 * (closes[i] - window_low) / hl_range
            else:
                fast_k[i] = 50.0  # Neutral when range is zero

        # Slow %K = SMA of Fast %K (smoothing)
        slow_k = np.full(n, np.nan)
        for i in range(self._k_period + self._smooth - 2, n):
            window = fast_k[i - self._smooth + 1 : i + 1]
            valid = window[~np.isnan(window)]
            if len(valid) > 0:
                slow_k[i] = np.mean(valid)

        # %D = SMA of Slow %K
        d_line = np.full(n, np.nan)
        for i in range(self._k_period + self._smooth + self._d_period - 3, n):
            window = slow_k[i - self._d_period + 1 : i + 1]
            valid = window[~np.isnan(window)]
            if len(valid) > 0:
                d_line[i] = np.mean(valid)

        return IndicatorResult(
            name=self.name,
            values={
                "k": slow_k.tolist(),
                "d": d_line.tolist(),
            },
            params={
                "k_period": self._k_period,
                "d_period": self._d_period,
                "smooth": self._smooth,
            },
        )
