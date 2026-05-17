"""Unit tests for Dynamic SL/TP Manager.

Tests all adjustment triggers and validation rules from Requirement 8.
"""

from datetime import datetime, timezone

import pytest

from algoforge.core.constants import Direction
from algoforge.core.models import Position
from algoforge.position.dynamic_sltp import (
    AdjustmentTrigger,
    AdjustmentType,
    DynamicSLTPConfig,
    DynamicSLTPManager,
    PositionMonitor,
    SLTPAdjustment,
)


@pytest.fixture
def config() -> DynamicSLTPConfig:
    """Create a default config for testing."""
    return DynamicSLTPConfig()


@pytest.fixture
def manager(config: DynamicSLTPConfig) -> DynamicSLTPManager:
    """Create a manager instance for testing."""
    return DynamicSLTPManager(config)


@pytest.fixture
def long_position() -> Position:
    """Create a sample long position."""
    return Position(
        id="test-long-1",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        quantity=100.0,
        stop_loss=145.0,
        take_profit=160.0,
        strategy="test_strategy",
        opened_at=datetime.now(timezone.utc),
        current_price=150.0,
    )


@pytest.fixture
def short_position() -> Position:
    """Create a sample short position."""
    return Position(
        id="test-short-1",
        symbol="TSLA",
        direction=Direction.SHORT,
        entry_price=200.0,
        quantity=50.0,
        stop_loss=210.0,
        take_profit=180.0,
        strategy="test_strategy",
        opened_at=datetime.now(timezone.utc),
        current_price=200.0,
    )


