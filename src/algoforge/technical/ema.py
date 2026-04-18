"""Exponential Moving Average (EMA) indicator.

Computes EMA for multiple periods simultaneously.
EMA gives more weight to recent prices, making it more responsive
than SMA for trend detection and crossover signals.

Requirements: INDI-01
Default periods: 5, 9, 21, 50, 100, 200
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult, ema_calc


class EMA(Indicator):
    """Exponential Moving Average indicator.

    Computes EMA for all configured periods in a single pass.
    Used directly by strategies (EMA alignment, crossovers) and
    as a building block inside MACD, Keltner, etc.

    Usage:
        ema = EMA(periods=[5, 9, 21, 50, 100, 200])
        result = ema.compute(closes)
        # result.values = {"ema_5": [...], "ema_9": [...], ...}
    """

    def __init__(self, periods: list[int] | None = None) -> None:
        self._periods = periods or [5, 9, 21, 50, 100, 200]

    @property
    def name(self) -> str:
        return "ema"

    @property
    def lookback_period(self) -> int:
        return max(self._periods)

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute EMA for all configured periods.

        Returns IndicatorResult with values like:
            {"ema_5": [...], "ema_9": [...], "ema_21": [...], ...}
        """
        self._validate_input(closes)

        values: dict[str, list[float]] = {}
        for period in self._periods:
            ema_values = ema_calc(closes, period)
            values[f"ema_{period}"] = ema_values.tolist()

        return IndicatorResult(
            name=self.name,
            values=values,
            params={"periods": self._periods},
        )

    @property
    def periods(self) -> list[int]:
        """Configured EMA periods."""
        return self._periods
