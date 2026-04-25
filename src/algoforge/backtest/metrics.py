"""Metrics calculation engine for backtest results."""

import numpy as np
import pandas as pd

from algoforge.backtest.models import MetricsResult, TradePnL


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate the maximum peak-to-trough drawdown percentage.

    Args:
        equity_curve: A pandas Series of account equity over time.

    Returns:
        Max drawdown as a positive float (e.g., 0.15 for 15%).
    """
    if len(equity_curve) == 0:
        return 0.0

    rolling_max = equity_curve.cummax()
    drawdowns = (rolling_max - equity_curve) / rolling_max
    return float(drawdowns.max())


def calculate_metrics(
    trades: list[TradePnL],
    equity_curve: pd.Series,
    initial_capital: float,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252  # Default to daily
) -> MetricsResult:
    """Calculate comprehensive performance metrics.

    Args:
        trades: List of executed trades.
        equity_curve: Series of daily account equity.
        initial_capital: Starting capital amount.
        risk_free_rate: Annual risk-free rate (default 0.0).
        periods_per_year: Number of periods in a year (252 for daily).

    Returns:
        MetricsResult containing all calculated statistics.
    """
    if not trades or len(equity_curve) < 2:
        return MetricsResult(
            total_return_pct=0.0, max_drawdown_pct=0.0,
            sharpe_ratio=0.0, sortino_ratio=0.0, calmar_ratio=0.0,
            win_rate=0.0, profit_factor=0.0, expectancy=0.0,
            total_trades=0, raw_sharpe_ratio=0.0
        )

    # 1. Basic PnL Metrics
    final_equity = equity_curve.iloc[-1]
    total_return_pct = (final_equity - initial_capital) / initial_capital

    wins = [t for t in trades if t.pnl_amount > 0]
    losses = [t for t in trades if t.pnl_amount <= 0]
    
    total_trades = len(trades)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
    
    gross_profit = sum(t.pnl_amount for t in wins)
    gross_loss = abs(sum(t.pnl_amount for t in losses))
    
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
    
    expectancy = sum(t.pnl_amount for t in trades) / total_trades if total_trades > 0 else 0.0

    # 2. Drawdown
    max_dd = calculate_max_drawdown(equity_curve)

    # 3. Risk-Adjusted Returns (Sharpe, Sortino, Calmar)
    returns = equity_curve.pct_change().dropna()
    
    if len(returns) < 2 or returns.std() == 0:
        return MetricsResult(
            total_return_pct=total_return_pct, max_drawdown_pct=max_dd,
            sharpe_ratio=0.0, sortino_ratio=0.0, calmar_ratio=0.0,
            win_rate=win_rate, profit_factor=profit_factor, expectancy=expectancy,
            total_trades=total_trades, raw_sharpe_ratio=0.0
        )

    # Annualize return and vol
    mean_return = returns.mean()
    volatility = returns.std()
    
    annualized_return = mean_return * periods_per_year
    annualized_vol = volatility * np.sqrt(periods_per_year)
    
    raw_sharpe = (annualized_return - risk_free_rate) / annualized_vol
    
    # Apply the mandated Sharpe Haircut (divide by 2) for realistic expectations
    haircut_sharpe = raw_sharpe / 2.0

    # Sortino (downside deviation)
    downside_returns = returns[returns < 0]
    if len(downside_returns) > 0:
        downside_vol = downside_returns.std() * np.sqrt(periods_per_year)
        sortino = (annualized_return - risk_free_rate) / downside_vol if downside_vol > 0 else float('inf')
    else:
        sortino = float('inf')

    # Calmar (return over max drawdown)
    calmar = annualized_return / max_dd if max_dd > 0 else float('inf')

    return MetricsResult(
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_dd,
        sharpe_ratio=haircut_sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        win_rate=win_rate,
        profit_factor=profit_factor,
        expectancy=expectancy,
        total_trades=total_trades,
        raw_sharpe_ratio=raw_sharpe
    )
