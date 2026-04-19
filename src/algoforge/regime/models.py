"""Data models for market regime classification."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RegimeState(str, Enum):
    """The 4 core market regimes detected by the HMM."""

    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    MEAN_REVERT = "mean_revert"
    CRISIS = "crisis"  # Extreme stress/volatility


class RegimeProbabilities(BaseModel):
    """Continuous probability vector across all market regimes.
    
    Rather than a binary label, the engine provides probabilities for each state
    to allow downstream signals to adapt smoothly.
    
    Attributes:
        trend_up: Probability of an upward trending market (0.0 - 1.0).
        trend_down: Probability of a downward trending market (0.0 - 1.0).
        mean_revert: Probability of a ranging/mean-reverting market (0.0 - 1.0).
        crisis: Probability of extreme stress/volatility (0.0 - 1.0).
        uncertainty_flag: True if probabilities are too entropic (evenly spread) or conflict 
            with cross-asset heuristics (like extreme VIX). When True, positions 
            should be reduced.
    """

    trend_up: float = Field(..., ge=0.0, le=1.0)
    trend_down: float = Field(..., ge=0.0, le=1.0)
    mean_revert: float = Field(..., ge=0.0, le=1.0)
    crisis: float = Field(..., ge=0.0, le=1.0)
    uncertainty_flag: bool = Field(default=False)

    @property
    def dominant_regime(self) -> RegimeState:
        """Get the regime with the highest probability."""
        probs = {
            RegimeState.TREND_UP: self.trend_up,
            RegimeState.TREND_DOWN: self.trend_down,
            RegimeState.MEAN_REVERT: self.mean_revert,
            RegimeState.CRISIS: self.crisis,
        }
        # Max by value
        return max(probs.items(), key=lambda item: item[1])[0]

    @property
    def is_trending(self) -> bool:
        """Return True if trend probabilities dominate ranging probabilities."""
        return (self.trend_up + self.trend_down) > (self.mean_revert + self.crisis)
