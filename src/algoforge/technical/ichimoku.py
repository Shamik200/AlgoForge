"""Ichimoku Cloud (Ichimoku Kinko Hyo).

Multi-factor analysis system with 5 lines providing support/resistance,
trend direction, and momentum across multiple timeframes in one view.

Requirements: INDI-14
Default: tenkan=9, kijun=26, senkou_b=52
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class Ichimoku(Indicator):
    """Ichimoku Cloud indicator.

    Components:
    - Tenkan-sen (Conversion): (9-period high + low) / 2
    - Kijun-sen (Base): (26-period high + low) / 2
    - Senkou Span A (Leading A): (Tenkan + Kijun) / 2, projected 26 periods ahead
    - Senkou Span B (Leading B): (52-period high + low) / 2, projected 26 periods ahead
    - Chikou Span (Lagging): Close projected 26 periods back

    Usage:
        ichi = Ichimoku(tenkan=9, kijun=26, senkou_b=52)
        result = ichi.compute(closes, highs, lows)
    """

    def __init__(
        self, tenkan: int = 9, kijun: int = 26, senkou_b: int = 52
    ) -> None:
        self._tenkan = tenkan
        self._kijun = kijun
        self._senkou_b = senkou_b

    @property
    def name(self) -> str:
        return "ichimoku"

    @property
    def lookback_period(self) -> int:
        return self._senkou_b

    def _midpoint(self, highs: np.ndarray, lows: np.ndarray, period: int) -> np.ndarray:
        """Calculate (highest high + lowest low) / 2 over period."""
        n = len(highs)
        result = np.full(n, np.nan)
        for i in range(period - 1, n):
            window_h = highs[i - period + 1 : i + 1]
            window_l = lows[i - period + 1 : i + 1]
            result[i] = (np.max(window_h) + np.min(window_l)) / 2.0
        return result

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute all 5 Ichimoku components."""
        if highs is None or lows is None:
            msg = "Ichimoku requires highs and lows arrays"
            raise ValueError(msg)

        self._validate_input(closes)
        n = len(closes)

        # Tenkan-sen (Conversion Line)
        tenkan = self._midpoint(highs, lows, self._tenkan)

        # Kijun-sen (Base Line)
        kijun = self._midpoint(highs, lows, self._kijun)

        # Senkou Span A (Leading Span A) — projected kijun periods ahead
        senkou_a = np.full(n, np.nan)
        for i in range(n):
            if not np.isnan(tenkan[i]) and not np.isnan(kijun[i]):
                target = i + self._kijun
                if target < n:
                    senkou_a[target] = (tenkan[i] + kijun[i]) / 2.0

        # Senkou Span B (Leading Span B) — projected kijun periods ahead
        senkou_b_line = self._midpoint(highs, lows, self._senkou_b)
        senkou_b = np.full(n, np.nan)
        for i in range(n):
            if not np.isnan(senkou_b_line[i]):
                target = i + self._kijun
                if target < n:
                    senkou_b[target] = senkou_b_line[i]

        # Chikou Span (Lagging) — close projected kijun periods back
        chikou = np.full(n, np.nan)
        for i in range(self._kijun, n):
            chikou[i - self._kijun] = closes[i]

        return IndicatorResult(
            name=self.name,
            values={
                "tenkan": tenkan.tolist(),
                "kijun": kijun.tolist(),
                "senkou_a": senkou_a.tolist(),
                "senkou_b": senkou_b.tolist(),
                "chikou": chikou.tolist(),
            },
            params={
                "tenkan_period": self._tenkan,
                "kijun_period": self._kijun,
                "senkou_b_period": self._senkou_b,
            },
        )
