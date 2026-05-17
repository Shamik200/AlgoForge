"""Higher-timeframe coordination and caching utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.strategies.dual_timeframe import DualTimeframeFilter
from algoforge.technical.engine import IndicatorEngine
from algoforge.technical.regime import RegimeClassifier, RegimeResult
from algoforge.technical.structural.engine import StructuralEngine
from algoforge.technical.structural.models import StructuralSnapshot

logger = structlog.get_logger(__name__)


@dataclass
class HigherTimeframeContext:
    source_timeframe: Timeframe
    target_timeframe: Timeframe
    htf_series: OHLCVSeries
    htf_structure: StructuralSnapshot
    htf_regime: RegimeResult
    cache_hit: bool = False


class TimeframeCoordinator:
    """Build and cache higher-timeframe context from a lower timeframe series."""

    def __init__(self) -> None:
        self._cache: dict[str, HigherTimeframeContext] = {}

    def build_context(
        self,
        symbol: str,
        series: OHLCVSeries,
        indicator_engine: IndicatorEngine,
        structural_engine: StructuralEngine,
        regime_classifier: RegimeClassifier,
    ) -> HigherTimeframeContext | None:
        """Return a cached or freshly computed higher-timeframe context."""
        target_timeframe = DualTimeframeFilter.get_higher_timeframe(series.timeframe)
        if target_timeframe is None:
            return None

        cache_key = self._cache_key(symbol, series, target_timeframe)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return HigherTimeframeContext(
                source_timeframe=series.timeframe,
                target_timeframe=target_timeframe,
                htf_series=cached.htf_series,
                htf_structure=cached.htf_structure,
                htf_regime=cached.htf_regime,
                cache_hit=True,
            )

        htf_series = self._resample_series(symbol, series, target_timeframe)
        if htf_series.count < 20:
            return None

        indicators = indicator_engine.compute(htf_series)
        ema_res = indicators.get("ema")
        atr_res = indicators.get("atr")
        ema_vals = ema_res.values if ema_res else None
        atr_vals = atr_res.values.get("atr", []) if atr_res else None

        htf_structure = structural_engine.analyze(
            htf_series,
            ema_values=ema_vals,
            atr_values=atr_vals,
        )

        adx_res = indicators.get("adx")
        bb_res = indicators.get("bollinger")
        adx_vals = adx_res.values.get("adx", []) if adx_res else []
        adx_pdi = adx_res.values.get("plus_di", []) if adx_res else []
        adx_mdi = adx_res.values.get("minus_di", []) if adx_res else []
        bb_w = bb_res.values.get("bandwidth", []) if bb_res else []

        htf_regime = regime_classifier.classify(
            symbol=f"{symbol}:{target_timeframe.value}",
            adx=adx_vals[-1] if adx_vals else None,
            plus_di=adx_pdi[-1] if adx_pdi else None,
            minus_di=adx_mdi[-1] if adx_mdi else None,
            bb_bandwidth=bb_w[-1] if bb_w else None,
            atr_current=atr_vals[-1] if atr_vals else None,
            atr_avg=float(sum(atr_vals) / len(atr_vals)) if atr_vals else None,
            price=htf_series.closes[-1] if htf_series.count else None,
        )

        context = HigherTimeframeContext(
            source_timeframe=series.timeframe,
            target_timeframe=target_timeframe,
            htf_series=htf_series,
            htf_structure=htf_structure,
            htf_regime=htf_regime,
        )
        self._cache[cache_key] = context

        logger.debug(
            "htf_context_built",
            symbol=symbol,
            source_timeframe=series.timeframe.value,
            target_timeframe=target_timeframe.value,
            cache_size=len(self._cache),
        )
        return context

    def clear_cache(self) -> None:
        self._cache.clear()

    def _cache_key(self, symbol: str, series: OHLCVSeries, target_timeframe: Timeframe) -> str:
        latest_ts = series.latest.timestamp.isoformat() if series.latest else datetime.now(timezone.utc).isoformat()
        return f"{symbol}:{series.timeframe.value}:{target_timeframe.value}:{len(series.candles)}:{latest_ts}"

    def _resample_series(
        self,
        symbol: str,
        series: OHLCVSeries,
        target_timeframe: Timeframe,
    ) -> OHLCVSeries:
        group_size = self._group_size(series.timeframe, target_timeframe)
        candles = series.candles
        resampled: list[OHLCV] = []

        for start in range(0, len(candles), group_size):
            chunk = candles[start:start + group_size]
            if len(chunk) < group_size:
                continue
            resampled.append(
                OHLCV(
                    symbol=symbol,
                    timeframe=target_timeframe,
                    timestamp=chunk[-1].timestamp,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=sum(c.volume for c in chunk),
                )
            )

        return OHLCVSeries(symbol=symbol, timeframe=target_timeframe, candles=resampled)

    @staticmethod
    def _group_size(source: Timeframe, target: Timeframe) -> int:
        mapping = {
            (Timeframe.M1, Timeframe.M5): 5,
            (Timeframe.M5, Timeframe.M15): 3,
            (Timeframe.M15, Timeframe.H1): 4,
            (Timeframe.H1, Timeframe.H4): 4,
            (Timeframe.H4, Timeframe.D1): 6,
            (Timeframe.D1, Timeframe.W1): 5,
        }
        return mapping.get((source, target), 5)
