"""IndicatorEngine v2 — Two-tier Orthogonal Indicator Engine.

7 core orthogonal indicators (always computed):
  1. KAMA (10, 2, 30) — adaptive trend direction
  2. ADX/DMI (14) — trend strength
  3. ROC (14) — pure momentum
  4. ATR (14) — volatility state
  5. Bollinger %B (20, 2σ) — volatility extremes
  6. OBV — volume-price divergence
  7. VWAP — institutional fair value
  8. RSI (14) — divergence detection ONLY

Supporting tools (optional, configurable):
  - Donchian Channels (20)
  - Keltner Channels (20, 1.5×ATR)
  - Volume Profile

Subscribes to MarketDataEvent, computes indicators for a symbol/timeframe,
caches results in-memory, and publishes IndicatorUpdateEvent.
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
from algoforge.technical.indicator_base import Indicator, IndicatorResult
from algoforge.technical.kama import KAMA
from algoforge.technical.keltner import KeltnerChannels
from algoforge.technical.obv import OBV
from algoforge.technical.roc import ROC
from algoforge.technical.rsi import RSI
from algoforge.technical.volume_profile import VolumeProfile
from algoforge.technical.vwap import VWAP

logger = structlog.get_logger(__name__)

# Registry of available supporting tools
SUPPORTING_TOOLS: dict[str, type[Indicator]] = {
    "donchian": DonchianChannels,
    "keltner": KeltnerChannels,
    "volume_profile": VolumeProfile,
}


class IndicatorSnapshot:
    """Complete indicator state for one symbol/timeframe pair.

    Holds all indicator results, providing a consistent view
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
    """Two-tier orthogonal indicator engine.

    Tier 1 (Core): 8 orthogonal indicators — ALWAYS computed.
    Tier 2 (Tools): Optional supporting tools — configurable.

    Central hub for indicator management:
    - Registers core indicators with fixed parameters
    - Optionally registers supporting tools
    - Computes all active indicators when new candle data arrives
    - Caches results in-memory (keyed by symbol:timeframe)

    Usage:
        # Core only (default)
        engine = IndicatorEngine()

        # Core + specific tools
        engine = IndicatorEngine(include_tools=["donchian", "keltner"])

        # Core + all tools
        engine = IndicatorEngine(include_tools=list(SUPPORTING_TOOLS.keys()))

        snapshot = engine.compute(series)
        latest = snapshot.latest_values()
    """

    def __init__(
        self,
        # KAMA params
        kama_er_period: int = 10,
        kama_fast_sc: int = 2,
        kama_slow_sc: int = 30,
        # Core indicator params
        rsi_period: int = 14,
        adx_period: int = 14,
        atr_period: int = 14,
        roc_period: int = 14,
        bb_period: int = 20,
        bb_std: float = 2.0,
        # Supporting tool params
        kc_period: int = 20,
        kc_multiplier: float = 1.5,
        donchian_period: int = 20,
        # Tool selection
        include_tools: list[str] | None = None,
    ) -> None:
        """Initialize with configurable parameters.

        Args:
            include_tools: List of supporting tool names to include.
                Options: "donchian", "keltner", "volume_profile".
                None = core indicators only (default).
        """
        # Tier 1: Core orthogonal indicators (ALWAYS computed)
        self._core_indicators: list[Indicator] = [
            KAMA(er_period=kama_er_period, fast_sc=kama_fast_sc, slow_sc=kama_slow_sc),
            EMA(periods=[5, 9, 21, 50, 100, 200]),
            ADX(period=adx_period),
            ROC(period=roc_period),
            ATR(period=atr_period),
            BollingerBands(period=bb_period, std_dev=bb_std),
            OBV(),
            VWAP(),
            RSI(period=rsi_period),
        ]

        # Tier 2: Supporting tools (optional)
        self._tool_indicators: list[Indicator] = []
        if include_tools:
            for tool_name in include_tools:
                if tool_name == "donchian":
                    self._tool_indicators.append(DonchianChannels(period=donchian_period))
                elif tool_name == "keltner":
                    self._tool_indicators.append(KeltnerChannels(period=kc_period, multiplier=kc_multiplier))
                elif tool_name == "volume_profile":
                    self._tool_indicators.append(VolumeProfile())
                else:
                    logger.warning("unknown_tool", tool=tool_name, available=list(SUPPORTING_TOOLS.keys()))

        # All active indicators
        self._indicators: list[Indicator] = self._core_indicators + self._tool_indicators

        # Cache: {symbol}:{timeframe} -> IndicatorSnapshot
        self._cache: dict[str, IndicatorSnapshot] = {}

        # Performance stats
        self._total_computations = 0
        self._total_time_ms = 0.0

    @property
    def indicators(self) -> list[Indicator]:
        """All active indicators (core + tools)."""
        return list(self._indicators)

    @property
    def core_indicators(self) -> list[Indicator]:
        """Core orthogonal indicators only."""
        return list(self._core_indicators)

    @property
    def tool_indicators(self) -> list[Indicator]:
        """Optional supporting tools only."""
        return list(self._tool_indicators)

    @property
    def indicator_count(self) -> int:
        """Number of active indicators."""
        return len(self._indicators)

    @property
    def core_count(self) -> int:
        """Number of core indicators."""
        return len(self._core_indicators)

    @property
    def tool_count(self) -> int:
        """Number of active supporting tools."""
        return len(self._tool_indicators)

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
            "core_count": self.core_count,
            "tool_count": self.tool_count,
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
            core=self.core_count,
            tools=self.tool_count,
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
