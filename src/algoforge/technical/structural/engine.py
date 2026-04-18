"""StructuralEngine — Orchestrates S/R, trendlines, and trend analysis.

Single entry point for all structural analysis. Coordinates:
- SRDetector → find S/R levels
- TrendlineBuilder → construct trendlines
- TrendAnalyzer → determine trend direction + channels
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCVSeries
from algoforge.technical.structural.models import StructuralSnapshot, TrendDirection
from algoforge.technical.structural.sr_detector import SRDetector
from algoforge.technical.structural.trendline_builder import TrendlineBuilder
from algoforge.technical.structural.trend_analyzer import TrendAnalyzer

logger = structlog.get_logger(__name__)


class StructuralEngine:
    """Orchestrates all structural analysis components.

    Usage:
        engine = StructuralEngine()
        snapshot = engine.analyze(series, ema_values=ema_result.values)
    """

    def __init__(
        self,
        sr_detector: SRDetector | None = None,
        trendline_builder: TrendlineBuilder | None = None,
        trend_analyzer: TrendAnalyzer | None = None,
    ) -> None:
        self._sr_detector = sr_detector or SRDetector()
        self._trendline_builder = trendline_builder or TrendlineBuilder()
        self._trend_analyzer = trend_analyzer or TrendAnalyzer()
        self._cache: dict[str, StructuralSnapshot] = {}
        self._total_analyses = 0
        self._total_time_ms = 0.0

    @property
    def stats(self) -> dict[str, Any]:
        """Performance statistics."""
        avg_ms = (
            self._total_time_ms / self._total_analyses
            if self._total_analyses > 0
            else 0.0
        )
        return {
            "total_analyses": self._total_analyses,
            "total_time_ms": round(self._total_time_ms, 2),
            "avg_time_ms": round(avg_ms, 2),
            "cache_size": len(self._cache),
        }

    def _cache_key(self, symbol: str, timeframe: Timeframe) -> str:
        return f"{symbol}:{timeframe.value}"

    def analyze(
        self,
        series: OHLCVSeries,
        ema_values: dict[str, list[float]] | None = None,
        atr_values: list[float] | None = None,
    ) -> StructuralSnapshot:
        """Run full structural analysis on an OHLCV series.

        Args:
            series: Candle data
            ema_values: EMA values from indicator engine (for trend confirmation)
            atr_values: ATR values (for trendline break threshold)

        Returns:
            StructuralSnapshot with S/R levels, trendlines, channels, trend direction.
        """
        start = time.perf_counter()

        if series.is_empty or series.count < 10:
            return StructuralSnapshot(symbol=series.symbol)

        highs = np.array(series.highs, dtype=np.float64)
        lows = np.array(series.lows, dtype=np.float64)
        closes = np.array(series.closes, dtype=np.float64)
        volumes = np.array(series.volumes, dtype=np.float64)
        timestamps = [c.timestamp for c in series.candles]

        atr_arr = np.array(atr_values, dtype=np.float64) if atr_values else None

        # 1. Detect S/R levels
        sr_levels, swing_highs, swing_lows = self._sr_detector.detect(
            highs, lows, closes, volumes, timestamps
        )

        # 2. Build trendlines
        trendlines = self._trendline_builder.build(
            swing_highs, swing_lows, highs, lows, closes, atr_arr
        )

        # 3. Determine trend direction
        trend_direction = self._trend_analyzer.determine_trend(
            swing_highs, swing_lows, ema_values
        )

        # 4. Detect channels
        channels = self._trend_analyzer.detect_channels(trendlines)

        snapshot = StructuralSnapshot(
            symbol=series.symbol,
            sr_levels=sr_levels,
            trendlines=trendlines,
            channels=channels,
            trend_direction=trend_direction,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
        )

        # Cache
        key = self._cache_key(series.symbol, series.timeframe)
        self._cache[key] = snapshot

        elapsed_ms = (time.perf_counter() - start) * 1000
        self._total_analyses += 1
        self._total_time_ms += elapsed_ms

        logger.info(
            "structural_analysis_complete",
            symbol=series.symbol,
            timeframe=series.timeframe.value,
            sr_levels=len(sr_levels),
            trendlines=len(trendlines),
            channels=len(channels),
            trend=trend_direction.value,
            elapsed_ms=round(elapsed_ms, 2),
        )

        return snapshot

    def get_cached(self, symbol: str, timeframe: Timeframe) -> StructuralSnapshot | None:
        """Retrieve cached structural analysis."""
        return self._cache.get(self._cache_key(symbol, timeframe))

    def clear_cache(self) -> None:
        """Clear all cached analyses."""
        self._cache.clear()