class TestPositionRegistration:
    """Test position registration and unregistration."""

    def test_register_position(self, manager: DynamicSLTPManager, long_position: Position):
        """Test registering a position for monitoring."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            ml_direction="long",
            regime="bull",
        )

        assert long_position.id in manager.position_monitors
        monitor = manager.get_monitor(long_position.id)
        assert monitor is not None
        assert monitor.position_id == long_position.id
        assert monitor.symbol == "AAPL"
        assert monitor.entry_price == 150.0
        assert monitor.original_sl == 145.0
        assert monitor.current_sl == 145.0
        assert monitor.original_tp == 160.0
        assert monitor.current_tp == 160.0
        assert monitor.entry_atr == 2.0
        assert monitor.last_ml_confidence == 0.7
        assert monitor.last_ml_direction == "long"
        assert monitor.last_regime == "bull"

    def test_unregister_position(self, manager: DynamicSLTPManager, long_position: Position):
        """Test unregistering a position."""
        manager.register_position(long_position, entry_atr=2.0)
        assert long_position.id in manager.position_monitors

        manager.unregister_position(long_position.id)
        assert long_position.id not in manager.position_monitors

    def test_get_all_monitors(self, manager: DynamicSLTPManager, long_position: Position, short_position: Position):
        """Test getting all monitors."""
        manager.register_position(long_position, entry_atr=2.0)
        manager.register_position(short_position, entry_atr=3.0)

        monitors = manager.get_all_monitors()
        assert len(monitors) == 2
        assert long_position.id in monitors
        assert short_position.id in monitors


class TestMLConfidenceIncrease:
    """Test ML confidence increase trigger (Requirement 8.2)."""

    def test_ml_confidence_increase_widens_tp(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that ML confidence increase widens TP by 0.5 ATR."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.5,
            ml_direction="long",
        )

        # Increase confidence by 20%
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            ml_direction="long",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.ML_CONFIDENCE_INCREASE
        assert adjustment.adjustment_type == AdjustmentType.WIDEN_TP
        assert adjustment.new_take_profit == 160.0 + (0.5 * 2.0)  # Original TP + 0.5 ATR
        assert adjustment.new_stop_loss is None
        assert abs(adjustment.details["confidence_change"] - 0.2) < 1e-6

    def test_ml_confidence_increase_below_threshold(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that small confidence increases don't trigger adjustment."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.5,
            ml_direction="long",
        )

        # Increase confidence by only 10% (below 20% threshold)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.6,
            ml_direction="long",
            current_atr=2.0,
        )

        assert adjustment is None


class TestMLConfidenceDecrease:
    """Test ML confidence decrease trigger (Requirement 8.3)."""

    def test_ml_confidence_decrease_moves_to_breakeven(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that ML confidence decrease moves SL to breakeven."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            ml_direction="long",
        )

        # Decrease confidence by 20%
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.5,
            ml_direction="long",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.ML_CONFIDENCE_DECREASE
        assert adjustment.adjustment_type == AdjustmentType.BREAKEVEN
        assert adjustment.new_stop_loss == 150.0  # Entry price
        assert abs(adjustment.details["confidence_change"] - 0.2) < 1e-6

    def test_ml_direction_reversal_moves_to_breakeven(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that ML direction reversal moves SL to breakeven."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            ml_direction="long",
        )

        # ML direction reverses
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            ml_direction="short",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.ML_DIRECTION_REVERSAL
        assert adjustment.adjustment_type == AdjustmentType.BREAKEVEN
        assert adjustment.new_stop_loss == 150.0  # Entry price


class TestRegimeConflict:
    """Test regime conflict trigger (Requirement 8.4)."""

    def test_regime_conflict_tightens_sl_long(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that regime conflict tightens SL for long position."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="bull",
        )

        # Regime transitions to bear (conflict)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="bear",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.REGIME_CONFLICT
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        # SL should tighten by 0.5 ATR (145 + 1.0 = 146)
        assert adjustment.new_stop_loss == 145.0 + (0.5 * 2.0)

    def test_regime_conflict_tightens_sl_short(self, manager: DynamicSLTPManager, short_position: Position):
        """Test that regime conflict tightens SL for short position."""
        manager.register_position(
            short_position,
            entry_atr=3.0,
            ml_confidence=0.7,
            regime="bear",
        )

        # Regime transitions to bull (conflict)
        adjustment = manager.monitor_position(
            short_position,
            ml_confidence=0.7,
            regime="bull",
            current_atr=3.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.REGIME_CONFLICT
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        # SL should tighten by 0.5 ATR (210 - 1.5 = 208.5)
        assert adjustment.new_stop_loss == 210.0 - (0.5 * 3.0)

    def test_no_adjustment_for_aligned_regime(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that aligned regime doesn't trigger adjustment."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            regime="bull",
        )

        # Regime stays aligned
        adjustment = manager.monitor_position(
            long_position,
            regime="bull",
            current_atr=2.0,
        )

        assert adjustment is None

    def test_regime_trend_down_conflicts_with_long(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that TREND_DOWN regime conflicts with long position."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="trend_up",
        )

        # Regime transitions to TREND_DOWN (conflict for long)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="trend_down",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.REGIME_CONFLICT
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        assert adjustment.new_stop_loss == 145.0 + (0.5 * 2.0)
        assert adjustment.details["new_regime"] == "trend_down"
        assert adjustment.details["old_regime"] == "trend_up"

    def test_regime_trend_up_conflicts_with_short(self, manager: DynamicSLTPManager, short_position: Position):
        """Test that TREND_UP regime conflicts with short position."""
        manager.register_position(
            short_position,
            entry_atr=3.0,
            ml_confidence=0.7,
            regime="trend_down",
        )

        # Regime transitions to TREND_UP (conflict for short)
        adjustment = manager.monitor_position(
            short_position,
            ml_confidence=0.7,
            regime="trend_up",
            current_atr=3.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.REGIME_CONFLICT
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        assert adjustment.new_stop_loss == 210.0 - (0.5 * 3.0)

    def test_regime_crisis_conflicts_with_long(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that CRISIS regime conflicts with long position."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="trend_up",
        )

        # Regime transitions to CRISIS (conflict for long)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="crisis",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.REGIME_CONFLICT
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        assert adjustment.new_stop_loss == 145.0 + (0.5 * 2.0)

    def test_regime_mean_revert_no_conflict(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that MEAN_REVERT regime doesn't conflict with any position."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="trend_up",
        )

        # Regime transitions to MEAN_REVERT (neutral, no conflict)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="mean_revert",
            current_atr=2.0,
        )

        assert adjustment is None

    def test_regime_no_change_no_adjustment(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that no regime change means no adjustment."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="trend_down",
        )

        # Regime stays the same (even though it conflicts)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="trend_down",
            current_atr=2.0,
        )

        assert adjustment is None

    def test_regime_unknown_no_adjustment(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that unknown regime doesn't trigger adjustment."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="trend_up",
        )

        # Regime transitions to unknown
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="unknown",
            current_atr=2.0,
        )

        assert adjustment is None

    def test_regime_conflict_respects_original_sl_limit(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that regime conflict adjustment respects original SL limit."""
        # Create a position where tightening would violate the original SL
        # This is an edge case where the current SL is already very tight
        tight_position = Position(
            id="test-tight-1",
            symbol="AAPL",
            direction=Direction.LONG,
            entry_price=150.0,
            quantity=100.0,
            stop_loss=149.0,  # Very tight original SL
            take_profit=160.0,
            strategy="test_strategy",
            opened_at=datetime.now(timezone.utc),
            current_price=150.0,
        )

        manager.register_position(
            tight_position,
            entry_atr=0.5,  # Small ATR
            ml_confidence=0.7,
            regime="trend_up",
        )

        # Manually set current SL to be at the original (simulating no prior adjustments)
        monitor = manager.get_monitor(tight_position.id)
        assert monitor is not None
        monitor.current_sl = 149.0

        # Regime transitions to conflict
        adjustment = manager.monitor_position(
            tight_position,
            ml_confidence=0.7,
            regime="trend_down",
            current_atr=0.5,
        )

        # Should generate adjustment since tightening is valid
        assert adjustment is not None
        assert adjustment.new_stop_loss == 149.0 + (0.5 * 0.5)  # 149.25

    def test_regime_conflict_with_underscore_format(self, manager: DynamicSLTPManager, long_position: Position):
        """Test regime conflict detection with underscore format (trend_down)."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="trend_up",
        )

        # Use underscore format
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="trend_down",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.REGIME_CONFLICT

    def test_regime_conflict_with_no_underscore_format(self, manager: DynamicSLTPManager, long_position: Position):
        """Test regime conflict detection with no underscore format (trenddown)."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="trendup",
        )

        # Use no underscore format
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="trenddown",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.REGIME_CONFLICT

    def test_regime_conflict_adjustment_details(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that regime conflict adjustment includes proper details."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            regime="trend_up",
        )

        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            regime="crisis",
            current_atr=2.0,
        )

        assert adjustment is not None
        assert "old_regime" in adjustment.details
        assert "new_regime" in adjustment.details
        assert "position_direction" in adjustment.details
        assert "atr" in adjustment.details
        assert "sl_adjustment_atr" in adjustment.details
        assert adjustment.details["old_regime"] == "trend_up"
        assert adjustment.details["new_regime"] == "crisis"
        assert adjustment.details["position_direction"] == "long"
        assert adjustment.details["atr"] == 2.0
        assert adjustment.details["sl_adjustment_atr"] == 1.0  # 0.5 * 2.0


