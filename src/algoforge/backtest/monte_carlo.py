"""Monte Carlo simulation for robustness testing."""

import random

import numpy as np
import pandas as pd

from algoforge.backtest.models import TradePnL, MonteCarloResult
from algoforge.backtest.metrics import calculate_max_drawdown


def run_monte_carlo_drawdown(
    trades: list[TradePnL], 
    initial_capital: float, 
    num_simulations: int = 1000
) -> MonteCarloResult | None:
    """Run Monte Carlo simulation by shuffling trade sequence.

    This breaks the chronological serial correlation of trades to reveal the 
    distribution of maximum drawdowns if the exact same trades occurred in a 
    different (potentially worst-case) sequence.

    Args:
        trades: The list of executed trades from a backtest.
        initial_capital: The starting capital to simulate equity curves.
        num_simulations: Number of random shuffles to perform.

    Returns:
        MonteCarloResult containing P5, P50, and P95 drawdown percentiles, or None if no trades.
    """
    if not trades:
        return None

    # Extract just the PnL amounts
    pnl_amounts = [t.pnl_amount for t in trades]
    
    max_drawdowns = []

    for _ in range(num_simulations):
        # Shuffle the PnL sequence
        shuffled_pnls = pnl_amounts.copy()
        random.shuffle(shuffled_pnls)
        
        # Build synthetic equity curve
        # Start with initial capital, then cumsum the shuffled PnLs
        equity_values = [initial_capital]
        current_equity = initial_capital
        
        for pnl in shuffled_pnls:
            current_equity += pnl
            equity_values.append(current_equity)
            
        equity_series = pd.Series(equity_values)
        
        # Calculate max drawdown for this synthetic curve
        dd = calculate_max_drawdown(equity_series)
        max_drawdowns.append(dd)

    # Calculate percentiles (P95 is the worst drawdown, P5 is the best)
    # Using np.percentile, 95th percentile means 95% of drawdowns were BETTER (lower) than this.
    p5 = float(np.percentile(max_drawdowns, 5))
    p50 = float(np.percentile(max_drawdowns, 50))
    p95 = float(np.percentile(max_drawdowns, 95))

    return MonteCarloResult(
        p5_drawdown_pct=p5,
        p50_drawdown_pct=p50,
        p95_drawdown_pct=p95,
        num_simulations=num_simulations
    )
