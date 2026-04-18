"""MACD — Moving Average Convergence Divergence.

MACD measures the relationship between two EMAs to identify
momentum changes and trend direction.

MACD Line = EMA(fast) - EMA(slow)
Signal Line = EMA(MACD Line, signal_period)
Histogram = MACD Line - Signal Line

Requirements: INDI-05
Default params: fast=12, slow=26, signal=9
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult, ema_calc


class MACD(Indicator):
    """MACD indicator with signal line and histogram.

    Usage:
        macd = MACD(fast=12, slow=26, signal=9)
        result = macd.compute(closes)
        # result.values = {"macd": [...], "signal": [...], "histogram": [...]}
    """

    def __init__(
        self, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> None:
        self._fast = fast
        self._slow = slow
        self._signal = signal

    @property
    def name(self) -> str:
        return "macd"

    @property
    def lookback_period(self) -> int:
        return self._slow + self._signal

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute MACD line, signal line, and histogram."""
        self._validate_input(closes)

        fast_ema = ema_calc(closes, self._fast)
        slow_ema = ema_calc(closes, self._slow)

        # MACD line = fast EMA - slow EMA
        macd_line = fast_ema - slow_ema

        # Signal line = EMA of MACD line
        # Need to handle NaN values — compute EMA only on valid MACD values
        valid_start = self._slow - 1  # First valid MACD value index
        macd_valid = macd_line[valid_start:]

        signal_line_valid = ema_calc(macd_valid, self._signal)

        # Pad signal line back to full length
        signal_line = np.full(len(closes), np.nan)
        signal_line[valid_start:] = signal_line_valid

        # Histogram = MACD - Signal
        histogram = macd_line - signal_line

        return IndicatorResult(
            name=self.name,
            values={
                "macd": macd_line.tolist(),
                "signal": signal_line.tolist(),
                "histogram": histogram.tolist(),
            },
            params={
                "fast": self._fast,
                "slow": self._slow,
                "signal": self._signal,
            },
        )
