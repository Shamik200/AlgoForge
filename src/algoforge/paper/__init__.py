"""Paper Trading Simulator module."""

from algoforge.paper.config import AssetClass, PaperTradingConfig, FillResult
from algoforge.paper.engine import PaperTradingEngine
from algoforge.paper.friction import (
    calculate_commissions,
    simulate_latency_drift,
    simulate_slippage,
    calculate_market_impact
)

__all__ = [
    "AssetClass",
    "PaperTradingConfig",
    "FillResult",
    "PaperTradingEngine",
    "calculate_commissions",
    "simulate_latency_drift",
    "simulate_slippage",
    "calculate_market_impact",
]
