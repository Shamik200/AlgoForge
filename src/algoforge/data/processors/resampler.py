"""Multi-timeframe OHLCV resampler.

Converts lower-timeframe candles (e.g., 1m) into higher-timeframe candles
(e.g., 5m, 15m, 1h) following standard OHLCV aggregation rules:
  Open  = first candle's open
  High  = max of all highs
  Low   = min of all lows
  Close = last candle's close
  Volume = sum of all volumes
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import ClassVar

import structlog

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV

logger = structlog.get_logger()

# Timeframe duration in minutes for ordering and bucketing
_TF_MINUTES: dict[Timeframe, int] = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
    Timeframe.W1: 10080,
    Timeframe.MO1: 43200,
}


class Resampler:
    """Resample OHLCV candles from a lower timeframe to higher timeframes.

    Usage:
        resampler = Resampler()
        five_min = resampler.resample(one_min_candles, Timeframe.M5)
    """

    def resample(
        self,
        candles: list[OHLCV],
        target: Timeframe,
    ) -> list[OHLCV]:
        """Resample a list of candles to a higher timeframe.

        Args:
            candles: Source candles (must all be same symbol/timeframe).
            target: Target timeframe (must be higher than source).

        Returns:
            List of resampled OHLCV candles.

        Raises:
            ValueError: If target is same or lower than source timeframe.
        """
        if not candles:
            return []

        source_tf = candles[0].timeframe
        source_minutes = _TF_MINUTES[source_tf]
        target_minutes = _TF_MINUTES[target]

        if target_minutes <= source_minutes:
            msg = f"target must be a higher timeframe than source ({target.value} <= {source_tf.value})"
            raise ValueError(msg)

        symbol = candles[0].symbol

        # Group candles into target-timeframe buckets
        buckets: dict[datetime, list[OHLCV]] = {}
        for candle in candles:
            bucket_key = self._bucket_start(candle.timestamp, target_minutes)
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(candle)

        # Aggregate each bucket
        result: list[OHLCV] = []
        for bucket_ts in sorted(buckets.keys()):
            bucket = buckets[bucket_ts]
            result.append(
                OHLCV(
                    symbol=symbol,
                    timeframe=target,
                    timestamp=bucket_ts,
                    open=bucket[0].open,
                    high=max(c.high for c in bucket),
                    low=min(c.low for c in bucket),
                    close=bucket[-1].close,
                    volume=sum(c.volume for c in bucket),
                )
            )

        return result

    def resample_to_all(
        self,
        candles: list[OHLCV],
        targets: list[Timeframe],
    ) -> dict[Timeframe, list[OHLCV]]:
        """Resample to multiple target timeframes at once.

        Invalid targets (same or lower timeframe) are silently skipped.
        """
        results: dict[Timeframe, list[OHLCV]] = {}
        for target in targets:
            try:
                resampled = self.resample(candles, target)
                results[target] = resampled
            except ValueError:
                # Skip invalid timeframes (target <= source)
                continue
        return results

    @staticmethod
    def _bucket_start(ts: datetime, interval_minutes: int) -> datetime:
        """Compute the start of the bucket a timestamp falls into.

        For example, 09:37 with a 5-minute interval → 09:35.
        """
        total_minutes = ts.hour * 60 + ts.minute
        bucket_minutes = (total_minutes // interval_minutes) * interval_minutes
        return ts.replace(
            hour=bucket_minutes // 60,
            minute=bucket_minutes % 60,
            second=0,
            microsecond=0,
        )
