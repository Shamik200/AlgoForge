"""Indicator base classes and result models.

All 14 technical indicators inherit from the Indicator ABC.
Results are returned as IndicatorResult Pydantic models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class IndicatorResult(BaseModel):
    """Unified result model for all indicators.

    Every indicator returns this same shape — downstream consumers
    don't need to know which indicator produced the result.

    Attributes:
        name: Indicator identifier (e.g., "ema_21", "rsi_14")
        values: Dict of named series. Single-value indicators have one key,
                multi-value (MACD, Bollinger) have multiple.
        params: Parameters used for computation (for audit/reproducibility)
        timestamp: When this result was computed
        metadata: Indicator-specific extra data
    """

    name: str = Field(..., min_length=1)
    values: dict[str, list[float]] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def latest(self) -> dict[str, float]:
        """Get the most recent value for each series."""
        return {k: v[-1] for k, v in self.values.items() if v}

    @property
    def is_empty(self) -> bool:
        """True if no values computed."""
        return not self.values or all(len(v) == 0 for v in self.values.values())


class Indicator(ABC):
    """Abstract base class for all technical indicators.

    Each indicator:
    - Declares its lookback_period (how many candles it needs)
    - Implements compute() that takes NumPy arrays and returns IndicatorResult
    - Is stateless — state lives in IndicatorEngine's caches

    Usage:
        class EMA(Indicator):
            def compute(self, closes, ...) -> IndicatorResult: ...
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique indicator identifier (e.g., 'ema', 'rsi', 'macd')."""
        ...

    @property
    @abstractmethod
    def lookback_period(self) -> int:
        """Minimum number of candles needed for first valid output."""
        ...

    @abstractmethod
    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute indicator values from OHLCV arrays.

        Args:
            closes: Array of close prices (required by all indicators)
            highs: Array of high prices (needed by ATR, ADX, etc.)
            lows: Array of low prices
            volumes: Array of volumes (needed by OBV, VWAP, etc.)
            opens: Array of open prices (needed by some indicators)

        Returns:
            IndicatorResult with computed values.
        """
        ...

    def _validate_input(self, data: np.ndarray, min_length: int | None = None) -> None:
        """Validate input array has sufficient data."""
        required = min_length or self.lookback_period
        if len(data) < required:
            msg = (
                f"{self.name} requires at least {required} data points, "
                f"got {len(data)}"
            )
            raise ValueError(msg)


def ema_calc(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average — core building block.

    Used by EMA, MACD, ADX, Keltner, Supertrend, and others.
    Uses the standard EMA formula: EMA_t = close_t * k + EMA_(t-1) * (1-k)
    where k = 2 / (period + 1).

    Args:
        data: Input price array
        period: EMA period

    Returns:
        Array of EMA values (same length as input, NaN-padded at start)
    """
    if len(data) < period:
        return np.full(len(data), np.nan)

    k = 2.0 / (period + 1)
    result = np.full(len(data), np.nan)

    # Seed with SMA of first `period` values
    result[period - 1] = np.mean(data[:period])

    # Recursive EMA from period onwards
    for i in range(period, len(data)):
        result[i] = data[i] * k + result[i - 1] * (1 - k)

    return result


def true_range(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
    """Calculate True Range — used by ATR, ADX, Supertrend, Keltner.

    TR = max(high - low, |high - prev_close|, |low - prev_close|)

    Returns:
        Array of TR values (first value is high - low, rest use prev close).
    """
    tr = np.empty(len(highs))
    tr[0] = highs[0] - lows[0]

    for i in range(1, len(highs)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    return tr
