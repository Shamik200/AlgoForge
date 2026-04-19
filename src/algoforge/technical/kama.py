"""KAMA — Kaufman Adaptive Moving Average.

Adaptive trend indicator that adjusts speed based on market noise.
Replaces all 6 static EMAs (5, 9, 21, 50, 100, 200) with a single
noise-adaptive line.

Parameters: KAMA(10, 2, 30)
  - er_period=10: Efficiency Ratio lookback
  - fast_sc=2: Fast smoothing constant period (high volatility → responsive)
  - slow_sc=30: Slow smoothing constant period (low volatility → smooth)

Formula:
  ER = |close - close_n| / sum(|close_i - close_i-1|, i=1..n)
  SC = [ER * (fast_alpha - slow_alpha) + slow_alpha]^2
  KAMA_t = KAMA_(t-1) + SC * (close_t - KAMA_(t-1))
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class KAMA(Indicator):
    """Kaufman Adaptive Moving Average.

    Adapts between fast and slow EMA based on the Efficiency Ratio:
    - Trending market (high ER) → fast response
    - Choppy market (low ER) → slow, filtered response

    Usage:
        kama = KAMA(er_period=10, fast_sc=2, slow_sc=30)
        result = kama.compute(closes)
        # result.values = {"kama": [...], "er": [...]}
    """

    def __init__(
        self,
        er_period: int = 10,
        fast_sc: int = 2,
        slow_sc: int = 30,
    ) -> None:
        self._er_period = er_period
        self._fast_sc = fast_sc
        self._slow_sc = slow_sc
        # Pre-compute alpha bounds
        self._fast_alpha = 2.0 / (fast_sc + 1)
        self._slow_alpha = 2.0 / (slow_sc + 1)

    @property
    def name(self) -> str:
        return "kama"

    @property
    def lookback_period(self) -> int:
        return self._er_period + 1

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute KAMA and Efficiency Ratio values."""
        self._validate_input(closes)
        n = len(closes)

        kama = np.full(n, np.nan)
        er = np.full(n, np.nan)

        # Seed KAMA with the close at the start of the lookback
        kama[self._er_period] = closes[self._er_period]

        for i in range(self._er_period, n):
            # Direction: absolute price change over er_period
            direction = abs(closes[i] - closes[i - self._er_period])

            # Volatility: sum of absolute period-to-period changes
            volatility = np.sum(np.abs(np.diff(closes[i - self._er_period : i + 1])))

            # Efficiency Ratio (0 = choppy, 1 = trending)
            if volatility == 0:
                er[i] = 0.0
            else:
                er[i] = direction / volatility

            # Smoothing Constant: maps ER to adaptive alpha
            sc = (er[i] * (self._fast_alpha - self._slow_alpha) + self._slow_alpha) ** 2

            # Adaptive EMA step
            if i == self._er_period:
                kama[i] = closes[i]
            else:
                kama[i] = kama[i - 1] + sc * (closes[i] - kama[i - 1])

        return IndicatorResult(
            name=self.name,
            values={
                "kama": kama.tolist(),
                "er": er.tolist(),
            },
            params={
                "er_period": self._er_period,
                "fast_sc": self._fast_sc,
                "slow_sc": self._slow_sc,
            },
        )
