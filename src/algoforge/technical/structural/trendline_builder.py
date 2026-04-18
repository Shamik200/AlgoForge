"""Trendline Builder — Constructs trendlines from swing points.

Connects fractal swing highs (resistance lines) and swing lows
(support lines) with validation and ranking.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import structlog

from algoforge.technical.structural.models import SwingPoint, Trendline

logger = structlog.get_logger(__name__)


class TrendlineBuilder:
    """Builds and validates trendlines from swing points.

    Algorithm:
    1. Take all pairs of swing highs → candidate resistance lines
    2. Take all pairs of swing lows → candidate support lines
    3. For each candidate, count additional touch points
    4. Validate lines (not violated for >tolerance bars)
    5. Rank by touch count and recency, return top lines

    Usage:
        builder = TrendlineBuilder(touch_tolerance_pct=0.003, max_lines=4)
        trendlines = builder.build(swing_highs, swing_lows, highs, lows, closes, atr_values)
    """

    def __init__(
        self,
        touch_tolerance_pct: float = 0.003,
        max_lines: int = 4,
        min_touches: int = 2,
        max_violation_bars: int = 2,
    ) -> None:
        """Initialize trendline builder.

        Args:
            touch_tolerance_pct: Price within this % of the line counts as a "touch" (0.3%)
            max_lines: Maximum trendlines to return (split upper/lower)
            min_touches: Minimum touch points for a valid trendline
            max_violation_bars: Max consecutive bars price can violate line before invalidation
        """
        self._touch_tolerance_pct = touch_tolerance_pct
        self._max_lines = max_lines
        self._min_touches = min_touches
        self._max_violation_bars = max_violation_bars

    def _fit_line(self, p1: SwingPoint, p2: SwingPoint) -> tuple[float, float]:
        """Fit a line through two swing points.

        Returns:
            (slope, intercept) where price_at_index = slope * index + intercept
        """
        if p1.index == p2.index:
            return 0.0, p1.price

        slope = (p2.price - p1.price) / (p2.index - p1.index)
        intercept = p1.price - slope * p1.index
        return slope, intercept

    def _count_touches(
        self,
        slope: float,
        intercept: float,
        points: list[SwingPoint],
        anchor_indices: set[int],
    ) -> list[SwingPoint]:
        """Count how many swing points are near the trendline."""
        touches: list[SwingPoint] = []
        for point in points:
            line_price = slope * point.index + intercept
            if line_price > 0:
                distance_pct = abs(point.price - line_price) / line_price
                if distance_pct <= self._touch_tolerance_pct or point.index in anchor_indices:
                    touches.append(point)
        return touches

    def _validate_line(
        self,
        slope: float,
        intercept: float,
        is_upper: bool,
        prices: np.ndarray,
        atr_values: np.ndarray | None = None,
    ) -> bool:
        """Validate trendline hasn't been broken by consecutive violations.

        For upper (resistance) lines: broken if close stays above for max_violation_bars
        For lower (support) lines: broken if close stays below for max_violation_bars
        """
        consecutive_violations = 0
        n = len(prices)

        for i in range(n):
            line_price = slope * i + intercept
            if line_price <= 0:
                continue

            # Tolerance based on ATR if available, else percentage
            if atr_values is not None and not np.isnan(atr_values[i]):
                tolerance = atr_values[i] * 0.5
            else:
                tolerance = line_price * self._touch_tolerance_pct

            if is_upper and prices[i] > line_price + tolerance:
                consecutive_violations += 1
            elif not is_upper and prices[i] < line_price - tolerance:
                consecutive_violations += 1
            else:
                consecutive_violations = 0

            if consecutive_violations > self._max_violation_bars:
                return False

        return True

    def _build_lines(
        self,
        swing_points: list[SwingPoint],
        is_upper: bool,
        prices: np.ndarray,
        atr_values: np.ndarray | None = None,
    ) -> list[Trendline]:
        """Build trendlines from swing points of one type."""
        if len(swing_points) < self._min_touches:
            return []

        candidates: list[Trendline] = []

        # Try all pairs of swing points
        for p1, p2 in combinations(swing_points, 2):
            if abs(p1.index - p2.index) < 3:
                continue  # Too close together

            slope, intercept = self._fit_line(p1, p2)

            # Count additional touches
            anchor_indices = {p1.index, p2.index}
            touches = self._count_touches(slope, intercept, swing_points, anchor_indices)

            if len(touches) < self._min_touches:
                continue

            # Validate against price series
            if not self._validate_line(slope, intercept, is_upper, prices, atr_values):
                continue

            # Score: touch_count * recency_bonus
            max_idx = max(t.index for t in touches)
            recency_bonus = 1.0 + (max_idx / len(prices)) if len(prices) > 0 else 1.0
            strength = len(touches) * recency_bonus

            candidates.append(Trendline(
                slope=slope,
                intercept=intercept,
                touch_points=touches,
                is_upper=is_upper,
                strength=strength,
            ))

        # Sort by strength and deduplicate similar lines
        candidates.sort(key=lambda t: t.strength, reverse=True)
        return self._deduplicate(candidates)

    def _deduplicate(self, lines: list[Trendline]) -> list[Trendline]:
        """Remove near-duplicate trendlines (similar slope + intercept)."""
        if not lines:
            return []

        unique: list[Trendline] = [lines[0]]
        for line in lines[1:]:
            is_dup = False
            for existing in unique:
                slope_diff = abs(line.slope - existing.slope)
                intercept_diff = abs(line.intercept - existing.intercept)
                if slope_diff < 0.01 and intercept_diff < existing.intercept * 0.005:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(line)

        return unique

    def build(
        self,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        atr_values: np.ndarray | None = None,
    ) -> list[Trendline]:
        """Build trendlines from swing points.

        Returns:
            List of validated trendlines, max_lines total (split upper/lower).
        """
        max_per_side = self._max_lines // 2

        upper_lines = self._build_lines(swing_highs, True, highs, atr_values)[:max_per_side]
        lower_lines = self._build_lines(swing_lows, False, lows, atr_values)[:max_per_side]

        all_lines = upper_lines + lower_lines

        logger.info(
            "trendlines_built",
            upper=len(upper_lines),
            lower=len(lower_lines),
            total=len(all_lines),
        )

        return all_lines
