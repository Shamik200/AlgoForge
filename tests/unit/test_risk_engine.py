"""Unit tests for the Risk Management Engine."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from algoforge.risk.correlation import CorrelationMatrix
from algoforge.risk.engine import RiskEngine
from algoforge.risk.limits import (
    check_account_limits,
    check_portfolio_limits,
    check_trade_limits,
)
from algoforge.risk.models import (
    AccountState,
    ActivePosition,
    TradeDirection,
    TradeLedger,
    TradeRecord,
)
from algoforge.risk.sizing import calculate_kelly_fraction, calculate_position_size


def test_kelly_sizing():
    """Test fractional Kelly and fallback sizing."""
    ledger = TradeLedger()
    
    # Under 30 trades should fallback to 1% fixed risk
    for _ in range(10):
        ledger.records.append(TradeRecord(
            symbol="AAPL", direction=TradeDirection.LONG, entry_price=100.0,
            exit_price=110.0, pnl_amount=10.0, pnl_percent=0.1
        ))
        
    risk_pct = calculate_kelly_fraction(ledger, kelly_multiplier=0.5, max_risk_pct=0.02)
    assert risk_pct == 0.01  # Fallback
    
    # Build up to 30 trades. 20 winners of +$10, 10 losers of -$5.
    # Win rate = 20/30 = 0.666
    # Avg win = 10, Avg loss = 5. Payoff Ratio = 2.0.
    # Full Kelly = W - ((1-W)/R) = 0.666 - (0.333/2) = 0.666 - 0.166 = 0.50
    # Half Kelly = 0.25
    ledger.records.clear()
    for _ in range(20):
        ledger.records.append(TradeRecord(
            symbol="AAPL", direction=TradeDirection.LONG, entry_price=100.0,
            exit_price=110.0, pnl_amount=10.0, pnl_percent=0.1
        ))
    for _ in range(10):
        ledger.records.append(TradeRecord(
            symbol="AAPL", direction=TradeDirection.LONG, entry_price=100.0,
            exit_price=95.0, pnl_amount=-5.0, pnl_percent=-0.05
        ))
        
    # Cap at max_risk_pct (e.g. 0.02)
    risk_pct = calculate_kelly_fraction(ledger, kelly_multiplier=0.5, max_risk_pct=0.02)
    assert risk_pct == 0.02  # Capped!
    
    # If we allow higher cap:
    risk_pct_uncapped = calculate_kelly_fraction(ledger, kelly_multiplier=0.5, max_risk_pct=1.0)
    assert risk_pct_uncapped == pytest.approx(0.25, 0.01)


def test_account_limits():
    """Test global account killswitches."""
    account = AccountState(current_equity=100000.0, peak_equity=100000.0)
    
    assert check_account_limits(account) is None
    
    # 25% drawdown
    bad_dd = AccountState(current_equity=75000.0, peak_equity=100000.0)
    assert "max_drawdown" in check_account_limits(bad_dd)
    
    # Daily loss > 5%
    bad_daily = AccountState(current_equity=100000.0, peak_equity=100000.0, daily_pnl=-6000.0)
    assert "max_daily_loss" in check_account_limits(bad_daily)
    
    # Consecutive losses
    bad_streak = AccountState(current_equity=100000.0, peak_equity=100000.0, consecutive_losses=6)
    assert "cooldown_active" in check_account_limits(bad_streak)


def test_portfolio_limits():
    """Test portfolio concentration and correlation."""
    account = AccountState(current_equity=100000.0, peak_equity=100000.0)
    corr_matrix = CorrelationMatrix()
    
    # Mock some data for correlation matrix
    df = pd.DataFrame({
        "AAPL": [0.01, 0.02, -0.01, 0.01],
        "MSFT": [0.01, 0.02, -0.01, 0.01],  # Perf correlation to AAPL
        "GOLD": [-0.01, -0.02, 0.01, -0.01] # Negative correlation
    })
    corr_matrix.update(df)
    
    active = [
        ActivePosition(symbol="AAPL", direction=TradeDirection.LONG, sector="tech", entry_price=100, current_price=100, position_size_value=20000.0)
    ]
    
    # Sector limit (Max 25%). AAPL is 20k. Trying to add 6k of MSFT tech. Total 26k (26%). Should fail.
    assert "sector_limit" in check_portfolio_limits(
        "MSFT", "tech", TradeDirection.LONG, 6000.0, active, account, corr_matrix
    )
    
    # Correlation limit. MSFT is highly correlated to AAPL. Adding LONG MSFT while LONG AAPL fails.
    # Note: Sector limit happens first in the function, so let's use different sector to test correlation specifically.
    assert "correlation_limit" in check_portfolio_limits(
        "MSFT", "other", TradeDirection.LONG, 1000.0, active, account, corr_matrix
    )
    
    # But SHORTING MSFT while LONG AAPL is fine (hedging)
    assert check_portfolio_limits(
        "MSFT", "other", TradeDirection.SHORT, 1000.0, active, account, corr_matrix
    ) is None


def test_trade_limits():
    """Test micro trade constraints."""
    # Circuit Breaker: Stock dropped 6% from open
    assert "circuit_breaker" in check_trade_limits(
        entry_price=94.0, stop_loss=90.0, take_profit=110.0,
        session_open_price=100.0, current_price=94.0,
        daily_volume=1000000, candidate_size=1000.0
    )
    
    # Bad RR: Risk 10, Reward 5 = 0.5 RR
    assert "insufficient_rr" in check_trade_limits(
        entry_price=100.0, stop_loss=90.0, take_profit=105.0,
        session_open_price=100.0, current_price=100.0,
        daily_volume=1000000, candidate_size=1000.0
    )


def test_engine_integration():
    """Test the full RiskEngine evaluation pipeline."""
    engine = RiskEngine()
    account = AccountState(current_equity=100000.0, peak_equity=100000.0)
    ledger = TradeLedger()
    
    eval_result = engine.evaluate_trade(
        symbol="AAPL", sector="tech", direction=TradeDirection.LONG,
        entry_price=100.0, stop_loss=95.0, take_profit=115.0,
        session_open_price=100.0, current_price=100.0, daily_volume=1000000,
        account=account, ledger=ledger, active_positions=[]
    )
    
    assert eval_result.is_approved is True
    # Default risk is 1%, so Risk Amount = 1000.
    # Entry=100, SL=95 -> Trade Risk = 5%.
    # Ideal Position Size = 20,000.
    # But Max Position Cap is 10% of equity (10,000).
    assert eval_result.allocated_capital == 10000.0
    assert eval_result.metadata["source"] == "fixed_fallback"