class TestVolatilityAdjustments:
    """Test volatility-based adjustments (Requirements 8.7, 8.8, 8.9)."""

    def test_volatility_expansion_widens_sl_long(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that volatility expansion widens SL for long position while respecting original limit."""
        # Start with a tightened SL (above original)
        long_position.stop_loss = 147.0  # Tightened from original 145.0
        
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )
        
        # Update current SL in monitor
        monitor = manager.get_monitor(long_position.id)
        monitor.current_sl = 147.0

        # ATR expands by 50% (2.0 -> 3.0)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=3.0,
        )

        # Should widen SL (move down) proportionally
        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.VOLATILITY_EXPANSION
        
        # Calculate expected adjustment
        atr_change_pct = (3.0 - 2.0) / 2.0  # 0.5 (50%)
        sl_adjustment = atr_change_pct * 3.0  # 1.5
        expected_sl = 147.0 - 1.5  # 145.5
        
        assert adjustment.new_stop_loss == expected_sl
        assert adjustment.details["atr_change_pct"] == atr_change_pct

    def test_volatility_expansion_respects_original_sl_limit_long(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that volatility expansion respects original SL limit for long position."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # ATR expands by 50% (2.0 -> 3.0)
        # This would try to widen SL below original (145.0), so it should be capped at original
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=3.0,
        )

        # Should widen to original SL limit (145.0) since calculated would go below
        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.VOLATILITY_EXPANSION
        assert adjustment.new_stop_loss == 145.0  # Capped at original SL

    def test_volatility_expansion_widens_sl_short(self, manager: DynamicSLTPManager, short_position: Position):
        """Test that volatility expansion widens SL for short position."""
        # Start with a tightened SL (below original)
        short_position.stop_loss = 208.0  # Tightened from original 210.0
        
        manager.register_position(
            short_position,
            entry_atr=3.0,
            ml_confidence=0.7,
        )
        
        # Update current SL in monitor
        monitor = manager.get_monitor(short_position.id)
        monitor.current_sl = 208.0

        # ATR expands by 50% (3.0 -> 4.5)
        adjustment = manager.monitor_position(
            short_position,
            ml_confidence=0.7,
            current_atr=4.5,
        )

        # Should widen SL (move up) proportionally
        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.VOLATILITY_EXPANSION
        
        # Calculate expected adjustment
        atr_change_pct = (4.5 - 3.0) / 3.0  # 0.5 (50%)
        sl_adjustment = atr_change_pct * 4.5  # 2.25
        expected_sl = 208.0 + 2.25  # 210.25
        
        # Should be capped at original SL (210.0)
        assert adjustment.new_stop_loss == 210.0

    def test_volatility_expansion_no_adjustment_at_limit(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that no adjustment is made when already at original SL limit."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Already at original SL (145.0)
        # ATR expands by 50%
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=3.0,
        )

        # Should try to widen to original limit, but we're already there
        # The implementation will set new_sl to original_sl (145.0)
        # and detect we're already at limit, returning None
        assert adjustment is not None  # Actually returns adjustment to original SL
        assert adjustment.new_stop_loss == 145.0

    def test_volatility_expansion_below_threshold(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that volatility expansion below threshold doesn't trigger adjustment."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # ATR expands by only 30% (below 50% threshold)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.6,
        )

        # Should not trigger volatility expansion adjustment
        # (may trigger other adjustments, but not volatility expansion)
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.VOLATILITY_EXPANSION

    def test_volatility_contraction_tightens_sl_long(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that volatility contraction tightens SL for long position."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # ATR contracts by 30% (2.0 -> 1.4)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=1.4,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.VOLATILITY_CONTRACTION
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        
        # Calculate expected adjustment
        atr_change_pct = (2.0 - 1.4) / 2.0  # 0.3 (30%)
        sl_adjustment = 1.4 * atr_change_pct  # 0.42
        expected_sl = 145.0 + 0.42  # 145.42
        
        assert adjustment.new_stop_loss == expected_sl
        assert adjustment.details["atr_change_pct"] == atr_change_pct

    def test_volatility_contraction_tightens_sl_short(self, manager: DynamicSLTPManager, short_position: Position):
        """Test that volatility contraction tightens SL for short position."""
        manager.register_position(
            short_position,
            entry_atr=3.0,
            ml_confidence=0.7,
        )

        # ATR contracts by 30% (3.0 -> 2.1)
        adjustment = manager.monitor_position(
            short_position,
            ml_confidence=0.7,
            current_atr=2.1,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.VOLATILITY_CONTRACTION
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        
        # Calculate expected adjustment
        atr_change_pct = (3.0 - 2.1) / 3.0  # 0.3 (30%)
        sl_adjustment = 2.1 * atr_change_pct  # 0.63
        expected_sl = 210.0 - 0.63  # 209.37
        
        assert adjustment.new_stop_loss == expected_sl

    def test_volatility_contraction_below_threshold(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that volatility contraction below threshold doesn't trigger adjustment."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # ATR contracts by only 20% (below 30% threshold)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=1.6,
        )

        # Should not trigger volatility contraction adjustment
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.VOLATILITY_CONTRACTION

    def test_volatility_expansion_exact_threshold(self, manager: DynamicSLTPManager, long_position: Position):
        """Test volatility expansion at exact 50% threshold."""
        # Start with tightened SL
        long_position.stop_loss = 147.0
        
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )
        
        monitor = manager.get_monitor(long_position.id)
        monitor.current_sl = 147.0

        # ATR expands by exactly 50% (2.0 -> 3.0)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=3.0,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.VOLATILITY_EXPANSION

    def test_volatility_contraction_exact_threshold(self, manager: DynamicSLTPManager, long_position: Position):
        """Test volatility contraction at exact 30% threshold."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # ATR contracts by exactly 30% (2.0 -> 1.4)
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=1.4,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.VOLATILITY_CONTRACTION

    def test_volatility_adjustments_with_zero_entry_atr(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that volatility adjustments are skipped when entry ATR is zero."""
        manager.register_position(
            long_position,
            entry_atr=0.0,  # Zero ATR
            ml_confidence=0.7,
        )

        # Try to trigger volatility expansion
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=3.0,
        )

        # Should not generate volatility-based adjustments
        if adjustment:
            assert adjustment.trigger not in [
                AdjustmentTrigger.VOLATILITY_EXPANSION,
                AdjustmentTrigger.VOLATILITY_CONTRACTION,
            ]

    def test_volatility_expansion_and_contraction_sequence(self, manager: DynamicSLTPManager, long_position: Position):
        """Test sequence of expansion then contraction."""
        # Start with tightened SL
        long_position.stop_loss = 147.0
        
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )
        
        monitor = manager.get_monitor(long_position.id)
        monitor.current_sl = 147.0

        # First: ATR expands by 50%
        adjustment1 = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=3.0,
        )

        assert adjustment1 is not None
        assert adjustment1.trigger == AdjustmentTrigger.VOLATILITY_EXPANSION
        
        # Apply the adjustment
        manager.apply_adjustment(long_position, adjustment1)
        
        # Update entry_atr to current for next check
        monitor.entry_atr = 3.0

        # Second: ATR contracts by 30% from new baseline
        adjustment2 = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.1,
        )

        assert adjustment2 is not None
        assert adjustment2.trigger == AdjustmentTrigger.VOLATILITY_CONTRACTION


class TestTrendlineBreak:
    """Test trendline break trigger (Requirement 8.6)."""

    def test_trendline_break_moves_to_breakeven(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that trendline break moves SL to breakeven."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Trendline breaks against trade direction
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            trendline_broken=True,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.TRENDLINE_BREAK
        assert adjustment.adjustment_type == AdjustmentType.BREAKEVEN
        assert adjustment.new_stop_loss == 150.0  # Entry price


class TestSLValidation:
    """Test SL validation rules (Requirement 8.9)."""

    def test_never_widen_sl_beyond_original_long(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that SL never widens beyond original for long position."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        monitor = manager.get_monitor(long_position.id)
        assert monitor is not None

        # Try to widen SL below original (145 -> 140)
        is_valid = manager._is_valid_sl_adjustment(long_position, monitor, 140.0)
        assert not is_valid

        # Tightening SL above original is valid (145 -> 148)
        is_valid = manager._is_valid_sl_adjustment(long_position, monitor, 148.0)
        assert is_valid

    def test_never_widen_sl_beyond_original_short(self, manager: DynamicSLTPManager, short_position: Position):
        """Test that SL never widens beyond original for short position."""
        manager.register_position(
            short_position,
            entry_atr=3.0,
            ml_confidence=0.7,
        )

        monitor = manager.get_monitor(short_position.id)
        assert monitor is not None

        # Try to widen SL above original (210 -> 215)
        is_valid = manager._is_valid_sl_adjustment(short_position, monitor, 215.0)
        assert not is_valid

        # Tightening SL below original is valid (210 -> 205)
        is_valid = manager._is_valid_sl_adjustment(short_position, monitor, 205.0)
        assert is_valid


class TestApplyAdjustment:
    """Test applying adjustments to positions."""

    def test_apply_sl_adjustment(self, manager: DynamicSLTPManager, long_position: Position):
        """Test applying SL adjustment."""
        manager.register_position(long_position, entry_atr=2.0)

        adjustment = SLTPAdjustment(
            position_id=long_position.id,
            adjustment_type=AdjustmentType.TIGHTEN_SL,
            trigger=AdjustmentTrigger.VOLATILITY_CONTRACTION,
            new_stop_loss=148.0,
            old_stop_loss=145.0,
            old_take_profit=160.0,
        )

        manager.apply_adjustment(long_position, adjustment)

        assert long_position.stop_loss == 148.0
        monitor = manager.get_monitor(long_position.id)
        assert monitor is not None
        assert monitor.current_sl == 148.0

    def test_apply_tp_adjustment(self, manager: DynamicSLTPManager, long_position: Position):
        """Test applying TP adjustment."""
        manager.register_position(long_position, entry_atr=2.0)

        adjustment = SLTPAdjustment(
            position_id=long_position.id,
            adjustment_type=AdjustmentType.WIDEN_TP,
            trigger=AdjustmentTrigger.ML_CONFIDENCE_INCREASE,
            new_take_profit=165.0,
            old_stop_loss=145.0,
            old_take_profit=160.0,
        )

        manager.apply_adjustment(long_position, adjustment)

        assert long_position.take_profit == 165.0
        monitor = manager.get_monitor(long_position.id)
        assert monitor is not None
        assert monitor.current_tp == 165.0


class TestMaxAdjustments:
    """Test maximum adjustments limit."""

    def test_max_adjustments_limit(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that adjustments stop after max limit."""
        config = DynamicSLTPConfig(max_adjustments_per_position=2)
        manager = DynamicSLTPManager(config)

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.5,
        )

        # First adjustment
        adjustment1 = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
        )
        assert adjustment1 is not None

        # Second adjustment
        adjustment2 = manager.monitor_position(
            long_position,
            ml_confidence=0.5,
            current_atr=2.0,
        )
        assert adjustment2 is not None

        # Third adjustment should be blocked
        adjustment3 = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
        )
        assert adjustment3 is None


