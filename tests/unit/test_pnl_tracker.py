"""Unit tests for EnhancedPnLTracker."""

from datetime import datetime, timedelta, timezone

import pytest

from algoforge.core.constants import Direction
from algoforge.pnl.tracker import (
    EnhancedPnLTracker,
    FamilyMetrics,
    PortfolioMetrics,
    TradeMetrics,
)


@pytest.fixture
def tracker():
    """Create a fresh tracker instance."""
    return EnhancedPnLTracker(initial_capital=100_000.0)


def test_tracker_initialization(tracker):
    """Test tracker initializes with correct values."""
    assert tracker._initial_capital == 100_000.0
    assert tracker._total_capital == 100_000.0
    assert tracker._allocated_capital == 0.0
    assert tracker._peak_capital == 100_000.0
    assert len(tracker._open_positions) == 0
    assert len(tracker._trade_history) == 0


def test_record_trade_open_long(tracker):
    """Test recording a long trade opening."""
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
        conviction_score=0.75,
    )

    assert len(tracker._open_positions) == 1
    assert "pos1" in tracker._open_positions

    pos = tracker._open_positions["pos1"]
    assert pos["symbol"] == "AAPL"
    assert pos["direction"] == Direction.LONG
    assert pos["entry_price"] == 150.0
    assert pos["stop_loss"] == 145.0
    assert pos["quantity"] == 100
    assert pos["signal_family"] == "momentum"
    assert pos["conviction_score"] == 0.75
    assert pos["initial_risk"] == 500.0  # (150 - 145) * 100
    assert pos["capital_allocated"] == 15_000.0  # 150 * 100

    assert tracker._allocated_capital == 15_000.0


def test_record_trade_open_short(tracker):
    """Test recording a short trade opening."""
    tracker.record_trade_open(
        position_id="pos1",
        symbol="TSLA",
        direction=Direction.SHORT,
        entry_price=200.0,
        stop_loss=210.0,
        quantity=50,
        signal_family="mean_reversion",
        conviction_score=0.65,
    )

    pos = tracker._open_positions["pos1"]
    assert pos["direction"] == Direction.SHORT
    assert pos["initial_risk"] == 500.0  # (210 - 200) * 50
    assert pos["capital_allocated"] == 10_000.0  # 200 * 50


def test_record_trade_close_long_profit(tracker):
    """Test closing a profitable long trade."""
    # Open trade
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
        conviction_score=0.75,
    )

    # Close trade at profit
    metrics = tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
        commission=10.0,
        slippage=5.0,
    )

    # Verify metrics
    assert metrics.trade_id == "pos1"
    assert metrics.symbol == "AAPL"
    assert metrics.signal_family == "momentum"
    assert metrics.entry_price == 150.0
    assert metrics.exit_price == 160.0
    assert metrics.quantity == 100
    assert metrics.direction == Direction.LONG

    # P&L calculations
    # Gross P&L: (160 - 150) * 100 = 1000
    # Net P&L: 1000 - 10 - 5 = 985
    assert metrics.pnl_dollars == 985.0
    assert metrics.pnl_percent == pytest.approx(6.6667, rel=1e-3)  # (160-150)/150 * 100
    assert metrics.r_multiple == pytest.approx(1.97, rel=1e-2)  # 985 / 500

    # Verify tracker state
    assert len(tracker._open_positions) == 0
    assert len(tracker._trade_history) == 1
    assert tracker._allocated_capital == 0.0
    assert tracker._total_capital == 100_985.0


def test_record_trade_close_long_loss(tracker):
    """Test closing a losing long trade."""
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )

    metrics = tracker.record_trade_close(
        position_id="pos1",
        exit_price=145.0,
        exit_reason="SL",
        commission=10.0,
    )

    # P&L: (145 - 150) * 100 - 10 = -510
    assert metrics.pnl_dollars == -510.0
    assert metrics.pnl_percent == pytest.approx(-3.3333, rel=1e-3)
    assert metrics.r_multiple == pytest.approx(-1.02, rel=1e-2)  # -510 / 500

    assert tracker._total_capital == 99_490.0


def test_record_trade_close_short_profit(tracker):
    """Test closing a profitable short trade."""
    tracker.record_trade_open(
        position_id="pos1",
        symbol="TSLA",
        direction=Direction.SHORT,
        entry_price=200.0,
        stop_loss=210.0,
        quantity=50,
        signal_family="mean_reversion",
    )

    metrics = tracker.record_trade_close(
        position_id="pos1",
        exit_price=180.0,
        exit_reason="TP",
        commission=10.0,
    )

    # P&L: (200 - 180) * 50 - 10 = 990
    assert metrics.pnl_dollars == 990.0
    # For short: price went from 200 to 180 = -10% price change, but inverted = +10% for short
    assert metrics.pnl_percent == pytest.approx(10.0, rel=1e-3)
    assert metrics.r_multiple == pytest.approx(1.98, rel=1e-2)  # 990 / 500


