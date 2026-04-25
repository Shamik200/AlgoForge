"""Unit tests for the Alpha Decay Monitoring System."""

from datetime import datetime
import pandas as pd

from algoforge.backtest.models import TradePnL
from algoforge.decay.models import BaselineManifest, HealthStatus
from algoforge.decay.monitor import AlphaDecayMonitor
from algoforge.combination.engine import CombinationEngine
from algoforge.signals.models import SignalResult, SignalDirection
import pytest


def test_monitor_healthy():
    """Test monitor returns healthy when trades match baseline."""
    monitor = AlphaDecayMonitor()
    baseline = BaselineManifest("momentum", 0.5, 0.02, 1.0, 0.05)
    
    # 10 trades, 6 wins (60% hit rate, > baseline 50%)
    trades = []
    for _ in range(6):
        trades.append(TradePnL("w", "AAPL", "long", 10, 11, 1, 1, 0.1, datetime.now(), datetime.now()))
    for _ in range(4):
        trades.append(TradePnL("l", "AAPL", "long", 10, 9, 1, -1, -0.1, datetime.now(), datetime.now()))
        
    equity = pd.Series([100.0, 101.0, 102.0, 101.0, 103.0])  # Fake up-trending equity
    
    report = monitor.evaluate_family_health("momentum", trades, equity, baseline)
    assert report.status == HealthStatus.HEALTHY
    assert report.multiplier == 1.0


def test_monitor_degraded_sharpe():
    """Test monitor throttles to 0.5 when Sharpe drops below 0."""
    monitor = AlphaDecayMonitor()
    baseline = BaselineManifest("momentum", 0.5, 0.0, 1.0, 0.05)
    
    # 10 trades, 5 wins, 5 losses. 
    trades = []
    for _ in range(5):
        trades.append(TradePnL("w", "AAPL", "long", 10, 11, 1, 1, 0.1, datetime.now(), datetime.now()))
    for _ in range(5):
        trades.append(TradePnL("l", "AAPL", "long", 10, 9, 1, -1, -0.1, datetime.now(), datetime.now()))
        
    # Fake down-trending equity for negative Sharpe
    equity = pd.Series([100.0, 99.0, 98.0, 97.0, 96.0]) 
    
    report = monitor.evaluate_family_health("momentum", trades, equity, baseline)
    assert report.status == HealthStatus.DEGRADED
    assert report.multiplier == 0.5


def test_monitor_paused_hit_rate():
    """Test monitor pauses when hit rate deviation > 2σ."""
    monitor = AlphaDecayMonitor()
    # Baseline: 50% hit rate, 5% std_dev. (2σ is 10%, so < 40% should pause)
    baseline = BaselineManifest("momentum", 0.5, -0.06, 1.0, 0.05)
    
    # 10 trades, 2 wins, 8 losses (20% hit rate)
    trades = []
    for _ in range(2):
        trades.append(TradePnL("w", "AAPL", "long", 10, 11, 1, 1, 0.1, datetime.now(), datetime.now()))
    for _ in range(8):
        trades.append(TradePnL("l", "AAPL", "long", 10, 9, 1, -1, -0.1, datetime.now(), datetime.now()))
        
    equity = pd.Series([100.0, 99.0, 98.0, 97.0, 96.0]) 
    
    report = monitor.evaluate_family_health("momentum", trades, equity, baseline)
    assert report.status == HealthStatus.PAUSED
    assert report.multiplier == 0.0
    assert report.hit_rate_z_score < -2.0


def test_monitor_paused_average_r():
    """Test monitor pauses when Average R drops below 50% of expected."""
    monitor = AlphaDecayMonitor()
    baseline = BaselineManifest("momentum", 0.5, 2.0, 1.0, 0.05)
    
    # Fake trades with terrible R (avg pnl_pct around 0.1, baseline wants 2.0)
    trades = []
    for _ in range(10):
        trades.append(TradePnL("t", "AAPL", "long", 10, 10.1, 1, 0.1, 0.01, datetime.now(), datetime.now()))
        
    equity = pd.Series([100.0, 100.1, 100.2]) 
    
    report = monitor.evaluate_family_health("momentum", trades, equity, baseline)
    assert report.status == HealthStatus.PAUSED
    assert report.multiplier == 0.0


def test_combination_engine_health_multipliers():
    """Test Combination Engine correctly applies multipliers and re-normalizes."""
    engine = CombinationEngine()
    
    sig1 = SignalResult(family_name="momentum", score=1.0, direction=SignalDirection.LONG, is_valid=True)
    sig2 = SignalResult(family_name="mean_rev", score=1.0, direction=SignalDirection.LONG, is_valid=True)
    
    sharpes = {"momentum": 1.0, "mean_rev": 1.0} # Softmax should weight them 50/50
    
    # First without multipliers
    res1 = engine.combine([sig1, sig2], sharpes)
    import json
    weights1 = json.loads(res1.metadata["weights"])
    assert pytest.approx(weights1["momentum"], 0.01) == 0.5
    assert pytest.approx(weights1["mean_rev"], 0.01) == 0.5
    
    # Now throttle momentum to 0.5
    multipliers = {"momentum": 0.5, "mean_rev": 1.0}
    res2 = engine.combine([sig1, sig2], sharpes, health_multipliers=multipliers)
    weights2 = json.loads(res2.metadata["weights"])
    
    # momentum was 0.5 * 0.5 = 0.25
    # mean_rev was 0.5 * 1.0 = 0.50
    # Total = 0.75. Re-normalized:
    # momentum = 0.25 / 0.75 = 0.333
    # mean_rev = 0.50 / 0.75 = 0.666
    assert pytest.approx(weights2["momentum"], 0.01) == 0.333
    assert pytest.approx(weights2["mean_rev"], 0.01) == 0.666
    
    # Now pause momentum entirely (0.0)
    multipliers_paused = {"momentum": 0.0, "mean_rev": 1.0}
    res3 = engine.combine([sig1, sig2], sharpes, health_multipliers=multipliers_paused)
    weights3 = json.loads(res3.metadata["weights"])
    assert weights3.get("momentum", 0.0) == 0.0
    assert pytest.approx(weights3["mean_rev"], 0.01) == 1.0
