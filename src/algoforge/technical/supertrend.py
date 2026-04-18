"""Supertrend indicator.

ATR-based trend-following indicator that provides clear
buy/sell signals and acts as a trailing stop.

Upper Band = (High + Low) / 2 + Multiplier × ATR
Lower Band = (High + Low) / 2 - Multiplier × ATR

Requirements: INDI-09
Default params: period=10, multiplier=3.0
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import (
    Indicator,
    IndicatorResult,
    true_range,
)


class Supertrend(Indicator):
    """Supertrend indicator with trend direction signals.

    Usage:
        st = Supertrend(period=10, multiplier=3.0)
        result = st.compute(closes, highs, lows)
        # result.values = {"supertrend": [...], "direction": [...]}
        # direction: 1.0 = bullish, -1.0 = bearish
    """

    def __init__(self, period: int = 10, multiplier: float = 3.0) -> None:
        self._period = period
        self._multiplier = multiplier

    @property
    def name(self) -> str:
        return "supertrend"

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
        """Compute Supertrend values and direction."""
        if highs is None or lows is None:
            msg = "Supertrend requires highs and lows arrays"
            raise ValueError(msg)

        self._validate_input(closes)
        n = len(closes)

        # Calculate ATR using true range
        tr = true_range(highs, lows, closes)

        # ATR as rolling mean of true range
        atr = np.full(n, np.nan)
        atr[self._period - 1] = np.mean(tr[:self._period])
        for i in range(self._period, n):
            atr[i] = (atr[i - 1] * (self._period - 1) + tr[i]) / self._period

        # HL2 midpoint
        hl2 = (highs + lows) / 2.0

        # Basic upper and lower bands
        basic_upper = hl2 + self._multiplier * atr
        basic_lower = hl2 - self._multiplier * atr

        # Final bands with trend logic
        final_upper = np.full(n, np.nan)
        final_lower = np.full(n, np.nan)
        supertrend = np.full(n, np.nan)
        direction = np.full(n, np.nan)  # 1 = bullish, -1 = bearish

        start = self._period - 1

        final_upper[start] = basic_upper[start]
        final_lower[start] = basic_lower[start]

        # Initial direction based on close vs upper band
        if closes[start] <= final_upper[start]:
            supertrend[start] = final_upper[start]
            direction[start] = -1.0
        else:
            supertrend[start] = final_lower[start]
            direction[start] = 1.0

        for i in range(start + 1, n):
            # Update final upper band
            if basic_upper[i] < final_upper[i - 1] or closes[i - 1] > final_upper[i - 1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i - 1]

            # Update final lower band
            if basic_lower[i] > final_lower[i - 1] or closes[i - 1] < final_lower[i - 1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i - 1]

            # Determine trend direction
            if direction[i - 1] == -1.0 and closes[i] > final_upper[i - 1]:
                direction[i] = 1.0
            elif direction[i - 1] == 1.0 and closes[i] < final_lower[i - 1]:
                direction[i] = -1.0
            else:
                direction[i] = direction[i - 1]

            # Set supertrend value
            if direction[i] == 1.0:
                supertrend[i] = final_lower[i]
            else:
                supertrend[i] = final_upper[i]

        return IndicatorResult(
            name=self.name,
            values={
                "supertrend": supertrend.tolist(),
                "direction": direction.tolist(),
            },
            params={
                "period": self._period,
                "multiplier": self._multiplier,
            },
        )