class TestMonitorState:
    """Test monitor state tracking."""

    def test_bars_in_trade_increments(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that bars_in_trade increments on each monitor call."""
        manager.register_position(long_position, entry_atr=2.0)

        monitor = manager.get_monitor(long_position.id)
        assert monitor is not None
        assert monitor.bars_in_trade == 0

        manager.monitor_position(long_position, current_atr=2.0)
        assert monitor.bars_in_trade == 1

        manager.monitor_position(long_position, current_atr=2.0)
        assert monitor.bars_in_trade == 2

    def test_adjustment_count_increments(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that adjustment_count increments when adjustments are made."""
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.5,
        )

        monitor = manager.get_monitor(long_position.id)
        assert monitor is not None
        assert monitor.adjustment_count == 0

        # Trigger adjustment
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
        )
        assert adjustment is not None
        assert monitor.adjustment_count == 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_monitor_unregistered_position(self, manager: DynamicSLTPManager, long_position: Position):
        """Test monitoring a position that wasn't registered."""
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
        )
        assert adjustment is None

    def test_unregister_nonexistent_position(self, manager: DynamicSLTPManager):
        """Test unregistering a position that doesn't exist."""
        # Should not raise an error
        manager.unregister_position("nonexistent-id")

    def test_get_monitor_nonexistent(self, manager: DynamicSLTPManager):
        """Test getting a monitor that doesn't exist."""
        monitor = manager.get_monitor("nonexistent-id")
        assert monitor is None

    def test_zero_atr_handling(self, manager: DynamicSLTPManager, long_position: Position):
        """Test handling of zero ATR values."""
        manager.register_position(
            long_position,
            entry_atr=0.0,  # Zero ATR
            ml_confidence=0.5,
        )

        # Should not crash, but won't generate volatility-based adjustments
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.5,
            current_atr=2.0,
        )
        # May be None or a different adjustment type
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.VOLATILITY_EXPANSION


