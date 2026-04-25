"""Data models for Alpha Decay Monitoring."""

from dataclasses import dataclass
from enum import Enum


class HealthStatus(str, Enum):
    """The operational status of a signal family."""
    HEALTHY = "healthy"      # Full conviction weight (multiplier = 1.0)
    DEGRADED = "degraded"    # Throttled conviction weight (multiplier = 0.5)
    PAUSED = "paused"        # Zero conviction weight (multiplier = 0.0)


@dataclass
class BaselineManifest:
    """The ground-truth expected performance from the backtest."""
    family_name: str
    expected_hit_rate: float
    expected_average_r: float
    expected_sharpe: float
    hit_rate_std_dev: float  # Standard deviation of hit rate across WFO folds


@dataclass
class HealthReport:
    """The result of evaluating a signal family's live performance."""
    family_name: str
    status: HealthStatus
    multiplier: float
    current_hit_rate: float
    current_average_r: float
    current_30d_sharpe: float
    hit_rate_z_score: float
    reason: str = "Operating normally."
