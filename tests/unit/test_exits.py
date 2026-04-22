"""Unit tests for the Multi-Target Exits module."""

import pytest

from algoforge.exits.manager import ExitManager
from algoforge.exits.stops import calculate_initial_stop
from algoforge.exits.tranches import split_into_tranches
from algoforge.risk.models import TradeDirection


def test_initial_stop_calculation():
    """Test ATR anchoring based on regime."""
    entry = 100.0
    atr = 2.0
    
    # Trending LONG (1.5 * 2 = 3). SL = 97.
    sl = calculate_initial_stop(entry, TradeDirection.LONG, atr, "trending")
    assert sl == 97.0
    
    # Ranging SHORT (1.0 * 2 = 2). SL = 102.
    sl = calculate_initial_stop(entry, TradeDirection.SHORT, atr, "ranging")
    assert sl == 102.0


def test_tranche_splitting():
    """Test splitting a trade into 50/30/20 tranches with TP levels."""
    entry = 100.0
    sl = 90.0 # Risk = 10
    total_size = 10000.0
    
    tranches = split_into_tranches(
        symbol="AAPL", direction=TradeDirection.LONG, sector="tech",
        entry_price=entry, initial_stop_loss=sl, 
        total_position_size_value=total_size, current_price=100.0
    )
    
    assert len(tranches) == 3
    
    t1, t2, t3 = tranches
    
    # Check parent ID links them
    assert t1.parent_trade_id == t2.parent_trade_id == t3.parent_trade_id
    
    # Check sizing
    assert t1.position_size_value == 5000.0
    assert t2.position_size_value == 3000.0
    assert t3.position_size_value == 2000.0
    
    # Check TPs
    assert t1.take_profit_price == 115.0 # 1.5R (10 * 1.5 = 15)
    assert t2.take_profit_price == 125.0 # 2.5R (10 * 2.5 = 25)
    assert t3.take_profit_price is None


def test_exit_manager_breakeven():
    """Test time-based breakeven logic."""
    manager = ExitManager(time_limit_candles=5)
    
    # Setup trade
    tranches = split_into_tranches(
        "AAPL", TradeDirection.LONG, "tech", 100.0, 90.0, 1000, 100.0
    )
    
    # Fast forward 4 candles.
    for _ in range(4):
        manager.evaluate_candle_close(tranches, current_atr=2.0)
        
    for t in tranches:
        assert t.stop_loss_price == 90.0 # Still at initial SL
        assert t.is_breakeven is False
        
    # Fast forward 1 more candle to hit limit.
    manager.evaluate_candle_close(tranches, current_atr=2.0)
    
    for t in tranches:
        assert t.stop_loss_price == 100.0 # Moved to entry
        assert t.is_breakeven is True


def test_exit_manager_trailing_stop():
    """Test trailing stop for tranche 3."""
    manager = ExitManager(time_limit_candles=50, trailing_atr_multiplier=2.0)
    
    tranches = split_into_tranches(
        "AAPL", TradeDirection.LONG, "tech", 100.0, 90.0, 1000, 100.0
    )
    t3 = tranches[2]
    
    # Price moves to 105, ATR = 2. Trail = 4. 
    # SL would be 105 - 4 = 101. 101 > entry (100), so it ratchets!
    t3.current_price = 105.0
    manager.evaluate_candle_close([t3], current_atr=2.0)
    assert t3.stop_loss_price == 101.0
    
    # Price moves down to 102. 102 - 4 = 98. 
    # Ratchet only goes UP, so SL should stay at 101.
    t3.current_price = 102.0
    manager.evaluate_candle_close([t3], current_atr=2.0)
    assert t3.stop_loss_price == 101.0
