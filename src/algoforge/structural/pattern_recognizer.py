"""Candlestick Pattern Recognition for Structural Analysis.

Detects major candlestick patterns and classifies them by direction and strength.
Used as a confirmation filter for signal generation, not as a standalone signal generator.

Requirements: 3.1, 3.3
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

import numpy as np
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class PatternDirection(str, Enum):
    """Direction of candlestick pattern."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class PatternStrength(str, Enum):
    """Strength classification of candlestick pattern."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class CandlestickPattern(BaseModel):
    """Represents a detected candlestick pattern.
    
    Attributes:
        pattern_type: Name of the pattern (e.g., 'engulfing', 'hammer')
        direction: Bullish, bearish, or neutral
        strength: Weak, moderate, or strong
        bars_involved: Number of bars that form the pattern (1-3)
        timestamp: Bar index where pattern completes
        at_sr_level: Whether pattern formed at a high-confluence S/R level
        confluence_boost: Conviction boost amount (0-0.3) when at S/R level
    """

    pattern_type: str = Field(..., description="Pattern name")
    direction: PatternDirection = Field(..., description="Pattern direction")
    strength: PatternStrength = Field(..., description="Pattern strength")
    bars_involved: int = Field(..., ge=1, le=3, description="Number of bars in pattern")
    timestamp: int = Field(..., ge=0, description="Bar index where pattern completes")
    at_sr_level: bool = Field(default=False, description="Pattern at S/R level")
    confluence_boost: float = Field(default=0.0, ge=0.0, le=0.3, description="Conviction boost")


class PatternRecognizer:
    """Recognizes candlestick patterns from price action.
    
    Detects 10 major candlestick patterns:
    - Engulfing (bullish/bearish)
    - Hammer / Shooting Star
    - Doji
    - Morning Star / Evening Star
    - Three White Soldiers / Three Black Crows
    - Harami (bullish/bearish)
    - Piercing Line / Dark Cloud Cover
    
    Usage:
        recognizer = PatternRecognizer()
        patterns = recognizer.recognize_patterns(bars_df)
        for pattern in patterns:
            direction, strength = recognizer.classify_pattern(pattern)
    """

    def __init__(
        self,
        body_ratio: float = 0.3,
        doji_ratio: float = 0.1,
        confluence_boost: float = 0.2,
    ) -> None:
        """Initialize pattern recognizer.
        
        Args:
            body_ratio: Minimum body/range ratio for significant candles
            doji_ratio: Maximum body/range ratio for doji patterns
            confluence_boost: Conviction boost when pattern at S/R level (default 0.2 = 20%)
        """
        self._body_ratio = body_ratio
        self._doji_ratio = doji_ratio
        self._confluence_boost = confluence_boost

    def recognize_patterns(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        lookback: int = 5,
    ) -> list[CandlestickPattern]:
        """Detect patterns in recent bars.
        
        Args:
            opens: Open prices
            highs: High prices
            lows: Low prices
            closes: Close prices
            lookback: Number of recent bars to analyze
            
        Returns:
            List of detected patterns
        """
        if len(closes) < 3:
            return []

        # Only analyze the most recent bars
        start_idx = max(0, len(closes) - lookback)
        patterns: list[CandlestickPattern] = []

        for i in range(start_idx, len(closes)):
            o, h, l, c = float(opens[i]), float(highs[i]), float(lows[i]), float(closes[i])
            rng = self._range(h, l)
            if rng == 0:
                continue

            body = self._body(o, c)
            body_pct = body / rng

            # --- Single candle patterns (1 bar) ---

            # Hammer (bullish)
            if self._is_hammer(o, h, l, c, body, body_pct) and i > 0:
                patterns.append(
                    CandlestickPattern(
                        pattern_type="hammer",
                        direction=PatternDirection.BULLISH,
                        strength=PatternStrength.MODERATE,
                        bars_involved=1,
                        timestamp=i,
                    )
                )

            # Shooting Star (bearish)
            if self._is_shooting_star(o, h, l, c, body, body_pct) and i > 0:
                patterns.append(
                    CandlestickPattern(
                        pattern_type="shooting_star",
                        direction=PatternDirection.BEARISH,
                        strength=PatternStrength.MODERATE,
                        bars_involved=1,
                        timestamp=i,
                    )
                )

            # Doji (neutral)
            if self._is_doji(body_pct):
                patterns.append(
                    CandlestickPattern(
                        pattern_type="doji",
                        direction=PatternDirection.NEUTRAL,
                        strength=PatternStrength.WEAK,
                        bars_involved=1,
                        timestamp=i,
                    )
                )

            # --- Two candle patterns (2 bars) ---
            if i >= 1:
                o1, h1, l1, c1 = (
                    float(opens[i - 1]),
                    float(highs[i - 1]),
                    float(lows[i - 1]),
                    float(closes[i - 1]),
                )
                body1 = self._body(o1, c1)

                # Bullish Engulfing
                if self._is_bullish_engulfing(o1, c1, o, c, body1, body):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="engulfing",
                            direction=PatternDirection.BULLISH,
                            strength=PatternStrength.STRONG,
                            bars_involved=2,
                            timestamp=i,
                        )
                    )

                # Bearish Engulfing
                if self._is_bearish_engulfing(o1, c1, o, c, body1, body):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="engulfing",
                            direction=PatternDirection.BEARISH,
                            strength=PatternStrength.STRONG,
                            bars_involved=2,
                            timestamp=i,
                        )
                    )

                # Piercing Line (bullish)
                if self._is_piercing_line(o1, c1, o, c):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="piercing",
                            direction=PatternDirection.BULLISH,
                            strength=PatternStrength.MODERATE,
                            bars_involved=2,
                            timestamp=i,
                        )
                    )

                # Dark Cloud Cover (bearish)
                if self._is_dark_cloud(o1, c1, o, c):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="dark_cloud",
                            direction=PatternDirection.BEARISH,
                            strength=PatternStrength.MODERATE,
                            bars_involved=2,
                            timestamp=i,
                        )
                    )

                # Bullish Harami
                if self._is_bullish_harami(o1, c1, o, c, body1, body):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="harami",
                            direction=PatternDirection.BULLISH,
                            strength=PatternStrength.WEAK,
                            bars_involved=2,
                            timestamp=i,
                        )
                    )

                # Bearish Harami
                if self._is_bearish_harami(o1, c1, o, c, body1, body):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="harami",
                            direction=PatternDirection.BEARISH,
                            strength=PatternStrength.WEAK,
                            bars_involved=2,
                            timestamp=i,
                        )
                    )

            # --- Three candle patterns (3 bars) ---
            if i >= 2:
                o2, h2, l2, c2 = (
                    float(opens[i - 2]),
                    float(highs[i - 2]),
                    float(lows[i - 2]),
                    float(closes[i - 2]),
                )
                o1, h1, l1, c1 = (
                    float(opens[i - 1]),
                    float(highs[i - 1]),
                    float(lows[i - 1]),
                    float(closes[i - 1]),
                )
                body2 = self._body(o2, c2)
                body1 = self._body(o1, c1)

                # Morning Star (bullish)
                if self._is_morning_star(o2, c2, o1, c1, o, c, body2, body1):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="morning_star",
                            direction=PatternDirection.BULLISH,
                            strength=PatternStrength.STRONG,
                            bars_involved=3,
                            timestamp=i,
                        )
                    )

                # Evening Star (bearish)
                if self._is_evening_star(o2, c2, o1, c1, o, c, body2, body1):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="evening_star",
                            direction=PatternDirection.BEARISH,
                            strength=PatternStrength.STRONG,
                            bars_involved=3,
                            timestamp=i,
                        )
                    )

                # Three White Soldiers (bullish)
                if self._is_three_white_soldiers(o2, c2, o1, c1, o, c):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="three_soldiers",
                            direction=PatternDirection.BULLISH,
                            strength=PatternStrength.STRONG,
                            bars_involved=3,
                            timestamp=i,
                        )
                    )

                # Three Black Crows (bearish)
                if self._is_three_black_crows(o2, c2, o1, c1, o, c):
                    patterns.append(
                        CandlestickPattern(
                            pattern_type="three_crows",
                            direction=PatternDirection.BEARISH,
                            strength=PatternStrength.STRONG,
                            bars_involved=3,
                            timestamp=i,
                        )
                    )

        logger.debug("pattern_recognition", total_patterns=len(patterns))
        return patterns

    def classify_pattern(
        self, pattern: CandlestickPattern
    ) -> tuple[Literal["bullish", "bearish", "neutral"], Literal["weak", "moderate", "strong"]]:
        """Classify pattern direction and strength.
        
        Args:
            pattern: The candlestick pattern to classify
            
        Returns:
            Tuple of (direction, strength) where direction is 'bullish'/'bearish'/'neutral'
            and strength is 'weak'/'moderate'/'strong'
        """
        return pattern.direction.value, pattern.strength.value

    # --- Helper methods for pattern detection ---

    def _body(self, o: float, c: float) -> float:
        """Calculate real body size."""
        return abs(c - o)

    def _range(self, h: float, l: float) -> float:
        """Calculate full candle range."""
        return h - l

    def _is_bullish(self, o: float, c: float) -> bool:
        """Check if candle is bullish."""
        return c > o

    def _is_bearish(self, o: float, c: float) -> bool:
        """Check if candle is bearish."""
        return c < o

    def _upper_shadow(self, o: float, h: float, c: float) -> float:
        """Calculate upper shadow length."""
        return h - max(o, c)

    def _lower_shadow(self, o: float, l: float, c: float) -> float:
        """Calculate lower shadow length."""
        return min(o, c) - l

    # --- Single candle pattern detectors ---

    def _is_hammer(
        self, o: float, h: float, l: float, c: float, body: float, body_pct: float
    ) -> bool:
        """Detect hammer pattern: small body at top, long lower shadow."""
        return (
            self._lower_shadow(o, l, c) >= 2 * body
            and self._upper_shadow(o, h, c) <= body * 0.5
            and body_pct >= self._doji_ratio
        )

    def _is_shooting_star(
        self, o: float, h: float, l: float, c: float, body: float, body_pct: float
    ) -> bool:
        """Detect shooting star: small body at bottom, long upper shadow."""
        return (
            self._upper_shadow(o, h, c) >= 2 * body
            and self._lower_shadow(o, l, c) <= body * 0.5
            and body_pct >= self._doji_ratio
        )

    def _is_doji(self, body_pct: float) -> bool:
        """Detect doji: very small body."""
        return body_pct <= self._doji_ratio

    # --- Two candle pattern detectors ---

    def _is_bullish_engulfing(
        self, o1: float, c1: float, o: float, c: float, body1: float, body: float
    ) -> bool:
        """Detect bullish engulfing: bearish candle → bullish candle that engulfs."""
        return (
            self._is_bearish(o1, c1)
            and self._is_bullish(o, c)
            and o <= c1
            and c >= o1
            and body > body1
        )

    def _is_bearish_engulfing(
        self, o1: float, c1: float, o: float, c: float, body1: float, body: float
    ) -> bool:
        """Detect bearish engulfing: bullish candle → bearish candle that engulfs."""
        return (
            self._is_bullish(o1, c1)
            and self._is_bearish(o, c)
            and o >= c1
            and c <= o1
            and body > body1
        )

    def _is_piercing_line(self, o1: float, c1: float, o: float, c: float) -> bool:
        """Detect piercing line: bearish → bullish opening below, closing above midpoint."""
        return (
            self._is_bearish(o1, c1)
            and self._is_bullish(o, c)
            and o < c1
            and c > (o1 + c1) / 2
            and c < o1
        )

    def _is_dark_cloud(self, o1: float, c1: float, o: float, c: float) -> bool:
        """Detect dark cloud cover: bullish → bearish opening above, closing below midpoint."""
        return (
            self._is_bullish(o1, c1)
            and self._is_bearish(o, c)
            and o > c1
            and c < (o1 + c1) / 2
            and c > o1
        )

    def _is_bullish_harami(
        self, o1: float, c1: float, o: float, c: float, body1: float, body: float
    ) -> bool:
        """Detect bullish harami: large bearish → small bullish inside."""
        return (
            self._is_bearish(o1, c1)
            and self._is_bullish(o, c)
            and o > c1
            and c < o1
            and body < body1
        )

    def _is_bearish_harami(
        self, o1: float, c1: float, o: float, c: float, body1: float, body: float
    ) -> bool:
        """Detect bearish harami: large bullish → small bearish inside."""
        return (
            self._is_bullish(o1, c1)
            and self._is_bearish(o, c)
            and o < c1
            and c > o1
            and body < body1
        )

    # --- Three candle pattern detectors ---

    def _is_morning_star(
        self,
        o2: float,
        c2: float,
        o1: float,
        c1: float,
        o: float,
        c: float,
        body2: float,
        body1: float,
    ) -> bool:
        """Detect morning star: bearish → small body → bullish."""
        return (
            self._is_bearish(o2, c2)
            and body2 > 0
            and (body1 / body2 if body2 > 0 else 0) < 0.5
            and self._is_bullish(o, c)
            and c > (o2 + c2) / 2
        )

    def _is_evening_star(
        self,
        o2: float,
        c2: float,
        o1: float,
        c1: float,
        o: float,
        c: float,
        body2: float,
        body1: float,
    ) -> bool:
        """Detect evening star: bullish → small body → bearish."""
        return (
            self._is_bullish(o2, c2)
            and body2 > 0
            and (body1 / body2 if body2 > 0 else 0) < 0.5
            and self._is_bearish(o, c)
            and c < (o2 + c2) / 2
        )

    def _is_three_white_soldiers(
        self, o2: float, c2: float, o1: float, c1: float, o: float, c: float
    ) -> bool:
        """Detect three white soldiers: 3 consecutive bullish with higher closes."""
        return (
            self._is_bullish(o2, c2)
            and self._is_bullish(o1, c1)
            and self._is_bullish(o, c)
            and c1 > c2
            and c > c1
            and o1 > o2
            and o > o1
        )

    def _is_three_black_crows(
        self, o2: float, c2: float, o1: float, c1: float, o: float, c: float
    ) -> bool:
        """Detect three black crows: 3 consecutive bearish with lower closes."""
        return (
            self._is_bearish(o2, c2)
            and self._is_bearish(o1, c1)
            and self._is_bearish(o, c)
            and c1 < c2
            and c < c1
            and o1 < o2
            and o < o1
        )
