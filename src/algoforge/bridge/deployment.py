"""Gradual deployment configuration for capital scaling."""

from dataclasses import dataclass, field


@dataclass
class ScalingThreshold:
    """A capital scaling threshold.

    When cumulative P&L percentage exceeds `pnl_pct`,
    capital allocation scales to `new_capital_pct`.
    """
    pnl_pct: float       # e.g., 0.05 = +5% P&L
    new_capital_pct: float  # e.g., 0.25 = scale to 25% capital


@dataclass
class DeploymentConfig:
    """Configuration for gradual capital deployment.

    Starts at a small capital percentage and scales up as the
    strategy proves itself in live trading.
    """
    initial_capital_pct: float = 0.10  # Start at 10%
    max_capital_pct: float = 1.0       # Never exceed 100%
    parallel_mode: bool = True          # Run paper + live simultaneously
    scaling_thresholds: list[ScalingThreshold] = field(default_factory=lambda: [
        ScalingThreshold(pnl_pct=0.05, new_capital_pct=0.25),   # +5% → 25%
        ScalingThreshold(pnl_pct=0.10, new_capital_pct=0.50),   # +10% → 50%
        ScalingThreshold(pnl_pct=0.20, new_capital_pct=0.75),   # +20% → 75%
        ScalingThreshold(pnl_pct=0.30, new_capital_pct=1.00),   # +30% → 100%
    ])

    def get_current_allocation(self, cumulative_pnl_pct: float) -> float:
        """Determine current capital allocation based on P&L.

        Args:
            cumulative_pnl_pct: Cumulative P&L as a percentage (e.g., 0.12 = +12%).

        Returns:
            Capital allocation percentage (0.0 to 1.0).
        """
        allocation = self.initial_capital_pct

        for threshold in sorted(self.scaling_thresholds, key=lambda t: t.pnl_pct):
            if cumulative_pnl_pct >= threshold.pnl_pct:
                allocation = threshold.new_capital_pct
            else:
                break

        return min(allocation, self.max_capital_pct)
