"""Structural analysis data models.

Pydantic models for S/R levels, trendlines, channels, and trend direction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TrendDirection(str, Enum):
    """Bigger trend direction classification."""

    UP = "up"
    DOWN = "down"
    UNCLEAR = "unclear"


class SRType(str, Enum):
    """Support or Resistance."""

    SUPPORT = "support"
    RESISTANCE = "resistance"


class ChannelType(str, Enum):
    """Channel classification."""

    ASCENDING = "ascending"
    DESCENDING = "descending"
    HORIZONTAL = "horizontal"


class SRLevel(BaseModel):
    """A support or resistance level with strength scoring.

    Detected via fractal swing points with volume confirmation.
    Strength combines touch count, recency, volume, and reaction magnitude.
    """

    price: float = Field(..., gt=0, description="Price level")
    sr_type: SRType = Field(..., description="Support or resistance")
    strength: float = Field(default=0.0, ge=0, description="Strength score (higher = stronger)")
    touch_count: int = Field(default=1, ge=1, description="Number of times price touched this level")
    volume_weight: float = Field(default=1.0, ge=0, description="Volume-weighted importance")
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_touched: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    broken: bool = Field(default=False, description="True if level has been broken")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def age_hours(self) -> float:
        """Hours since first detected."""
        delta = datetime.now(timezone.utc) - self.first_seen
        return delta.total_seconds() / 3600


class SwingPoint(BaseModel):
    """A fractal swing high or swing low point."""

    index: int = Field(..., ge=0, description="Index in the candle array")
    price: float = Field(..., gt=0, description="Price at the swing point")
    is_high: bool = Field(..., description="True = swing high, False = swing low")
    volume: float = Field(default=0.0, ge=0, description="Volume at this point")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Trendline(BaseModel):
    """A trendline connecting swing points.

    Constructed by connecting 2+ fractal swing points.
    Ranked by touch count and recency.
    """

    slope: float = Field(..., description="Slope (price change per bar)")
    intercept: float = Field(..., description="Y-intercept (price at index 0)")
    touch_points: list[SwingPoint] = Field(default_factory=list, min_length=2)
    is_upper: bool = Field(..., description="True = resistance line (connects highs)")
    strength: float = Field(default=0.0, ge=0, description="Line strength score")
    broken: bool = Field(default=False, description="True if line has been broken")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def touch_count(self) -> int:
        """Number of swing points on this line."""
        return len(self.touch_points)

    def price_at(self, index: int) -> float:
        """Calculate trendline price at a given bar index."""
        return self.slope * index + self.intercept

    def distance_from(self, index: int, price: float) -> float:
        """Distance of a price from the trendline at given index."""
        return abs(price - self.price_at(index))


class Channel(BaseModel):
    """A price channel formed by upper + lower trendlines."""

    upper_line: Trendline = Field(..., description="Upper boundary (resistance)")
    lower_line: Trendline = Field(..., description="Lower boundary (support)")
    channel_type: ChannelType = Field(..., description="Ascending/descending/horizontal")
    width: float = Field(default=0.0, ge=0, description="Average channel width in price units")

    @property
    def midline_at(self) -> float:
        """Midline price at the latest index."""
        if self.upper_line.touch_points and self.lower_line.touch_points:
            last_idx = max(
                self.upper_line.touch_points[-1].index,
                self.lower_line.touch_points[-1].index,
            )
            return (
                self.upper_line.price_at(last_idx) + self.lower_line.price_at(last_idx)
            ) / 2
        return 0.0


class StructuralSnapshot(BaseModel):
    """Complete structural analysis for one symbol/timeframe pair.

    Contains S/R levels, trendlines, channels, and trend direction.
    """

    symbol: str
    sr_levels: list[SRLevel] = Field(default_factory=list)
    trendlines: list[Trendline] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)
    trend_direction: TrendDirection = Field(default=TrendDirection.UNCLEAR)
    swing_highs: list[SwingPoint] = Field(default_factory=list)
    swing_lows: list[SwingPoint] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def support_levels(self) -> list[SRLevel]:
        """Active support levels sorted by strength."""
        return sorted(
            [s for s in self.sr_levels if s.sr_type == SRType.SUPPORT and not s.broken],
            key=lambda x: x.strength,
            reverse=True,
        )

    @property
    def resistance_levels(self) -> list[SRLevel]:
        """Active resistance levels sorted by strength."""
        return sorted(
            [s for s in self.sr_levels if s.sr_type == SRType.RESISTANCE and not s.broken],
            key=lambda x: x.strength,
            reverse=True,
        )

    @property
    def active_trendlines(self) -> list[Trendline]:
        """Non-broken trendlines."""
        return [t for t in self.trendlines if not t.broken]