def test_record_trade_close_short_loss(tracker):
    """Test closing a losing short trade."""
    tracker.record_trade_open(
        position_id="pos1",
        symbol="TSLA",
        direction=Direction.SHORT,
        entry_price=200.0,
        stop_loss=210.0,
        quantity=50,
        signal_family="mean_reversion",
    )

    metrics = tracker.record_trade_close(
        position_id="pos1",
        exit_price=210.0,
        exit_reason="SL",
        commission=10.0,
    )

    # P&L: (200 - 210) * 50 - 10 = -510
    assert metrics.pnl_dollars == -510.0
    # For short: price went from 200 to 210 = +5% price change, but inverted = -5% for short
    assert metrics.pnl_percent == pytest.approx(-5.0, rel=1e-3)
    assert metrics.r_multiple == pytest.approx(-1.02, rel=1e-2)


def test_record_trade_close_nonexistent_position(tracker):
    """Test closing a position that doesn't exist raises error."""
    with pytest.raises(KeyError, match="Position pos999 not found"):
        tracker.record_trade_close(
            position_id="pos999",
            exit_price=100.0,
            exit_reason="TP",
        )


def test_multiple_open_positions(tracker):
    """Test tracking multiple open positions."""
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )

    tracker.record_trade_open(
        position_id="pos2",
        symbol="TSLA",
        direction=Direction.SHORT,
        entry_price=200.0,
        stop_loss=210.0,
        quantity=50,
        signal_family="mean_reversion",
    )

    tracker.record_trade_open(
        position_id="pos3",
        symbol="MSFT",
        direction=Direction.LONG,
        entry_price=300.0,
        stop_loss=290.0,
        quantity=30,
        signal_family="breakout",
    )

    assert len(tracker._open_positions) == 3
    assert tracker._allocated_capital == 15_000.0 + 10_000.0 + 9_000.0  # 34,000


def test_get_portfolio_metrics_no_trades(tracker):
    """Test portfolio metrics with no trades."""
    metrics = tracker.get_portfolio_metrics()

    assert metrics.total_capital == 100_000.0
    assert metrics.allocated_capital == 0.0
    assert metrics.available_capital == 100_000.0
    assert metrics.total_pnl_dollars == 0.0
    assert metrics.total_pnl_percent == 0.0
    assert metrics.win_rate == 0.0
    assert metrics.avg_r_multiple == 0.0
    assert metrics.total_trades == 0
    assert metrics.winning_trades == 0
    assert metrics.losing_trades == 0


def test_get_portfolio_metrics_with_trades(tracker):
    """Test portfolio metrics after multiple trades."""
    # Trade 1: Profit
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )
    tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
        commission=10.0,
    )

    # Trade 2: Loss
    tracker.record_trade_open(
        position_id="pos2",
        symbol="TSLA",
        direction=Direction.LONG,
        entry_price=200.0,
        stop_loss=190.0,
        quantity=50,
        signal_family="breakout",
    )
    tracker.record_trade_close(
        position_id="pos2",
        exit_price=190.0,
        exit_reason="SL",
        commission=10.0,
    )

    # Trade 3: Profit
    tracker.record_trade_open(
        position_id="pos3",
        symbol="MSFT",
        direction=Direction.SHORT,
        entry_price=300.0,
        stop_loss=310.0,
        quantity=20,
        signal_family="mean_reversion",
    )
    tracker.record_trade_close(
        position_id="pos3",
        exit_price=280.0,
        exit_reason="TP",
        commission=10.0,
    )

    metrics = tracker.get_portfolio_metrics()

    # Trade 1: +990, Trade 2: -510, Trade 3: +390 = +870
    assert metrics.total_pnl_dollars == 870.0
    assert metrics.total_pnl_percent == pytest.approx(0.87, rel=1e-2)
    assert metrics.total_trades == 3
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1
    assert metrics.win_rate == pytest.approx(66.67, rel=1e-2)
    assert metrics.cumulative_r_multiples > 0  # Net positive R


def test_get_family_metrics_no_trades(tracker):
    """Test family metrics with no trades."""
    metrics = tracker.get_family_metrics("momentum")

    assert metrics.family_name == "momentum"
    assert metrics.total_trades == 0
    assert metrics.win_rate == 0.0
    assert metrics.avg_r_multiple == 0.0
    assert metrics.total_pnl_dollars == 0.0


