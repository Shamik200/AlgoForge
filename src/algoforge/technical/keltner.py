"""Keltner Channels.

Volatility envelope around an EMA using ATR.
Used with Bollinger Bands for squeeze detection (BB inside KC = squeeze).

Requirements: INDI-07
Default: period=20, multiplier=1.5
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import (
    Indicator,
    IndicatorResult,
    ema_calc,
    true_range,
)


class KeltnerChannels(Indicator):
    """Keltner Channels — EMA ± multiplier × ATR.

    Usage:
        kc = KeltnerChannels(period=20, multiplier=1.5)
        result = kc.compute(closes, highs, lows)
        # result.values = {"upper": [...], "middle": [...], "lower": [...]}
    """

    def __init__(self, period: int = 20, multiplier: float = 1.5) -> None:
        self._period = period
        self._multiplier = multiplier

    @property
    def name(self) -> str:
        return "keltner"

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
        """Compute Keltner Channels."""
        if highs is None or lows is None:
            msg = "Keltner Channels requires highs and lows arrays"
            raise ValueError(msg)

        self._validate_input(closes)

        # Middle band = EMA of closes
        middle = ema_calc(closes, self._period)

        # ATR for channel width
        tr = true_range(highs, lows, closes)
        atr = np.full(len(closes), np.nan)
        atr[self._period - 1] = np.mean(tr[:self._period])
        for i in range(self._period, len(closes)):
            atr[i] = (atr[i - 1] * (self._period - 1) + tr[i]) / self._period

        upper = middle + self._multiplier * atr
        lower = middle - self._multiplier * atr

        return IndicatorResult(
            name=self.name,
            values={
                "upper": upper.tolist(),
                "middle": middle.tolist(),
                "lower": lower.tolist(),
            },
            params={"period": self._period, "multiplier": self._multiplier},
        )
