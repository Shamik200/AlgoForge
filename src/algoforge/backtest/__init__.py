"""Backtesting Engine module."""

from algoforge.backtest.models import TradePnL, MetricsResult, MonteCarloResult, BacktestResult
from algoforge.backtest.metrics import calculate_metrics, calculate_max_drawdown
from algoforge.backtest.monte_carlo import run_monte_carlo_drawdown
from algoforge.backtest.wfo import generate_expanding_windows
from algoforge.backtest.engine import BacktestEngine

__all__ = [
    "TradePnL",
    "MetricsResult",
    "MonteCarloResult",
    "BacktestResult",
    "calculate_metrics",
    "calculate_max_drawdown",
    "run_monte_carlo_drawdown",
    "generate_expanding_windows",
    "BacktestEngine"
]
