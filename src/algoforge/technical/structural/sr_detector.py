"""S/R Detector — Fractal-based support/resistance detection.

Uses Williams 5-bar fractal pattern to find swing points,
then clusters nearby levels and scores by volume, touch count, and recency.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import structlog

from algoforge.technical.structural.models import SRLevel, SRType, SwingPoint

logger = structlog.get_logger(__name__)


class SRDetector:
    """Detects support and resistance levels from OHLCV data.

    Algorithm:
    1. Find fractal swing highs/lows (Williams 5-bar)
    2. Cluster nearby levels within merge_pct
    3. Score each level by touch count, volume, recency
    4. Return top max_levels sorted by strength

    Usage:
        detector = SRDetector(fractal_window=2, merge_pct=0.005, max_levels=10)
        levels, swing_highs, swing_lows = detector.detect(highs, lows, closes, volumes, timestamps)
    """

    def __init__(
        self,
        fractal_window: int = 2,
        merge_pct: float = 0.005,
        max_levels: int = 10,
        recency_decay: float = 0.95,
    ) -> None:
        """Initialize S/R detector.

        Args:
            fractal_window: Bars before/after for fractal detection (2 = Williams 5-bar)
            merge_pct: Levels within this % of each other get merged (0.005 = 0.5%)
            max_levels: Maximum active S/R levels to return
            recency_decay: Exponential decay factor for recency weighting
        """
        self._fractal_window = fractal_window
        self._merge_pct = merge_pct
        self._max_levels = max_levels
        self._recency_decay = recency_decay

    def find_swing_points(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        timestamps: list[datetime],
    ) -> tuple[list[SwingPoint], list[SwingPoint]]:
        """Find fractal swing highs and swing lows.

        A swing high is a bar whose high is higher than the `fractal_window`
        bars before and after it: H[i] > H[i-w..i-1] and H[i] > H[i+1..i+w]

        Returns:
            Tuple of (swing_highs, swing_lows)
        """
        n = len(highs)
        w = self._fractal_window
        swing_highs: list[SwingPoint] = []
        swing_lows: list[SwingPoint] = []

        for i in range(w, n - w):
            # Swing high check
            is_swing_high = True
            for j in range(1, w + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_swing_high = False
                    break

            if is_swing_high:
                swing_highs.append(SwingPoint(
                    index=i,
                    price=float(highs[i]),
                    is_high=True,
                    volume=float(volumes[i]),
                    timestamp=timestamps[i],
                ))

            # Swing low check
            is_swing_low = True
            for j in range(1, w + 1):
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_swing_low = False
                    break

            if is_swing_low:
                swing_lows.append(SwingPoint(
                    index=i,
                    price=float(lows[i]),
                    is_high=False,
                    volume=float(volumes[i]),
                    timestamp=timestamps[i],
                ))

        return swing_highs, swing_lows

    def _cluster_levels(
        self, prices: list[float], volumes: list[float], timestamps: list[datetime]
    ) -> list[dict]:
        """Cluster nearby price levels.

        Merges levels within merge_pct of each other.
        Returns list of clusters with avg price, total volume, touch count.
        """
        if not prices:
            return []

        # Sort by price
        sorted_data = sorted(zip(prices, volumes, timestamps), key=lambda x: x[0])
        clusters: list[dict] = []
        current_cluster: list[tuple[float, float, datetime]] = [sorted_data[0]]

        for i in range(1, len(sorted_data)):
            price, vol, ts = sorted_data[i]
            cluster_avg = np.mean([p for p, _, _ in current_cluster])

            if abs(price - cluster_avg) / cluster_avg <= self._merge_pct:
                current_cluster.append((price, vol, ts))
            else:
                clusters.append(self._summarize_cluster(current_cluster))
                current_cluster = [(price, vol, ts)]

        clusters.append(self._summarize_cluster(current_cluster))
        return clusters

    def _summarize_cluster(self, cluster: list[tuple[float, float, datetime]]) -> dict:
        """Summarize a cluster of price levels."""
        prices = [p for p, _, _ in cluster]
        volumes = [v for _, v, _ in cluster]
        timestamps = [t for _, _, t in cluster]
        return {
            "price": float(np.mean(prices)),
            "touch_count": len(cluster),
            "total_volume": float(np.sum(volumes)),
            "avg_volume": float(np.mean(volumes)),
            "first_seen": min(timestamps),
            "last_touched": max(timestamps),
        }

    def _score_level(
        self, cluster: dict, total_bars: int, avg_volume: float
    ) -> float:
        """Score an S/R level by touch count, volume, and recency.

        Score = touch_weight × volume_weight × recency_weight
        """
        # Touch count weight (more touches = stronger)
        touch_w = min(cluster["touch_count"] / 3.0, 2.0)  # Cap at 2x for 6+ touches

        # Volume weight (higher volume = stronger)
        vol_w = cluster["avg_volume"] / avg_volume if avg_volume > 0 else 1.0
        vol_w = min(vol_w, 3.0)  # Cap at 3x

        # Recency weight (recent levels more relevant)
        age_bars = total_bars  # Simplified — could use actual bar distance
        recency_w = self._recency_decay ** (age_bars * 0.01)

        return touch_w * vol_w * recency_w * 100

    def detect(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
        timestamps: list[datetime],
    ) -> tuple[list[SRLevel], list[SwingPoint], list[SwingPoint]]:
        """Detect S/R levels from OHLCV data.

        Returns:
            Tuple of (sr_levels, swing_highs, swing_lows)
        """
        swing_highs, swing_lows = self.find_swing_points(
            highs, lows, volumes, timestamps
        )

        avg_volume = float(np.mean(volumes)) if len(volumes) > 0 else 1.0
        n = len(highs)

        # Cluster resistance levels (from swing highs)
        res_clusters = self._cluster_levels(
            [s.price for s in swing_highs],
            [s.volume for s in swing_highs],
            [s.timestamp for s in swing_highs],
        )

        # Cluster support levels (from swing lows)
        sup_clusters = self._cluster_levels(
            [s.price for s in swing_lows],
            [s.volume for s in swing_lows],
            [s.timestamp for s in swing_lows],
        )

        sr_levels: list[SRLevel] = []

        for cluster in res_clusters:
            strength = self._score_level(cluster, n, avg_volume)
            sr_levels.append(SRLevel(
                price=cluster["price"],
                sr_type=SRType.RESISTANCE,
                strength=strength,
                touch_count=cluster["touch_count"],
                volume_weight=cluster["avg_volume"] / avg_volume if avg_volume > 0 else 1.0,
                first_seen=cluster["first_seen"],
                last_touched=cluster["last_touched"],
            ))

        for cluster in sup_clusters:
            strength = self._score_level(cluster, n, avg_volume)
            sr_levels.append(SRLevel(
                price=cluster["price"],
                sr_type=SRType.SUPPORT,
                strength=strength,
                touch_count=cluster["touch_count"],
                volume_weight=cluster["avg_volume"] / avg_volume if avg_volume > 0 else 1.0,
                first_seen=cluster["first_seen"],
                last_touched=cluster["last_touched"],
            ))

        # Sort by strength and limit
        sr_levels.sort(key=lambda x: x.strength, reverse=True)
        sr_levels = sr_levels[:self._max_levels]

        logger.info(
            "sr_detected",
            resistance_count=len(res_clusters),
            support_count=len(sup_clusters),
            total_levels=len(sr_levels),
            swing_highs=len(swing_highs),
            swing_lows=len(swing_lows),
        )

        return sr_levels, swing_highs, swing_lows
