"""Candlestick Pattern Recognition.

Detects 12 patterns (6 bullish + 6 bearish) from OHLCV data.
Used as confirmation layer in the primary and secondary strategies.

Requirements: CNDL-01, CNDL-02, CNDL-03
"""

from __future__ import annotations

from enum import Enum

import numpy as np
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class PatternType(str, Enum):
    """Candlestick pattern classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"


class CandlestickPattern(BaseModel):
    """A detected candlestick pattern."""

    name: str = Field(..., description="Pattern name (e.g., 'hammer')")
    pattern_type: PatternType
    index: int = Field(..., ge=0, description="Bar index where pattern completes")
    strength: float = Field(default=1.0, ge=0, le=2.0, description="Pattern strength/reliability")


class CandlestickDetector:
    """Detects 12 candlestick patterns from OHLCV data.

    Bullish patterns: Hammer, Bullish Engulfing, Morning Star,
                     Piercing Line, Dragonfly Doji, Three White Soldiers

    Bearish patterns: Shooting Star, Bearish Engulfing, Evening Star,
                     Dark Cloud Cover, Gravestone Doji, Three Black Crows

    Usage:
        detector = CandlestickDetector()
        patterns = detector.detect(opens, highs, lows, closes)
        bullish = detector.bullish_at(patterns, index=99)
        bearish = detector.bearish_at(patterns, index=99)
    """

    def __init__(self, body_ratio: float = 0.3, doji_ratio: float = 0.05) -> None:
        """Initialize detector.

        Args:
            body_ratio: Minimum body/range ratio for significant candles
            doji_ratio: Maximum body/range ratio for doji patterns
        """
        self._body_ratio = body_ratio
        self._doji_ratio = doji_ratio

    def _body(self, o: float, c: float) -> float:
        """Real body size."""
        return abs(c - o)

    def _range(self, h: float, l: float) -> float:
        """Full candle range."""
        return h - l

    def _is_bullish(self, o: float, c: float) -> bool:
        return c > o

    def _is_bearish(self, o: float, c: float) -> bool:
        return c < o

    def _upper_shadow(self, o: float, h: float, c: float) -> float:
        return h - max(o, c)

    def _lower_shadow(self, o: float, l: float, c: float) -> float:
        return min(o, c) - l

    def detect(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        lookback: int | None = None,
    ) -> list[CandlestickPattern]:
        """Detect all patterns across the entire series."""
        n = len(closes)
        patterns: list[CandlestickPattern] = []

        start_idx = 0
        if lookback is not None:
            start_idx = max(0, n - lookback)

        for i in range(start_idx, n):
            o, h, l, c = float(opens[i]), float(highs[i]), float(lows[i]), float(closes[i])
            rng = self._range(h, l)
            if rng == 0:
                continue
            body = self._body(o, c)
            body_pct = body / rng

            # --- Single candle patterns ---

            # Hammer (bullish): small body at top, long lower shadow
            if (
                i > 0
                and self._lower_shadow(o, l, c) >= 2 * body
                and self._upper_shadow(o, h, c) <= body * 0.5
                and body_pct >= self._doji_ratio
            ):
                patterns.append(CandlestickPattern(
                    name="hammer", pattern_type=PatternType.BULLISH, index=i, strength=1.2,
                ))

            # Shooting Star (bearish): small body at bottom, long upper shadow
            if (
                i > 0
                and self._upper_shadow(o, h, c) >= 2 * body
                and self._lower_shadow(o, l, c) <= body * 0.5
                and body_pct >= self._doji_ratio
            ):
                patterns.append(CandlestickPattern(
                    name="shooting_star", pattern_type=PatternType.BEARISH, index=i, strength=1.2,
                ))

            # Dragonfly Doji (bullish): very small body, long lower shadow, no upper shadow
            if (
                body_pct <= self._doji_ratio
                and self._lower_shadow(o, l, c) >= rng * 0.6
                and self._upper_shadow(o, h, c) <= rng * 0.1
            ):
                patterns.append(CandlestickPattern(
                    name="dragonfly_doji", pattern_type=PatternType.BULLISH, index=i, strength=1.0,
                ))

            # Gravestone Doji (bearish): very small body, long upper shadow, no lower shadow
            if (
                body_pct <= self._doji_ratio
                and self._upper_shadow(o, h, c) >= rng * 0.6
                and self._lower_shadow(o, l, c) <= rng * 0.1
            ):
                patterns.append(CandlestickPattern(
                    name="gravestone_doji", pattern_type=PatternType.BEARISH, index=i, strength=1.0,
                ))

            # --- Two candle patterns (need i >= 1) ---
            if i >= 1:
                o1, h1, l1, c1 = float(opens[i - 1]), float(highs[i - 1]), float(lows[i - 1]), float(closes[i - 1])
                body1 = self._body(o1, c1)
                rng1 = self._range(h1, l1)

                # Bullish Engulfing: bearish candle → bullish candle that engulfs
                if (
                    self._is_bearish(o1, c1)
                    and self._is_bullish(o, c)
                    and o <= c1
                    and c >= o1
                    and body > body1
                ):
                    patterns.append(CandlestickPattern(
                        name="bullish_engulfing", pattern_type=PatternType.BULLISH, index=i, strength=1.5,
                    ))

                # Bearish Engulfing: bullish candle → bearish candle that engulfs
                if (
                    self._is_bullish(o1, c1)
                    and self._is_bearish(o, c)
                    and o >= c1
                    and c <= o1
                    and body > body1
                ):
                    patterns.append(CandlestickPattern(
                        name="bearish_engulfing", pattern_type=PatternType.BEARISH, index=i, strength=1.5,
                    ))

                # Piercing Line (bullish): bearish candle → bullish opening below, closing above midpoint
                if (
                    self._is_bearish(o1, c1)
                    and self._is_bullish(o, c)
                    and o < c1
                    and c > (o1 + c1) / 2
                    and c < o1
                ):
                    patterns.append(CandlestickPattern(
                        name="piercing_line", pattern_type=PatternType.BULLISH, index=i, strength=1.3,
                    ))

                # Dark Cloud Cover (bearish): bullish candle → bearish opening above, closing below midpoint
                if (
                    self._is_bullish(o1, c1)
                    and self._is_bearish(o, c)
                    and o > c1
                    and c < (o1 + c1) / 2
                    and c > o1
                ):
                    patterns.append(CandlestickPattern(
                        name="dark_cloud_cover", pattern_type=PatternType.BEARISH, index=i, strength=1.3,
                    ))

            # --- Three candle patterns (need i >= 2) ---
            if i >= 2:
                o2, h2, l2, c2 = float(opens[i - 2]), float(highs[i - 2]), float(lows[i - 2]), float(closes[i - 2])
                o1, h1, l1, c1 = float(opens[i - 1]), float(highs[i - 1]), float(lows[i - 1]), float(closes[i - 1])
                body2 = self._body(o2, c2)
                body1 = self._body(o1, c1)
                rng1 = self._range(h1, l1)

                # Morning Star (bullish): bearish → small body → bullish
                if (
                    self._is_bearish(o2, c2)
                    and body2 > 0
                    and (body1 / body2 if body2 > 0 else 0) < 0.5
                    and self._is_bullish(o, c)
                    and c > (o2 + c2) / 2
                ):
                    patterns.append(CandlestickPattern(
                        name="morning_star", pattern_type=PatternType.BULLISH, index=i, strength=1.8,
                    ))

                # Evening Star (bearish): bullish → small body → bearish
                if (
                    self._is_bullish(o2, c2)
                    and body2 > 0
                    and (body1 / body2 if body2 > 0 else 0) < 0.5
                    and self._is_bearish(o, c)
                    and c < (o2 + c2) / 2
                ):
                    patterns.append(CandlestickPattern(
                        name="evening_star", pattern_type=PatternType.BEARISH, index=i, strength=1.8,
                    ))

                # Three White Soldiers (bullish): 3 consecutive bullish with higher closes
                if (
                    self._is_bullish(o2, c2)
                    and self._is_bullish(o1, c1)
                    and self._is_bullish(o, c)
                    and c1 > c2
                    and c > c1
                    and o1 > o2
                    and o > o1
                ):
                    patterns.append(CandlestickPattern(
                        name="three_white_soldiers", pattern_type=PatternType.BULLISH, index=i, strength=1.7,
                    ))

                # Three Black Crows (bearish): 3 consecutive bearish with lower closes
                if (
                    self._is_bearish(o2, c2)
                    and self._is_bearish(o1, c1)
                    and self._is_bearish(o, c)
                    and c1 < c2
                    and c < c1
                    and o1 < o2
                    and o < o1
                ):
                    patterns.append(CandlestickPattern(
                        name="three_black_crows", pattern_type=PatternType.BEARISH, index=i, strength=1.7,
                    ))

        logger.debug("candlestick_scan", total_patterns=len(patterns))
        return patterns

    def bullish_at(self, patterns: list[CandlestickPattern], index: int) -> list[CandlestickPattern]:
        """Get bullish patterns at a specific bar index."""
        return [p for p in patterns if p.index == index and p.pattern_type == PatternType.BULLISH]

    def bearish_at(self, patterns: list[CandlestickPattern], index: int) -> list[CandlestickPattern]:
        """Get bearish patterns at a specific bar index."""
        return [p for p in patterns if p.index == index and p.pattern_type == PatternType.BEARISH]

    def patterns_near(self, patterns: list[CandlestickPattern], index: int, window: int = 3) -> list[CandlestickPattern]:
        """Get patterns within a window of bars around index."""
        return [p for p in patterns if abs(p.index - index) <= window]