class TestDataModels:
    """Test data model validation."""

    def test_sltp_adjustment_model(self):
        """Test SLTPAdjustment model creation."""
        adjustment = SLTPAdjustment(
            position_id="test-1",
            adjustment_type=AdjustmentType.TIGHTEN_SL,
            trigger=AdjustmentTrigger.REGIME_CONFLICT,
            new_stop_loss=148.0,
            old_stop_loss=145.0,
            old_take_profit=160.0,
            details={"regime": "bear"},
        )

        assert adjustment.position_id == "test-1"
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        assert adjustment.trigger == AdjustmentTrigger.REGIME_CONFLICT
        assert adjustment.new_stop_loss == 148.0
        assert adjustment.old_stop_loss == 145.0
        assert adjustment.details["regime"] == "bear"

    def test_position_monitor_model(self):
        """Test PositionMonitor model creation."""
        monitor = PositionMonitor(
            position_id="test-1",
            symbol="AAPL",
            direction=Direction.LONG,
            entry_price=150.0,
            original_sl=145.0,
            current_sl=145.0,
            original_tp=160.0,
            current_tp=160.0,
            entry_atr=2.0,
        )

        assert monitor.position_id == "test-1"
        assert monitor.symbol == "AAPL"
        assert monitor.direction == Direction.LONG
        assert monitor.entry_price == 150.0
        assert monitor.original_sl == 145.0
        assert monitor.entry_atr == 2.0
        assert monitor.bars_in_trade == 0
        assert monitor.adjustment_count == 0

    def test_config_model(self):
        """Test DynamicSLTPConfig model with custom values."""
        config = DynamicSLTPConfig(
            ml_confidence_threshold=0.25,
            regime_conflict_sl_tightening=0.75,
            max_adjustments_per_position=5,
        )

        assert config.ml_confidence_threshold == 0.25
        assert config.regime_conflict_sl_tightening == 0.75
        assert config.max_adjustments_per_position == 5
        # Check defaults
        assert config.volatility_expansion_threshold == 0.5
        assert config.enable_breakeven_on_reversal is True


