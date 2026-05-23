"""Trendline Builder — Constructs trendlines from swing points.

Connects fractal swing highs (resistance lines) and swing lows
(support lines) with validation and ranking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
from typing import TYPE_CHECKING
import uuid

import numpy as np
import pandas as pd
import structlog

from algoforge.technical.structural.models import SwingPoint, Trendline

if TYPE_CHECKING:
    from algoforge.core.models import OHLCV

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
        self._active_trendlines: dict[str, list[Trendline]] = {}  # symbol -> trendlines

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

        Optimized using highly efficient vectorized NumPy operations.
        """
        n = len(prices)
        if n == 0:
            return True

        indices = np.arange(n)
        line_prices = slope * indices + intercept

        # Filter out line prices <= 0
        valid_mask = line_prices > 0
        if not valid_mask.any():
            return True

        # Calculate tolerances
        if atr_values is not None and len(atr_values) == n:
            atr_tolerance = atr_values * 0.5
            pct_tolerance = line_prices * self._touch_tolerance_pct
            tolerance = np.where(np.isnan(atr_tolerance), pct_tolerance, atr_tolerance)
        else:
            tolerance = line_prices * self._touch_tolerance_pct

        # Check violations
        if is_upper:
            violations = prices > (line_prices + tolerance)
        else:
            violations = prices < (line_prices - tolerance)

        # Only check violations where line_price is valid (> 0)
        violations = violations & valid_mask

        # Check for consecutive violations exceeding max_violation_bars
        w = self._max_violation_bars + 1
        if len(violations) < w:
            return True

        # Pure vectorized check for consecutive True values of window size w
        consec = np.ones(len(violations) - w + 1, dtype=bool)
        for shift in range(w):
            consec &= violations[shift : len(violations) - w + 1 + shift]

        return not consec.any()

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

        # Prune old swing points to focus on the most recent 25 swing points
        # This keeps candidates combinations bounded to a max of 300, avoiding O(N^2) explosions
        recent_swing_points = swing_points[-25:] if len(swing_points) > 25 else swing_points

        # Try all pairs of recent swing points
        for p1, p2 in combinations(recent_swing_points, 2):
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
                id=str(uuid.uuid4()),
                symbol="",  # Will be set by caller
                slope=slope,
                intercept=intercept,
                touch_points=touches,
                touches=len(touches),
                is_upper=is_upper,
                direction="resistance" if is_upper else "support",
                strength=strength,
                broken=False,
                invalidated=False,
                valid_from=datetime.now(timezone.utc),
                last_touch=touches[-1].timestamp if touches else datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
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

    def detect_trendlines(
        self,
        symbol: str,
        bars: pd.DataFrame,
        min_touches: int = 3,
    ) -> list[Trendline]:
        """Detect valid trendlines from historical bars.

        Args:
            symbol: Symbol to detect trendlines for
            bars: DataFrame with columns: high, low, close, and optionally atr
            min_touches: Minimum number of touches required for a valid trendline

        Returns:
            List of detected trendlines with all required fields
        """
        if len(bars) < min_touches:
            logger.warning("insufficient_bars", symbol=symbol, bars=len(bars), min_touches=min_touches)
            return []

        # Extract swing points from bars (simplified - in production would use fractal detection)
        swing_highs = self._extract_swing_highs(bars)
        swing_lows = self._extract_swing_lows(bars)

        # Extract price arrays
        highs = bars["high"].values
        lows = bars["low"].values
        closes = bars["close"].values
        atr_values = bars["atr"].values if "atr" in bars.columns else None

        # Override min_touches for this detection
        original_min_touches = self._min_touches
        self._min_touches = min_touches

        try:
            # Build trendlines using existing logic
            trendlines = self.build(swing_highs, swing_lows, highs, lows, closes, atr_values)

            # Enhance trendlines with required fields
            enhanced_trendlines = []
            for trendline in trendlines:
                enhanced = Trendline(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    slope=trendline.slope,
                    intercept=trendline.intercept,
                    touch_points=trendline.touch_points,
                    touches=len(trendline.touch_points),
                    is_upper=trendline.is_upper,
                    direction="resistance" if trendline.is_upper else "support",
                    strength=trendline.strength,
                    broken=trendline.broken,
                    invalidated=False,
                    valid_from=datetime.now(timezone.utc),
                    last_touch=trendline.touch_points[-1].timestamp if trendline.touch_points else datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                )
                enhanced_trendlines.append(enhanced)

            # Store active trendlines for this symbol
            self._active_trendlines[symbol] = enhanced_trendlines

            logger.info(
                "trendlines_detected",
                symbol=symbol,
                count=len(enhanced_trendlines),
                min_touches=min_touches,
            )

            return enhanced_trendlines

        finally:
            # Restore original min_touches
            self._min_touches = original_min_touches

    def update_trendlines(
        self,
        symbol: str,
        new_bar: OHLCV,
    ) -> list[Trendline]:
        """Update existing trendlines with new bar data for incremental updates.

        Args:
            symbol: Symbol to update trendlines for
            new_bar: New OHLCV bar to process

        Returns:
            List of updated trendlines (invalidated ones are removed)
        """
        if symbol not in self._active_trendlines:
            logger.debug("no_active_trendlines", symbol=symbol)
            return []

        active_trendlines = self._active_trendlines[symbol]
        updated_trendlines = []

        for trendline in active_trendlines:
            # Skip already invalidated trendlines
            if trendline.invalidated:
                continue

            # Check if new bar touches the trendline
            current_index = len(trendline.touch_points)  # Approximate index
            line_price = trendline.price_at(current_index)

            # Determine if price touches the line
            is_touch = False
            if trendline.is_upper:
                # For resistance, check if high is near the line
                distance = abs(new_bar.high - line_price)
                tolerance = line_price * self._touch_tolerance_pct
                is_touch = distance <= tolerance
            else:
                # For support, check if low is near the line
                distance = abs(new_bar.low - line_price)
                tolerance = line_price * self._touch_tolerance_pct
                is_touch = distance <= tolerance

            if is_touch:
                # Add new touch point
                new_touch = SwingPoint(
                    index=current_index,
                    price=new_bar.high if trendline.is_upper else new_bar.low,
                    is_high=trendline.is_upper,
                    volume=new_bar.volume,
                    timestamp=new_bar.timestamp,
                )
                trendline.touch_points.append(new_touch)
                trendline.touches = len(trendline.touch_points)
                trendline.last_touch = new_bar.timestamp

            # Check if trendline is broken
            is_broken = False
            if trendline.is_upper and new_bar.close > line_price * (1 + self._touch_tolerance_pct):
                is_broken = True
            elif not trendline.is_upper and new_bar.close < line_price * (1 - self._touch_tolerance_pct):
                is_broken = True

            if is_broken:
                trendline.broken = True
                trendline.invalidated = True
                logger.info(
                    "trendline_broken",
                    symbol=symbol,
                    trendline_id=trendline.id,
                    direction=trendline.direction,
                )
            else:
                updated_trendlines.append(trendline)

        # Update active trendlines (remove invalidated ones)
        self._active_trendlines[symbol] = updated_trendlines

        logger.debug(
            "trendlines_updated",
            symbol=symbol,
            active_count=len(updated_trendlines),
        )

        return updated_trendlines

    def check_proximity(
        self,
        price: float,
        trendline: Trendline,
        atr: float,
        threshold: float = 0.5,
    ) -> bool:
        """Check if price is within threshold ATR of trendline.

        Args:
            price: Current price to check
            trendline: Trendline to check proximity against
            atr: Average True Range value
            threshold: ATR multiplier for proximity (default 0.5)

        Returns:
            True if price is within threshold * ATR of the trendline
        """
        # Calculate trendline price at current index (use last touch point index + 1)
        current_index = trendline.touch_points[-1].index + 1 if trendline.touch_points else 0
        line_price = trendline.price_at(current_index)

        # Calculate distance from trendline
        distance = abs(price - line_price)

        # Check if within threshold ATR
        proximity_threshold = atr * threshold
        is_near = distance <= proximity_threshold

        logger.debug(
            "proximity_check",
            price=price,
            line_price=line_price,
            distance=distance,
            atr=atr,
            threshold=threshold,
            proximity_threshold=proximity_threshold,
            is_near=is_near,
        )

        return is_near

    def _extract_swing_highs(self, bars: pd.DataFrame, window: int = 5) -> list[SwingPoint]:
        """Extract swing high points from bars using a simple window-based approach.

        Args:
            bars: DataFrame with high prices
            window: Window size for swing detection

        Returns:
            List of swing high points
        """
        swing_highs = []
        highs = bars["high"].values

        for i in range(window, len(highs) - window):
            is_swing_high = True
            for j in range(i - window, i + window + 1):
                if j != i and highs[j] >= highs[i]:
                    is_swing_high = False
                    break

            if is_swing_high:
                swing_highs.append(SwingPoint(
                    index=i,
                    price=highs[i],
                    is_high=True,
                    volume=bars.iloc[i]["volume"] if "volume" in bars.columns else 0.0,
                    timestamp=bars.index[i] if isinstance(bars.index, pd.DatetimeIndex) else datetime.now(timezone.utc),
                ))

        return swing_highs

    def _extract_swing_lows(self, bars: pd.DataFrame, window: int = 5) -> list[SwingPoint]:
        """Extract swing low points from bars using a simple window-based approach.

        Args:
            bars: DataFrame with low prices
            window: Window size for swing detection

        Returns:
            List of swing low points
        """
        swing_lows = []
        lows = bars["low"].values

        for i in range(window, len(lows) - window):
            is_swing_low = True
            for j in range(i - window, i + window + 1):
                if j != i and lows[j] <= lows[i]:
                    is_swing_low = False
                    break

            if is_swing_low:
                swing_lows.append(SwingPoint(
                    index=i,
                    price=lows[i],
                    is_high=False,
                    volume=bars.iloc[i]["volume"] if "volume" in bars.columns else 0.0,
                    timestamp=bars.index[i] if isinstance(bars.index, pd.DatetimeIndex) else datetime.now(timezone.utc),
                ))

        return swing_lows

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
