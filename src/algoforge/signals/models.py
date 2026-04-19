"""Data models for signal generation and combination."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SignalDirection(str, Enum):
    """The intended direction of a trade signal."""

    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class SignalResult(BaseModel):
    """The standardized output of any signal strategy or family.
    
    This unified model allows the SignalCombiner to aggregate strategies
    objectively and without coupling to their internal logic.
    """

    family_name: str = Field(..., description="Name of the signal family (e.g., 'momentum')")
    score: float = Field(..., ge=-1.0, le=1.0, description="Normalized conviction score [-1.0, 1.0]")
    direction: SignalDirection = Field(..., description="The directional bias of the signal")
    is_valid: bool = Field(..., description="True if all confirmation filters passed")
    
    # Optional metadata for debugging and sub-signal tracking
    sub_scores: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, str | float | bool] = Field(default_factory=dict)