def test_get_family_metrics_with_trades(tracker):
    """Test family metrics after trades in that family."""
    # Momentum trade 1: Profit
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )
    tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
        commission=10.0,
    )

    # Momentum trade 2: Loss
    tracker.record_trade_open(
        position_id="pos2",
        symbol="GOOGL",
        direction=Direction.LONG,
        entry_price=100.0,
        stop_loss=95.0,
        quantity=50,
        signal_family="momentum",
    )
    tracker.record_trade_close(
        position_id="pos2",
        exit_price=95.0,
        exit_reason="SL",
        commission=10.0,
    )

    # Different family trade
    tracker.record_trade_open(
        position_id="pos3",
        symbol="TSLA",
        direction=Direction.SHORT,
        entry_price=200.0,
        stop_loss=210.0,
        quantity=50,
        signal_family="mean_reversion",
    )
    tracker.record_trade_close(
        position_id="pos3",
        exit_price=180.0,
        exit_reason="TP",
        commission=10.0,
    )

    metrics = tracker.get_family_metrics("momentum")

    assert metrics.family_name == "momentum"
    assert metrics.total_trades == 2
    assert metrics.winning_trades == 1
    assert metrics.losing_trades == 1
    assert metrics.win_rate == 50.0
    # Trade 1: +990, Trade 2: -260 = +730
    assert metrics.total_pnl_dollars == 730.0


def test_get_all_family_metrics(tracker):
    """Test getting metrics for all families."""
    # Create trades in different families
    families = ["momentum", "mean_reversion", "breakout"]

    for i, family in enumerate(families):
        tracker.record_trade_open(
            position_id=f"pos{i}",
            symbol="AAPL",
            direction=Direction.LONG,
            entry_price=150.0,
            stop_loss=145.0,
            quantity=100,
            signal_family=family,
        )
        tracker.record_trade_close(
            position_id=f"pos{i}",
            exit_price=160.0,
            exit_reason="TP",
        )

    all_metrics = tracker.get_all_family_metrics()

    assert len(all_metrics) == 3
    assert "momentum" in all_metrics
    assert "mean_reversion" in all_metrics
    assert "breakout" in all_metrics

    for family, metrics in all_metrics.items():
        assert metrics.family_name == family
        assert metrics.total_trades == 1


def test_drawdown_calculation(tracker):
    """Test drawdown calculation."""
    # Profitable trade - increases peak
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )
    tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
    )

    assert tracker._peak_capital == 101_000.0

    # Losing trade - creates drawdown
    tracker.record_trade_open(
        position_id="pos2",
        symbol="TSLA",
        direction=Direction.LONG,
        entry_price=200.0,
        stop_loss=190.0,
        quantity=50,
        signal_family="momentum",
    )
    tracker.record_trade_close(
        position_id="pos2",
        exit_price=190.0,
        exit_reason="SL",
    )

    metrics = tracker.get_portfolio_metrics()

    # Peak: 101,000, Current: 100,500, Drawdown: 500/101,000 = 0.495%
    assert metrics.max_drawdown_percent == pytest.approx(0.495, rel=1e-2)


def test_r_multiple_with_zero_risk(tracker):
    """Test R-multiple calculation when initial risk is zero."""
    # This shouldn't happen in practice, but test defensive code
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=150.0,  # Same as entry - zero risk
        quantity=100,
        signal_family="momentum",
    )

    metrics = tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
    )

    # Should handle division by zero gracefully
    assert metrics.r_multiple == 0.0


def test_sharpe_ratio_calculation(tracker):
    """Test Sharpe ratio calculation with multiple trades."""
    # Create several trades with varying returns
    trades = [
        (150.0, 160.0, 100),  # +6.67%
        (200.0, 190.0, 50),   # -5%
        (100.0, 110.0, 100),  # +10%
        (300.0, 295.0, 30),   # -1.67%
        (250.0, 270.0, 40),   # +8%
    ]

    for i, (entry, exit, qty) in enumerate(trades):
        tracker.record_trade_open(
            position_id=f"pos{i}",
            symbol="AAPL",
            direction=Direction.LONG,
            entry_price=entry,
            stop_loss=entry - 10,
            quantity=qty,
            signal_family="momentum",
        )
        tracker.record_trade_close(
            position_id=f"pos{i}",
            exit_price=exit,
            exit_reason="TP",
        )

    metrics = tracker.get_portfolio_metrics()

    # Should have a positive Sharpe ratio
    assert metrics.sharpe_ratio != 0.0


