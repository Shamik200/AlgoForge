"""ADX — Average Directional Index with +DI/-DI.

Measures trend strength (not direction). ADX > 25 = trending, < 20 = range.
+DI and -DI show trend direction.

Requirements: INDI-03
Default: period=14
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class ADX(Indicator):
    """ADX/DMI trend strength indicator.

    Usage:
        adx = ADX(period=14)
        result = adx.compute(closes, highs, lows)
        # result.values = {"adx": [...], "plus_di": [...], "minus_di": [...]}
    """

    def __init__(self, period: int = 14) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return "adx"

    @property
    def lookback_period(self) -> int:
        return self._period * 2  # Need 2x period for ADX smoothing

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute ADX, +DI, and -DI."""
        if highs is None or lows is None:
            msg = "ADX requires highs and lows arrays"
            raise ValueError(msg)

        self._validate_input(closes)
        n = len(closes)
        p = self._period

        # True Range
        tr = np.empty(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i - 1])
            lc = abs(lows[i] - closes[i - 1])
            tr[i] = max(hl, hc, lc)

        # Directional Movement
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)
        for i in range(1, n):
            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]

            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move

        # Smoothed TR, +DM, -DM using Wilder's smoothing
        smoothed_tr = np.full(n, np.nan)
        smoothed_plus_dm = np.full(n, np.nan)
        smoothed_minus_dm = np.full(n, np.nan)

        smoothed_tr[p] = np.sum(tr[1:p + 1])
        smoothed_plus_dm[p] = np.sum(plus_dm[1:p + 1])
        smoothed_minus_dm[p] = np.sum(minus_dm[1:p + 1])

        for i in range(p + 1, n):
            smoothed_tr[i] = smoothed_tr[i - 1] - (smoothed_tr[i - 1] / p) + tr[i]
            smoothed_plus_dm[i] = smoothed_plus_dm[i - 1] - (smoothed_plus_dm[i - 1] / p) + plus_dm[i]
            smoothed_minus_dm[i] = smoothed_minus_dm[i - 1] - (smoothed_minus_dm[i - 1] / p) + minus_dm[i]

        # +DI and -DI
        plus_di = np.full(n, np.nan)
        minus_di = np.full(n, np.nan)
        dx = np.full(n, np.nan)

        for i in range(p, n):
            if smoothed_tr[i] != 0:
                plus_di[i] = 100.0 * smoothed_plus_dm[i] / smoothed_tr[i]
                minus_di[i] = 100.0 * smoothed_minus_dm[i] / smoothed_tr[i]
            else:
                plus_di[i] = 0.0
                minus_di[i] = 0.0

            di_sum = plus_di[i] + minus_di[i]
            if di_sum != 0:
                dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum
            else:
                dx[i] = 0.0

        # ADX = smoothed DX
        adx = np.full(n, np.nan)
        start = 2 * p - 1  # First valid ADX index
        if start < n:
            # First ADX is average of first `period` DX values
            dx_slice = dx[p:2 * p]
            valid_dx = dx_slice[~np.isnan(dx_slice)]
            if len(valid_dx) > 0:
                adx[start] = np.mean(valid_dx)

                for i in range(start + 1, n):
                    adx[i] = (adx[i - 1] * (p - 1) + dx[i]) / p

        return IndicatorResult(
            name=self.name,
            values={
                "adx": adx.tolist(),
                "plus_di": plus_di.tolist(),
                "minus_di": minus_di.tolist(),
            },
            params={"period": self._period},
        )
