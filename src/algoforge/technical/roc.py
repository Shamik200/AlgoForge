"""ROC — Rate of Change.

Pure momentum oscillator measuring the percentage change between
the current close and the close N periods ago.

Replaces RSI/Stochastic/MACD for directional momentum signals
(RSI is kept separately but ONLY for divergence detection).

Parameters: ROC(14)
  - period=14: Lookback period

Formula:
  ROC = ((close - close_n) / close_n) * 100
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class ROC(Indicator):
    """Rate of Change — pure momentum indicator.

    Positive ROC = upward momentum, Negative = downward.
    Magnitude indicates strength of momentum.

    Usage:
        roc = ROC(period=14)
        result = roc.compute(closes)
        # result.values = {"roc": [...]}
    """

    def __init__(self, period: int = 14) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return "roc"

    @property
    def lookback_period(self) -> int:
        return self._period + 1

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute Rate of Change values."""
        self._validate_input(closes)
        n = len(closes)

        roc = np.full(n, np.nan)

        for i in range(self._period, n):
            prev_close = closes[i - self._period]
            if prev_close != 0:
                roc[i] = ((closes[i] - prev_close) / prev_close) * 100.0
            else:
                roc[i] = 0.0

        return IndicatorResult(
            name=self.name,
            values={"roc": roc.tolist()},
            params={"period": self._period},
        )
