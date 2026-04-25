"""Unit tests for the Backtesting Engine."""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest

from algoforge.backtest.models import TradePnL
from algoforge.backtest.metrics import calculate_max_drawdown, calculate_metrics
from algoforge.backtest.monte_carlo import run_monte_carlo_drawdown
from algoforge.backtest.wfo import generate_expanding_windows
from algoforge.backtest.engine import BacktestEngine
from algoforge.paper.config import PaperTradingConfig


def test_max_drawdown():
    """Test max drawdown calculation on equity curve."""
    equity = pd.Series([100.0, 110.0, 99.0, 95.0, 105.0, 120.0, 108.0])
    # Peak is 110. Trough is 95. Drawdown = (110 - 95) / 110 = 15 / 110 = 0.13636
    # Later peak is 120. Trough is 108. Drawdown = (120 - 108) / 120 = 0.1
    # Max DD should be 0.13636
    dd = calculate_max_drawdown(equity)
    assert pytest.approx(dd, 0.001) == 0.13636


def test_calculate_metrics():
    """Test comprehensive metrics including the Sharpe haircut."""
    # Synthesize daily returns of +0.1% every day except one -1.0% day
    returns = [0.001] * 200 + [-0.01] + [0.001] * 51
    # 252 days total. Mean = roughly 0.000956. StdDev = roughly 0.00078
    
    equity_vals = [100000.0]
    for r in returns:
        equity_vals.append(equity_vals[-1] * (1 + r))
    
    equity_series = pd.Series(equity_vals)
    
    # Fake trades
    t1 = TradePnL("1", "AAPL", "long", 100, 110, 10, 100, 0.1, datetime.now(), datetime.now())
    t2 = TradePnL("2", "TSLA", "long", 200, 180, 10, -200, -0.1, datetime.now(), datetime.now())
    t3 = TradePnL("3", "MSFT", "short", 300, 290, 10, 100, 0.033, datetime.now(), datetime.now())
    
    metrics = calculate_metrics([t1, t2, t3], equity_series, 100000.0)
    
    assert metrics.total_trades == 3
    assert metrics.win_rate == 2/3
    assert metrics.profit_factor == 1.0  # (100+100) / 200
    assert metrics.expectancy == 0.0     # (100 - 200 + 100) / 3
    
    # Raw sharpe vs Haircut sharpe (Haircut must be exactly half)
    assert metrics.sharpe_ratio == pytest.approx(metrics.raw_sharpe_ratio / 2.0)


def test_monte_carlo():
    """Test monte carlo trade sequence shuffling."""
    # 10 trades, 8 wins of 100, 2 losses of 500
    trades = []
    for i in range(8):
        trades.append(TradePnL(str(i), "A", "long", 1, 1, 1, 100, 0.1, datetime.now(), datetime.now()))
    for i in range(2):
        trades.append(TradePnL(f"l_{i}", "A", "long", 1, 1, 1, -500, -0.1, datetime.now(), datetime.now()))
        
    # If the 2 losses happen back-to-back at the start, max DD is roughly 1000/capital.
    # If they are separated by wins, max DD is lower.
    mc_result = run_monte_carlo_drawdown(trades, 10000.0, num_simulations=500)
    
    assert mc_result is not None
    assert mc_result.num_simulations == 500
    # P95 should represent a sequence where losses cluster
    # P5 should represent a sequence where losses are perfectly spaced
    assert mc_result.p95_drawdown_pct >= mc_result.p50_drawdown_pct
    assert mc_result.p50_drawdown_pct >= mc_result.p5_drawdown_pct


def test_expanding_windows():
    """Test WFO expanding window generator."""
    df = pd.DataFrame({'Close': range(100)})
    
    # Train 40, Test 20
    folds = list(generate_expanding_windows(df, train_size_bars=40, test_size_bars=20))
    
    assert len(folds) == 3
    
    # Fold 1: Train 0-40, Test 40-60
    t1, v1 = folds[0]
    assert len(t1) == 40
    assert len(v1) == 20
    assert t1.index[-1] == 39
    assert v1.index[0] == 40
    
    # Fold 2: Train 0-60, Test 60-80
    t2, v2 = folds[1]
    assert len(t2) == 60
    assert len(v2) == 20
    
    # Fold 3: Train 0-80, Test 80-100
    t3, v3 = folds[2]
    assert len(t3) == 80
    assert len(v3) == 20


def test_backtest_engine_loop():
    """Test the fast-path backtest engine execution loop."""
    config = PaperTradingConfig(starting_capital=10000.0)
    engine = BacktestEngine(config)
    
    # Mock data: 10 bars
    dates = pd.date_range("2026-01-01", periods=10)
    df = pd.DataFrame({
        'Open': [100]*10,
        'High': [105]*10,
        'Low': [95]*10,
        'Close': [100]*10,
        'Volume': [1000]*10
    }, index=dates)
    
    # Mock strategy logic that generates one trade at bar 5
    def mock_strategy(row, oms):
        closed_trades = []
        if row.name == dates[5]:
            closed_trades.append(
                TradePnL("1", "AAPL", "long", 100, 110, 10, 100, 0.1, dates[0], dates[5])
            )
        return [], closed_trades
        
    result = engine.run("MockStrategy", df, mock_strategy)
    
    assert result.strategy_name == "MockStrategy"
    assert result.initial_capital == 10000.0
    assert result.final_capital == 10100.0  # 1 trade of +100
    assert len(result.trades) == 1
    assert len(result.equity_curve) == 10
    
    # Since only 1 trade, monte carlo should be skipped
    assert result.monte_carlo is None
