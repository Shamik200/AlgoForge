"""Trend Analyzer — Determines trend direction and channel identification.

Uses HH/HL pattern matching as primary, EMA alignment as confirmation.
Identifies ascending/descending/horizontal channels from trendline pairs.
"""

from __future__ import annotations

import numpy as np
import structlog

from algoforge.technical.structural.models import (
    Channel,
    ChannelType,
    SwingPoint,
    Trendline,
    TrendDirection,
)

logger = structlog.get_logger(__name__)


class TrendAnalyzer:
    """Analyzes trend direction and channel structure.

    Trend detection:
    1. Find HH/HL (uptrend) or LH/LL (downtrend) from swing points
    2. Confirm with EMA alignment (5 > 21 > 50 for up, reverse for down)
    3. Both must agree → UP/DOWN. Conflict → UNCLEAR.

    Channel detection:
    1. Find matching upper + lower trendlines with similar slope direction
    2. Classify as ascending/descending/horizontal
    """

    def __init__(
        self,
        min_swing_points: int = 3,
        slope_threshold: float = 0.0001,
        slope_similarity_pct: float = 0.5,
    ) -> None:
        """Initialize trend analyzer.

        Args:
            min_swing_points: Minimum swing points needed for trend detection
            slope_threshold: Slopes below this are considered flat
            slope_similarity_pct: Max difference between upper/lower slopes for channel (as ratio)
        """
        self._min_swing_points = min_swing_points
        self._slope_threshold = slope_threshold
        self._slope_similarity_pct = slope_similarity_pct

    def detect_trend_from_swings(
        self,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
    ) -> TrendDirection:
        """Detect trend direction from HH/HL or LH/LL patterns.

        Uses the last min_swing_points swing highs and lows.
        """
        if (
            len(swing_highs) < self._min_swing_points
            or len(swing_lows) < self._min_swing_points
        ):
            return TrendDirection.UNCLEAR

        # Check recent swing highs
        recent_highs = [s.price for s in swing_highs[-self._min_swing_points:]]
        recent_lows = [s.price for s in swing_lows[-self._min_swing_points:]]

        # Higher highs check
        higher_highs = all(
            recent_highs[i] > recent_highs[i - 1]
            for i in range(1, len(recent_highs))
        )

        # Higher lows check
        higher_lows = all(
            recent_lows[i] > recent_lows[i - 1]
            for i in range(1, len(recent_lows))
        )

        # Lower highs check
        lower_highs = all(
            recent_highs[i] < recent_highs[i - 1]
            for i in range(1, len(recent_highs))
        )

        # Lower lows check
        lower_lows = all(
            recent_lows[i] < recent_lows[i - 1]
            for i in range(1, len(recent_lows))
        )

        if higher_highs and higher_lows:
            return TrendDirection.UP
        elif lower_highs and lower_lows:
            return TrendDirection.DOWN
        else:
            return TrendDirection.UNCLEAR

    def confirm_with_ema(
        self,
        ema_values: dict[str, list[float]] | None,
    ) -> TrendDirection:
        """Confirm trend using EMA alignment.

        UP: EMA5 > EMA21 > EMA50 (at latest valid index)
        DOWN: EMA5 < EMA21 < EMA50
        Otherwise: UNCLEAR
        """
        if ema_values is None:
            return TrendDirection.UNCLEAR

        ema_5 = ema_values.get("ema_5")
        ema_21 = ema_values.get("ema_21")
        ema_50 = ema_values.get("ema_50")

        if not ema_5 or not ema_21 or not ema_50:
            return TrendDirection.UNCLEAR

        # Get latest non-NaN values
        def latest_valid(arr: list[float]) -> float | None:
            for v in reversed(arr):
                if not np.isnan(v):
                    return v
            return None

        e5 = latest_valid(ema_5)
        e21 = latest_valid(ema_21)
        e50 = latest_valid(ema_50)

        if e5 is None or e21 is None or e50 is None:
            return TrendDirection.UNCLEAR

        if e5 > e21 > e50:
            return TrendDirection.UP
        elif e5 < e21 < e50:
            return TrendDirection.DOWN
        else:
            return TrendDirection.UNCLEAR

    def determine_trend(
        self,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
        ema_values: dict[str, list[float]] | None = None,
    ) -> TrendDirection:
        """Determine overall trend direction.

        Both swing pattern AND EMA alignment must agree.
        If either is UNCLEAR or they conflict → UNCLEAR.
        """
        swing_trend = self.detect_trend_from_swings(swing_highs, swing_lows)
        ema_trend = self.confirm_with_ema(ema_values)

        if swing_trend == ema_trend and swing_trend != TrendDirection.UNCLEAR:
            logger.info(
                "trend_confirmed",
                direction=swing_trend.value,
                method="swing+ema_aligned",
            )
            return swing_trend

        # If only swing pattern is clear (no EMA data), use swing alone
        if ema_values is None and swing_trend != TrendDirection.UNCLEAR:
            logger.info(
                "trend_from_swings_only",
                direction=swing_trend.value,
            )
            return swing_trend

        logger.info(
            "trend_unclear",
            swing=swing_trend.value,
            ema=ema_trend.value,
        )
        return TrendDirection.UNCLEAR

    def detect_channels(
        self, trendlines: list[Trendline]
    ) -> list[Channel]:
        """Detect channels from pairs of upper + lower trendlines.

        A channel exists when an upper and lower trendline have
        similar slope direction (both positive or both negative).
        """
        upper_lines = [t for t in trendlines if t.is_upper and not t.broken]
        lower_lines = [t for t in trendlines if not t.is_upper and not t.broken]

        channels: list[Channel] = []

        for upper in upper_lines:
            for lower in lower_lines:
                # Check slope direction alignment
                if not self._slopes_compatible(upper.slope, lower.slope):
                    continue

                channel_type = self._classify_channel(upper.slope, lower.slope)

                # Calculate width at the latest point
                if upper.touch_points and lower.touch_points:
                    last_idx = max(
                        upper.touch_points[-1].index,
                        lower.touch_points[-1].index,
                    )
                    width = abs(
                        upper.price_at(last_idx) - lower.price_at(last_idx)
                    )
                else:
                    width = 0.0

                channels.append(Channel(
                    upper_line=upper,
                    lower_line=lower,
                    channel_type=channel_type,
                    width=width,
                ))

        logger.info("channels_detected", count=len(channels))
        return channels

    def _slopes_compatible(self, slope1: float, slope2: float) -> bool:
        """Check if two slopes have compatible direction."""
        # Both positive or both negative (or both near zero)
        if abs(slope1) < self._slope_threshold and abs(slope2) < self._slope_threshold:
            return True  # Both flat = horizontal channel

        if slope1 * slope2 > 0:
            return True  # Same direction

        return False

    def _classify_channel(self, upper_slope: float, lower_slope: float) -> ChannelType:
        """Classify channel type from slopes."""
        avg_slope = (upper_slope + lower_slope) / 2

        if abs(avg_slope) < self._slope_threshold:
            return ChannelType.HORIZONTAL
        elif avg_slope > 0:
            return ChannelType.ASCENDING
        else:
            return ChannelType.DESCENDING