def test_sortino_ratio_calculation(tracker):
    """Test Sortino ratio calculation."""
    # Create trades with some losses
    trades = [
        (150.0, 160.0, 100),  # Profit
        (200.0, 190.0, 50),   # Loss
        (100.0, 110.0, 100),  # Profit
        (300.0, 290.0, 30),   # Loss
    ]

    for i, (entry, exit, qty) in enumerate(trades):
        tracker.record_trade_open(
            position_id=f"pos{i}",
            symbol="AAPL",
            direction=Direction.LONG,
            entry_price=entry,
            stop_loss=entry - 10,
            quantity=qty,
            signal_family="momentum",
        )
        tracker.record_trade_close(
            position_id=f"pos{i}",
            exit_price=exit,
            exit_reason="TP" if exit > entry else "SL",
        )

    metrics = tracker.get_portfolio_metrics()

    # Sortino should be calculated (may be positive or negative)
    assert metrics.sortino_ratio != 0.0


def test_get_trade_history(tracker):
    """Test retrieving trade history."""
    # Create some trades
    for i in range(3):
        tracker.record_trade_open(
            position_id=f"pos{i}",
            symbol="AAPL",
            direction=Direction.LONG,
            entry_price=150.0,
            stop_loss=145.0,
            quantity=100,
            signal_family="momentum",
        )
        tracker.record_trade_close(
            position_id=f"pos{i}",
            exit_price=160.0,
            exit_reason="TP",
        )

    history = tracker.get_trade_history()

    assert len(history) == 3
    assert all(isinstance(t, TradeMetrics) for t in history)


def test_get_open_positions_count(tracker):
    """Test getting count of open positions."""
    assert tracker.get_open_positions_count() == 0

    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )

    assert tracker.get_open_positions_count() == 1

    tracker.record_trade_open(
        position_id="pos2",
        symbol="TSLA",
        direction=Direction.SHORT,
        entry_price=200.0,
        stop_loss=210.0,
        quantity=50,
        signal_family="mean_reversion",
    )

    assert tracker.get_open_positions_count() == 2

    tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
    )

    assert tracker.get_open_positions_count() == 1


def test_reset(tracker):
    """Test resetting the tracker."""
    # Create some trades
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )
    tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
    )

    # Reset
    tracker.reset()

    # Verify everything is reset
    assert tracker._total_capital == 100_000.0
    assert tracker._allocated_capital == 0.0
    assert tracker._peak_capital == 100_000.0
    assert len(tracker._open_positions) == 0
    assert len(tracker._trade_history) == 0
    assert len(tracker._family_trades) == 0


def test_metadata_preservation(tracker):
    """Test that metadata is preserved through trade lifecycle."""
    metadata = {
        "regime": "trending",
        "ml_confidence": 0.85,
        "fingpt_prediction": "bullish",
    }

    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
        metadata=metadata,
    )

    metrics = tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
    )

    assert metrics.metadata == metadata


def test_time_in_trade_calculation(tracker):
    """Test that time in trade is calculated correctly."""
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )

    # Close immediately
    metrics = tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
    )

    # Time should be very small (milliseconds)
    assert metrics.time_in_trade.total_seconds() < 1.0
    assert isinstance(metrics.time_in_trade, timedelta)


def test_family_contribution_percentage(tracker):
    """Test family contribution percentage calculation."""
    # Momentum: +1000
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )
    tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
    )

    # Mean reversion: +500
    tracker.record_trade_open(
        position_id="pos2",
        symbol="TSLA",
        direction=Direction.SHORT,
        entry_price=200.0,
        stop_loss=210.0,
        quantity=50,
        signal_family="mean_reversion",
    )
    tracker.record_trade_close(
        position_id="pos2",
        exit_price=195.0,
        exit_reason="TP",
    )

    momentum_metrics = tracker.get_family_metrics("momentum")
    reversion_metrics = tracker.get_family_metrics("mean_reversion")

    # Total P&L: 1000 + 250 = 1250
    # Momentum: 1000/1250 = 80%
    # Mean reversion: 250/1250 = 20%
    assert momentum_metrics.contribution_percent == pytest.approx(80.0, rel=1e-1)
    assert reversion_metrics.contribution_percent == pytest.approx(20.0, rel=1e-1)


def test_available_capital_calculation(tracker):
    """Test available capital calculation."""
    metrics = tracker.get_portfolio_metrics()
    assert metrics.available_capital == 100_000.0

    # Open position
    tracker.record_trade_open(
        position_id="pos1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_loss=145.0,
        quantity=100,
        signal_family="momentum",
    )

    metrics = tracker.get_portfolio_metrics()
    # Total: 100,000, Allocated: 15,000, Available: 85,000
    assert metrics.available_capital == 85_000.0

    # Close position with profit
    tracker.record_trade_close(
        position_id="pos1",
        exit_price=160.0,
        exit_reason="TP",
    )

    metrics = tracker.get_portfolio_metrics()
    # Total: 101,000, Allocated: 0, Available: 101,000
    assert metrics.available_capital == 101_000.0
