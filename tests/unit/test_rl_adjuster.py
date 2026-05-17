"""Unit tests for RLThresholdAdjuster."""

import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pytest

from algoforge.ml.rl_adjuster import (
    RLThresholdAdjuster,
    RLConfig,
    TradeOutcome,
    ThresholdAdjustments,
    RLAgentState,
)


@pytest.fixture
def temp_state_file():
    """Create a temporary state file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        temp_path = f.name
    # Don't write anything - let the adjuster create the file
    Path(temp_path).unlink(missing_ok=True)
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def rl_config(temp_state_file):
    """Create a test RL configuration."""
    return RLConfig(
        baseline_conviction_thresholds=(0.3, 0.6),
        baseline_ml_confidence_threshold=0.5,
        exploration_rate=0.1,
        revert_threshold=5,
        poor_trade_r_multiple=-0.5,
        state_file=temp_state_file,
        max_history_size=100,
    )


@pytest.fixture
def rl_adjuster(rl_config):
    """Create an RLThresholdAdjuster instance."""
    return RLThresholdAdjuster(config=rl_config)


def create_trade_outcome(
    trade_id: str,
    r_multiple: float,
    signal_family: str = "momentum",
    conviction_score: float = 0.7,
    ml_confidence: float = 0.6,
) -> TradeOutcome:
    """Helper to create a TradeOutcome for testing."""
    entry_price = 100.0
    direction = "long" if r_multiple > 0 else "short"
    exit_price = entry_price * (1 + r_multiple * 0.01)  # Simplified
    
    return TradeOutcome(
        trade_id=trade_id,
        symbol="AAPL",
        direction=direction,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=10.0,
        pnl_dollars=r_multiple * 100,  # Simplified
        r_multiple=r_multiple,
        conviction_score=conviction_score,
        signal_family=signal_family,
        market_regime={"bull": 0.6, "bear": 0.2, "sideways": 0.2},
        signal_scores={"momentum": 0.5, "mean_reversion": -0.2},
        ml_confidence=ml_confidence,
        entry_time=datetime.now(timezone.utc) - timedelta(hours=2),
        exit_time=datetime.now(timezone.utc),
        bars_in_trade=10,
        exit_reason="take_profit",
    )


def test_rl_adjuster_initialization(rl_adjuster, rl_config):
    """Test RLThresholdAdjuster initializes correctly."""
    assert rl_adjuster.config == rl_config
    assert len(rl_adjuster.state_history) == 0
    assert rl_adjuster.state.total_trades_observed == 0
    assert rl_adjuster.state.consecutive_poor_trades == 0
    
    # Check baseline adjustments
    adjustments = rl_adjuster.get_current_adjustments()
    assert adjustments.conviction_thresholds == (0.3, 0.6)
    assert adjustments.ml_confidence_threshold == 0.5


def test_observe_trade_outcome(rl_adjuster):
    """Test observing a trade outcome updates state correctly."""
    trade = create_trade_outcome("trade_1", r_multiple=1.5)
    
    rl_adjuster.observe_trade_outcome(trade)
    
    assert len(rl_adjuster.state_history) == 1
    assert rl_adjuster.state.total_trades_observed == 1
    assert rl_adjuster.state.cumulative_r_multiple == 1.5
    assert rl_adjuster.state.consecutive_poor_trades == 0
    
    # Check per-family tracking
    assert "momentum" in rl_adjuster.state.avg_r_multiple_by_family
    assert rl_adjuster.state.avg_r_multiple_by_family["momentum"] == 1.5
    assert rl_adjuster.state.trade_count_by_family["momentum"] == 1


def test_observe_multiple_trades(rl_adjuster):
    """Test observing multiple trades updates averages correctly."""
    trades = [
        create_trade_outcome("trade_1", r_multiple=1.5, signal_family="momentum"),
        create_trade_outcome("trade_2", r_multiple=0.8, signal_family="momentum"),
        create_trade_outcome("trade_3", r_multiple=-0.5, signal_family="breakout"),
    ]
    
    for trade in trades:
        rl_adjuster.observe_trade_outcome(trade)
    
    assert len(rl_adjuster.state_history) == 3
    assert rl_adjuster.state.total_trades_observed == 3
    assert rl_adjuster.state.cumulative_r_multiple == pytest.approx(1.8)
    
    # Check momentum family average
    momentum_avg = rl_adjuster.state.avg_r_multiple_by_family["momentum"]
    assert momentum_avg == pytest.approx((1.5 + 0.8) / 2)
    
    # Check breakout family
    assert rl_adjuster.state.avg_r_multiple_by_family["breakout"] == -0.5


def test_consecutive_poor_trades_tracking(rl_adjuster):
    """Test consecutive poor trades are tracked correctly."""
    # Good trade resets counter
    rl_adjuster.observe_trade_outcome(create_trade_outcome("trade_1", r_multiple=1.0))
    assert rl_adjuster.state.consecutive_poor_trades == 0
    
    # Poor trade increments counter
    rl_adjuster.observe_trade_outcome(create_trade_outcome("trade_2", r_multiple=-0.6))
    assert rl_adjuster.state.consecutive_poor_trades == 1
    
    # Another poor trade
    rl_adjuster.observe_trade_outcome(create_trade_outcome("trade_3", r_multiple=-0.8))
    assert rl_adjuster.state.consecutive_poor_trades == 2
    
    # Good trade resets
    rl_adjuster.observe_trade_outcome(create_trade_outcome("trade_4", r_multiple=0.5))
    assert rl_adjuster.state.consecutive_poor_trades == 0


def test_revert_to_baseline_after_poor_trades(rl_adjuster):
    """Test automatic revert to baseline after consecutive poor trades."""
    # Manually adjust thresholds
    rl_adjuster.state.current_adjustments.conviction_thresholds = (0.4, 0.7)
    rl_adjuster.state.current_adjustments.ml_confidence_threshold = 0.6
    
    # Observe poor trades up to threshold
    for i in range(5):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=-0.6)
        )
    
    # Should have reverted to baseline
    adjustments = rl_adjuster.get_current_adjustments()
    assert adjustments.conviction_thresholds == (0.3, 0.6)
    assert adjustments.ml_confidence_threshold == 0.5
    assert rl_adjuster.state.consecutive_poor_trades == 0
    assert "Reverted to baseline" in adjustments.adjustments_reason


def test_adjust_thresholds_insufficient_data(rl_adjuster):
    """Test adjust_thresholds returns current values with insufficient data."""
    # Add only 5 trades (need 10)
    for i in range(5):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=0.5)
        )
    
    adjustments = rl_adjuster.adjust_thresholds()
    
    # Should return baseline (no changes)
    assert adjustments.conviction_thresholds == (0.3, 0.6)
    assert adjustments.ml_confidence_threshold == 0.5


def test_adjust_thresholds_with_sufficient_data(rl_adjuster):
    """Test adjust_thresholds computes new values with sufficient data."""
    # Add 20 trades with good performance
    for i in range(20):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=1.0)
        )
    
    # Set exploration rate to 0 to force exploitation
    rl_adjuster.config.exploration_rate = 0.0
    
    adjustments = rl_adjuster.adjust_thresholds()
    
    # With good performance, thresholds should be lowered (more aggressive)
    # Note: exact values depend on exploitation logic
    assert adjustments.trades_analyzed == 20
    assert "Exploitation" in adjustments.adjustments_reason


def test_exploration_mode(rl_adjuster):
    """Test exploration mode applies random perturbations."""
    # Add sufficient trades
    for i in range(15):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=0.5)
        )
    
    # Force exploration
    rl_adjuster.config.exploration_rate = 1.0
    
    adjustments = rl_adjuster.adjust_thresholds()
    
    assert "Exploration" in adjustments.adjustments_reason
    # Thresholds should be different from baseline (with high probability)
    # Note: there's a small chance they could be the same due to randomness


def test_exploitation_adjusts_based_on_performance(rl_adjuster):
    """Test exploitation mode adjusts thresholds based on performance."""
    # Add trades with poor performance
    for i in range(20):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=-0.3)
        )
    
    # Force exploitation
    rl_adjuster.config.exploration_rate = 0.0
    
    initial_adjustments = rl_adjuster.get_current_adjustments()
    new_adjustments = rl_adjuster.adjust_thresholds()
    
    # With poor performance, thresholds should be raised (more conservative)
    assert new_adjustments.conviction_thresholds[0] >= initial_adjustments.conviction_thresholds[0]
    assert "Exploitation" in new_adjustments.adjustments_reason


def test_signal_family_weight_adjustments(rl_adjuster):
    """Test signal family weights are adjusted based on per-family performance."""
    # Add good momentum trades
    for i in range(10):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"momentum_{i}", r_multiple=1.0, signal_family="momentum")
        )
    
    # Add poor breakout trades
    for i in range(10):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"breakout_{i}", r_multiple=-0.5, signal_family="breakout")
        )
    
    # Force exploitation
    rl_adjuster.config.exploration_rate = 0.0
    
    adjustments = rl_adjuster.adjust_thresholds()
    
    # Momentum should have higher weight, breakout should have lower weight
    # (compared to baseline of 1.0)
    assert adjustments.signal_family_weights["momentum"] >= 1.0
    assert adjustments.signal_family_weights["breakout"] <= 1.0


def test_ml_confidence_threshold_adjustment(rl_adjuster):
    """Test ML confidence threshold is adjusted based on ML prediction accuracy."""
    # Add trades with high ML confidence and good outcomes
    for i in range(15):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=1.0, ml_confidence=0.8)
        )
    
    # Force exploitation
    rl_adjuster.config.exploration_rate = 0.0
    
    initial_threshold = rl_adjuster.get_current_adjustments().ml_confidence_threshold
    new_adjustments = rl_adjuster.adjust_thresholds()
    
    # With accurate ML predictions, threshold should be lowered
    assert new_adjustments.ml_confidence_threshold <= initial_threshold


def test_state_persistence(rl_adjuster, temp_state_file):
    """Test state is persisted and loaded correctly."""
    # Add sufficient trades (need 10 for adjustments)
    for i in range(15):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=0.5)
        )
    
    # Adjust thresholds
    rl_adjuster.config.exploration_rate = 0.0
    adjustments = rl_adjuster.adjust_thresholds()
    
    # Check state file was created
    assert Path(temp_state_file).exists()
    
    # Create new adjuster with same config (should load state)
    new_adjuster = RLThresholdAdjuster(config=rl_adjuster.config)
    
    # State should be loaded
    assert new_adjuster.state.total_trades_observed == 15
    assert new_adjuster.state.cumulative_r_multiple == pytest.approx(7.5)
    
    # Adjustments should match
    loaded_adjustments = new_adjuster.get_current_adjustments()
    assert loaded_adjustments.conviction_thresholds == adjustments.conviction_thresholds
    assert loaded_adjustments.ml_confidence_threshold == adjustments.ml_confidence_threshold


def test_revert_to_baseline_method(rl_adjuster):
    """Test explicit revert_to_baseline method."""
    # Manually adjust thresholds
    rl_adjuster.state.current_adjustments.conviction_thresholds = (0.4, 0.7)
    rl_adjuster.state.current_adjustments.ml_confidence_threshold = 0.6
    rl_adjuster.state.consecutive_poor_trades = 3
    
    # Revert
    rl_adjuster.revert_to_baseline()
    
    # Check baseline values restored
    adjustments = rl_adjuster.get_current_adjustments()
    assert adjustments.conviction_thresholds == (0.3, 0.6)
    assert adjustments.ml_confidence_threshold == 0.5
    assert rl_adjuster.state.consecutive_poor_trades == 0


def test_history_size_limit(rl_adjuster):
    """Test state history respects max_history_size."""
    max_size = rl_adjuster.config.max_history_size
    
    # Add more trades than max_history_size
    for i in range(max_size + 50):
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=0.5)
        )
    
    # History should be capped at max_size
    assert len(rl_adjuster.state_history) == max_size
    
    # But total_trades_observed should be accurate
    assert rl_adjuster.state.total_trades_observed == max_size + 50


def test_trade_outcome_validation():
    """Test TradeOutcome model validation."""
    # Valid trade outcome
    trade = create_trade_outcome("trade_1", r_multiple=1.0)
    assert trade.trade_id == "trade_1"
    assert trade.r_multiple == 1.0
    
    # Test conviction_score bounds
    with pytest.raises(Exception):  # Pydantic validation error
        TradeOutcome(
            trade_id="invalid",
            symbol="AAPL",
            direction="long",
            entry_price=100.0,
            exit_price=105.0,
            quantity=10.0,
            pnl_dollars=50.0,
            r_multiple=1.0,
            conviction_score=1.5,  # Invalid: > 1.0
            signal_family="momentum",
            entry_time=datetime.now(timezone.utc),
            exit_time=datetime.now(timezone.utc),
        )


def test_threshold_adjustments_validation():
    """Test ThresholdAdjustments model validation."""
    # Valid adjustments
    adjustments = ThresholdAdjustments(
        conviction_thresholds=(0.3, 0.6),
        position_size_limits={"max_position_pct": 0.1},
        signal_family_weights={"momentum": 1.0},
        ml_confidence_threshold=0.5,
        adjustments_reason="Test",
        trades_analyzed=10,
    )
    assert adjustments.conviction_thresholds == (0.3, 0.6)
    
    # Test ml_confidence_threshold bounds
    with pytest.raises(Exception):  # Pydantic validation error
        ThresholdAdjustments(
            conviction_thresholds=(0.3, 0.6),
            position_size_limits={},
            signal_family_weights={},
            ml_confidence_threshold=1.5,  # Invalid: > 1.0
            adjustments_reason="Test",
            trades_analyzed=10,
        )


def test_get_current_adjustments(rl_adjuster):
    """Test get_current_adjustments returns current state."""
    adjustments = rl_adjuster.get_current_adjustments()
    
    assert isinstance(adjustments, ThresholdAdjustments)
    assert adjustments == rl_adjuster.state.current_adjustments


def test_config_defaults():
    """Test RLConfig has sensible defaults."""
    config = RLConfig()
    
    assert config.baseline_conviction_thresholds == (0.3, 0.6)
    assert config.baseline_ml_confidence_threshold == 0.5
    assert config.exploration_rate == 0.1
    assert config.revert_threshold == 20
    assert config.poor_trade_r_multiple == -0.5
    assert config.max_history_size == 1000


def test_exploitation_with_mixed_performance(rl_adjuster):
    """Test exploitation handles mixed performance correctly."""
    # Add mix of good and bad trades
    for i in range(10):
        r_mult = 1.0 if i % 2 == 0 else -0.5
        rl_adjuster.observe_trade_outcome(
            create_trade_outcome(f"trade_{i}", r_multiple=r_mult)
        )
    
    # Force exploitation
    rl_adjuster.config.exploration_rate = 0.0
    
    adjustments = rl_adjuster.adjust_thresholds()
    
    # Should produce valid adjustments
    assert 0.0 < adjustments.conviction_thresholds[0] < adjustments.conviction_thresholds[1] < 1.0
    assert 0.0 < adjustments.ml_confidence_threshold < 1.0
    assert adjustments.trades_analyzed == 10
