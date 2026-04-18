"""IndicatorEngine — Orchestrates all 14 indicators.

Subscribes to MarketDataEvent, computes all indicators for a symbol/timeframe,
caches results in-memory, and publishes IndicatorUpdateEvent.

This is the single entry point for all indicator computation downstream.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import structlog

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.technical.adx import ADX
from algoforge.technical.atr import ATR
from algoforge.technical.bollinger import BollingerBands
from algoforge.technical.donchian import DonchianChannels
from algoforge.technical.ema import EMA
from algoforge.technical.ichimoku import Ichimoku
from algoforge.technical.indicator_base import Indicator, IndicatorResult
from algoforge.technical.keltner import KeltnerChannels
from algoforge.technical.macd import MACD
from algoforge.technical.obv import OBV
from algoforge.technical.rsi import RSI
from algoforge.technical.stochastic import Stochastic
from algoforge.technical.supertrend import Supertrend
from algoforge.technical.volume_profile import VolumeProfile
from algoforge.technical.vwap import VWAP

logger = structlog.get_logger(__name__)


class IndicatorSnapshot:
    """Complete indicator state for one symbol/timeframe pair.

    Holds all 14 indicator results, providing a consistent view
    for downstream strategies to consume.
    """

    def __init__(self) -> None:
        self._results: dict[str, IndicatorResult] = {}
        self._computed_at: float = 0.0

    def set(self, name: str, result: IndicatorResult) -> None:
        """Store an indicator result."""
        self._results[name] = result

    def get(self, name: str) -> IndicatorResult | None:
        """Retrieve an indicator result by name."""
        return self._results.get(name)

    @property
    def results(self) -> dict[str, IndicatorResult]:
        """All indicator results."""
        return dict(self._results)

    @property
    def computed_at(self) -> float:
        """Timestamp when this snapshot was computed."""
        return self._computed_at

    @computed_at.setter
    def computed_at(self, value: float) -> None:
        self._computed_at = value

    @property
    def indicator_names(self) -> list[str]:
        """Names of indicators with computed results."""
        return list(self._results.keys())

    def latest_values(self) -> dict[str, dict[str, float]]:
        """Get the most recent value from each indicator."""
        return {
            name: result.latest
            for name, result in self._results.items()
            if not result.is_empty
        }


class IndicatorEngine:
    """Orchestrates computation of all 14 technical indicators.

    Central hub for indicator management:
    - Registers all indicators with configurable parameters
    - Computes all indicators when new candle data arrives
    - Caches results in-memory (keyed by symbol:timeframe)
    - Publishes batched IndicatorUpdateEvent via event bus

    Usage:
        engine = IndicatorEngine(config_params)
        snapshot = engine.compute(series)
        latest = snapshot.latest_values()
    """

    def __init__(
        self,
        ema_periods: list[int] | None = None,
        rsi_period: int = 14,
        adx_period: int = 14,
        atr_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        kc_period: int = 20,
        kc_multiplier: float = 1.5,
        st_period: int = 10,
        st_multiplier: float = 3.0,
        stoch_k: int = 14,
        stoch_d: int = 3,
        stoch_smooth: int = 3,
        donchian_period: int = 20,
        ichimoku_tenkan: int = 9,
        ichimoku_kijun: int = 26,
        ichimoku_senkou: int = 52,
    ) -> None:
        """Initialize with configurable parameters for all indicators."""
        self._indicators: list[Indicator] = [
            EMA(periods=ema_periods or [5, 9, 21, 50, 100, 200]),
            RSI(period=rsi_period),
            ADX(period=adx_period),
            ATR(period=atr_period),
            MACD(fast=macd_fast, slow=macd_slow, signal=macd_signal),
            BollingerBands(period=bb_period, std_dev=bb_std),
            KeltnerChannels(period=kc_period, multiplier=kc_multiplier),
            VWAP(),
            Supertrend(period=st_period, multiplier=st_multiplier),
            Stochastic(k_period=stoch_k, d_period=stoch_d, smooth=stoch_smooth),
            DonchianChannels(period=donchian_period),
            VolumeProfile(),
            OBV(),
            Ichimoku(tenkan=ichimoku_tenkan, kijun=ichimoku_kijun, senkou_b=ichimoku_senkou),
        ]

        # Cache: {symbol}:{timeframe} -> IndicatorSnapshot
        self._cache: dict[str, IndicatorSnapshot] = {}

        # Performance stats
        self._total_computations = 0
        self._total_time_ms = 0.0

    @property
    def indicators(self) -> list[Indicator]:
        """Registered indicators."""
        return list(self._indicators)

    @property
    def indicator_count(self) -> int:
        """Number of registered indicators."""
        return len(self._indicators)

    @property
    def cache_size(self) -> int:
        """Number of cached symbol/timeframe pairs."""
        return len(self._cache)

    @property
    def stats(self) -> dict[str, Any]:
        """Performance statistics."""
        avg_ms = (
            self._total_time_ms / self._total_computations
            if self._total_computations > 0
            else 0.0
        )
        return {
            "total_computations": self._total_computations,
            "total_time_ms": round(self._total_time_ms, 2),
            "avg_time_ms": round(avg_ms, 2),
            "cache_size": self.cache_size,
        }

    def _cache_key(self, symbol: str, timeframe: Timeframe) -> str:
        """Generate cache key for a symbol/timeframe pair."""
        return f"{symbol}:{timeframe.value}"

    def compute(self, series: OHLCVSeries) -> IndicatorSnapshot:
        """Compute all indicators for an OHLCV series.

        Args:
            series: Candle data for a single symbol/timeframe.

        Returns:
            IndicatorSnapshot with all computed indicator results.
        """
        start = time.perf_counter()
        snapshot = IndicatorSnapshot()

        if series.is_empty:
            logger.warning(
                "empty_series_skipped",
                symbol=series.symbol,
                timeframe=series.timeframe.value,
            )
            return snapshot

        # Convert to NumPy arrays once
        closes = np.array(series.closes, dtype=np.float64)
        highs = np.array(series.highs, dtype=np.float64)
        lows = np.array(series.lows, dtype=np.float64)
        volumes = np.array(series.volumes, dtype=np.float64)
        opens = np.array([c.open for c in series.candles], dtype=np.float64)

        for indicator in self._indicators:
            try:
                if len(closes) < indicator.lookback_period:
                    logger.debug(
                        "insufficient_data",
                        indicator=indicator.name,
                        required=indicator.lookback_period,
                        available=len(closes),
                    )
                    continue

                result = indicator.compute(
                    closes=closes,
                    highs=highs,
                    lows=lows,
                    volumes=volumes,
                    opens=opens,
                )
                snapshot.set(indicator.name, result)

            except Exception as exc:
                logger.error(
                    "indicator_compute_error",
                    indicator=indicator.name,
                    symbol=series.symbol,
                    error=str(exc),
                )

        # Cache the snapshot
        key = self._cache_key(series.symbol, series.timeframe)
        snapshot.computed_at = time.perf_counter()
        self._cache[key] = snapshot

        elapsed_ms = (time.perf_counter() - start) * 1000
        self._total_computations += 1
        self._total_time_ms += elapsed_ms

        logger.info(
            "indicators_computed",
            symbol=series.symbol,
            timeframe=series.timeframe.value,
            indicators=len(snapshot.indicator_names),
            elapsed_ms=round(elapsed_ms, 2),
        )

        return snapshot

    def get_cached(self, symbol: str, timeframe: Timeframe) -> IndicatorSnapshot | None:
        """Retrieve cached indicator snapshot."""
        return self._cache.get(self._cache_key(symbol, timeframe))

    def clear_cache(self, symbol: str | None = None) -> None:
        """Clear indicator cache.

        Args:
            symbol: If provided, clear only this symbol's cache.
                    If None, clear entire cache.
        """
        if symbol is None:
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{symbol}:")]
            for k in keys_to_remove:
                del self._cache[k]

    def compute_batch(self, series_list: list[OHLCVSeries]) -> list[IndicatorSnapshot]:
        """Compute indicators for multiple series.

        Used for batch processing multiple instruments/timeframes.
        """
        return [self.compute(series) for series in series_list]
