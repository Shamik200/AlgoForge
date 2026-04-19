"""Data models for structural confluence detection.

Represents individual price levels (swings, POCs, moving averages)
and clustered confluence zones where multiple levels overlap.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class LevelType(str, Enum):
    """Type of structural price level."""

    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"
    POC = "poc"  # Point of Control from Volume Profile
    VAH = "vah"  # Value Area High
    VAL = "val"  # Value Area Low
    DYNAMIC_RESISTANCE = "dynamic_resistance"  # e.g., KAMA, EMA from above
    DYNAMIC_SUPPORT = "dynamic_support"        # e.g., KAMA, EMA from below


class PriceLevel(BaseModel):
    """A single objective price level of support or resistance.
    
    Attributes:
        price: The exact price of the level.
        level_type: The type of structure (swing, POC, etc.).
        strength: Objective strength score (0.0 to 1.0).
            - For swings: touches * recency_weight
            - For POC/VAH/VAL: volume significance
            - For dynamic: distance/time-based significance
        age: Number of periods since this level was established or last touched.
    """

    price: float = Field(..., description="Exact price of the structural level")
    level_type: LevelType = Field(..., description="Type of structural level")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="Objective strength score")
    age: int = Field(default=0, ge=0, description="Periods since establishment/last touch")


class ConfluenceZone(BaseModel):
    """A clustered zone where multiple price levels converge.
    
    Replaces subjective trendlines with a quantifiable zone of support/resistance.
    
    Attributes:
        center_price: The volume-weighted or strength-weighted center of the zone.
        upper_bound: The top edge of the confluence zone.
        lower_bound: The bottom edge of the confluence zone.
        score: Total confluence score (0 to 5), representing the number and strength
               of converging structural elements. Score >= 3 is considered high confluence.
        contributing_levels: List of individual PriceLevels that make up this zone.
    """

    center_price: float = Field(..., description="Weighted center of the confluence zone")
    upper_bound: float = Field(..., description="Top edge of the zone")
    lower_bound: float = Field(..., description="Bottom edge of the zone")
    score: float = Field(..., ge=0.0, le=5.0, description="Total confluence score (0-5)")
    contributing_levels: list[PriceLevel] = Field(default_factory=list, description="Levels in this zone")

    @property
    def is_high_confluence(self) -> bool:
        """Return True if this zone represents high structural confluence (score >= 3.0)."""
        return self.score >= 3.0