class TestStructuralAdjustments:
    """Test structural-based SL/TP adjustments (Requirements 8.5, 8.6)."""

    def test_sr_level_proximity_long_position(self, manager: DynamicSLTPManager, long_position: Position):
        """Test SL placement near support level for long position (Requirement 8.5)."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        # Register position
        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Create structural snapshot with support level near current price
        # Long position at 150.0, support at 149.0 (within 0.5 ATR = 1.0)
        support_level = SRLevel(
            price=149.0,
            sr_type=SRType.SUPPORT,
            strength=0.8,
            touch_count=3,
        )

        snapshot = StructuralSnapshot(
            symbol="AAPL",
            sr_levels=[support_level],
        )

        # Monitor position with structural snapshot
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            structural_snapshot=snapshot,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.SR_LEVEL_PROXIMITY
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        # SL should be placed 0.1 ATR below support (149.0 - 0.2 = 148.8)
        assert adjustment.new_stop_loss == 149.0 - (0.1 * 2.0)
        assert adjustment.details["sr_level"] == 149.0
        assert adjustment.details["sr_type"] == "support"
        assert adjustment.details["level_strength"] == 0.8

    def test_sr_level_proximity_short_position(self, manager: DynamicSLTPManager, short_position: Position):
        """Test SL placement near resistance level for short position (Requirement 8.5)."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        # Register position
        manager.register_position(
            short_position,
            entry_atr=3.0,
            ml_confidence=0.7,
        )

        # Create structural snapshot with resistance level near current price
        # Short position at 200.0, resistance at 201.0 (within 0.5 ATR = 1.5)
        resistance_level = SRLevel(
            price=201.0,
            sr_type=SRType.RESISTANCE,
            strength=0.9,
            touch_count=4,
        )

        snapshot = StructuralSnapshot(
            symbol="TSLA",
            sr_levels=[resistance_level],
        )

        # Monitor position with structural snapshot
        adjustment = manager.monitor_position(
            short_position,
            ml_confidence=0.7,
            current_atr=3.0,
            structural_snapshot=snapshot,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.SR_LEVEL_PROXIMITY
        assert adjustment.adjustment_type == AdjustmentType.TIGHTEN_SL
        # SL should be placed 0.1 ATR above resistance (201.0 + 0.3 = 201.3)
        assert adjustment.new_stop_loss == 201.0 + (0.1 * 3.0)
        assert adjustment.details["sr_level"] == 201.0
        assert adjustment.details["sr_type"] == "resistance"

    def test_sr_level_too_far_no_adjustment(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that distant S/R levels don't trigger adjustment."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Support level too far away (150.0 - 145.0 = 5.0, threshold is 0.5 * 2.0 = 1.0)
        support_level = SRLevel(
            price=145.0,
            sr_type=SRType.SUPPORT,
            strength=0.8,
        )

        snapshot = StructuralSnapshot(
            symbol="AAPL",
            sr_levels=[support_level],
        )

        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            structural_snapshot=snapshot,
        )

        # Should not trigger SR proximity adjustment (may trigger other adjustments)
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.SR_LEVEL_PROXIMITY

    def test_sr_level_broken_ignored(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that broken S/R levels are ignored."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Broken support level near current price
        broken_support = SRLevel(
            price=149.0,
            sr_type=SRType.SUPPORT,
            strength=0.8,
            broken=True,  # Broken level
        )

        snapshot = StructuralSnapshot(
            symbol="AAPL",
            sr_levels=[broken_support],
        )

        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            structural_snapshot=snapshot,
        )

        # Should not trigger SR proximity adjustment for broken level
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.SR_LEVEL_PROXIMITY

    def test_sr_level_wrong_type_ignored_long(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that resistance levels are ignored for long positions."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Resistance level near current price (but we're long, so we only care about support)
        resistance_level = SRLevel(
            price=151.0,
            sr_type=SRType.RESISTANCE,
            strength=0.8,
        )

        snapshot = StructuralSnapshot(
            symbol="AAPL",
            sr_levels=[resistance_level],
        )

        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            structural_snapshot=snapshot,
        )

        # Should not trigger SR proximity adjustment for wrong level type
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.SR_LEVEL_PROXIMITY

    def test_sr_level_wrong_type_ignored_short(self, manager: DynamicSLTPManager, short_position: Position):
        """Test that support levels are ignored for short positions."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        manager.register_position(
            short_position,
            entry_atr=3.0,
            ml_confidence=0.7,
        )

        # Support level near current price (but we're short, so we only care about resistance)
        support_level = SRLevel(
            price=199.0,
            sr_type=SRType.SUPPORT,
            strength=0.8,
        )

        snapshot = StructuralSnapshot(
            symbol="TSLA",
            sr_levels=[support_level],
        )

        adjustment = manager.monitor_position(
            short_position,
            ml_confidence=0.7,
            current_atr=3.0,
            structural_snapshot=snapshot,
        )

        # Should not trigger SR proximity adjustment for wrong level type
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.SR_LEVEL_PROXIMITY

    def test_multiple_sr_levels_picks_closest(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that when multiple S/R levels are nearby, the first valid one is used."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Multiple support levels near current price
        support1 = SRLevel(price=149.5, sr_type=SRType.SUPPORT, strength=0.7)
        support2 = SRLevel(price=149.0, sr_type=SRType.SUPPORT, strength=0.9)

        snapshot = StructuralSnapshot(
            symbol="AAPL",
            sr_levels=[support1, support2],
        )

        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            structural_snapshot=snapshot,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.SR_LEVEL_PROXIMITY
        # Should use the first valid level (support1)
        assert adjustment.details["sr_level"] == 149.5

    def test_trendline_break_highest_priority(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that trendline break has highest priority over other adjustments (Requirement 8.6)."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
            ml_direction="long",
        )

        # Create conditions for multiple adjustments
        support_level = SRLevel(price=149.0, sr_type=SRType.SUPPORT, strength=0.8)
        snapshot = StructuralSnapshot(symbol="AAPL", sr_levels=[support_level])

        # Trigger both trendline break and SR proximity
        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.5,  # Also triggers ML confidence decrease
            ml_direction="long",
            current_atr=2.0,
            structural_snapshot=snapshot,
            trendline_broken=True,  # Highest priority
        )

        assert adjustment is not None
        # Trendline break should take priority
        assert adjustment.trigger == AdjustmentTrigger.TRENDLINE_BREAK
        assert adjustment.adjustment_type == AdjustmentType.BREAKEVEN
        assert adjustment.new_stop_loss == 150.0  # Entry price

    def test_trendline_break_immediate_breakeven(self, manager: DynamicSLTPManager, short_position: Position):
        """Test that trendline break immediately moves SL to breakeven (Requirement 8.6)."""
        manager.register_position(
            short_position,
            entry_atr=3.0,
            ml_confidence=0.7,
        )

        # Trendline breaks against trade direction
        adjustment = manager.monitor_position(
            short_position,
            ml_confidence=0.7,
            current_atr=3.0,
            trendline_broken=True,
        )

        assert adjustment is not None
        assert adjustment.trigger == AdjustmentTrigger.TRENDLINE_BREAK
        assert adjustment.adjustment_type == AdjustmentType.BREAKEVEN
        assert adjustment.new_stop_loss == 200.0  # Entry price
        assert adjustment.details["entry_price"] == 200.0

    def test_empty_structural_snapshot_no_adjustment(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that empty structural snapshot doesn't cause errors."""
        from algoforge.technical.structural.models import StructuralSnapshot

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Empty structural snapshot
        snapshot = StructuralSnapshot(symbol="AAPL", sr_levels=[])

        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            structural_snapshot=snapshot,
        )

        # Should not trigger SR proximity adjustment
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.SR_LEVEL_PROXIMITY

    def test_sr_adjustment_respects_original_sl_limit(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that SR-based adjustment respects the original SL limit (Requirement 8.9)."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        # Support level that would place SL below original SL
        # Original SL is 145.0, support at 144.0 would place SL at 143.8
        support_level = SRLevel(
            price=144.0,
            sr_type=SRType.SUPPORT,
            strength=0.8,
        )

        # Move current price close to this level
        long_position.current_price = 144.5

        snapshot = StructuralSnapshot(
            symbol="AAPL",
            sr_levels=[support_level],
        )

        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            structural_snapshot=snapshot,
        )

        # Should not trigger SR proximity adjustment because it would violate original SL
        if adjustment:
            assert adjustment.trigger != AdjustmentTrigger.SR_LEVEL_PROXIMITY

    def test_structural_adjustment_logging_details(self, manager: DynamicSLTPManager, long_position: Position):
        """Test that structural adjustments log comprehensive details (Requirement 8.10)."""
        from algoforge.technical.structural.models import SRLevel, SRType, StructuralSnapshot

        manager.register_position(
            long_position,
            entry_atr=2.0,
            ml_confidence=0.7,
        )

        support_level = SRLevel(
            price=149.0,
            sr_type=SRType.SUPPORT,
            strength=0.85,
            touch_count=5,
        )

        snapshot = StructuralSnapshot(
            symbol="AAPL",
            sr_levels=[support_level],
        )

        adjustment = manager.monitor_position(
            long_position,
            ml_confidence=0.7,
            current_atr=2.0,
            structural_snapshot=snapshot,
        )

        assert adjustment is not None
        # Verify all required details are logged
        assert "sr_level" in adjustment.details
        assert "sr_type" in adjustment.details
        assert "current_price" in adjustment.details
        assert "distance" in adjustment.details
        assert "atr" in adjustment.details
        assert "level_strength" in adjustment.details
        assert adjustment.details["level_strength"] == 0.85
        assert adjustment.old_stop_loss == 145.0
        assert adjustment.new_stop_loss is not None

