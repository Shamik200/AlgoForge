"""Data models for the Backtesting Engine."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class TradePnL:
    """Represents the outcome of a single closed trade/tranche."""
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl_amount: float
    pnl_pct: float
    opened_at: datetime
    closed_at: datetime
    friction_cost: float = 0.0


@dataclass
class MetricsResult:
    """Comprehensive performance metrics."""
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float  # Haircut applied
    sortino_ratio: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    expectancy: float
    total_trades: int
    raw_sharpe_ratio: float # Without haircut for reference


@dataclass
class MonteCarloResult:
    """Results from trade sequence shuffling."""
    p5_drawdown_pct: float
    p50_drawdown_pct: float
    p95_drawdown_pct: float
    num_simulations: int


@dataclass
class BacktestResult:
    """The complete result of a backtest run."""
    strategy_name: str
    initial_capital: float
    final_capital: float
    metrics: MetricsResult
    monte_carlo: MonteCarloResult | None
    trades: list[TradePnL] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    metadata: dict[str, Any] = field(default_factory=dict)
