from __future__ import annotations

from hypothesis import given, strategies as st

from algoforge.core.config import Settings
from algoforge.core.validator import validate_settings, ValidationResult
"""Property-based tests for ConfigValidator module.

**Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5, 16.6**

Property 7: Configuration Validation Completeness
For any SystemConfig instance, the ConfigValidator SHALL:
- Reject configs with invalid parameter values
- Reject configs with inconsistent risk parameters
- Reject configs with non-existent file paths
- Reject configs with missing required credentials when features are enabled
- Accept configs that satisfy all validation rules
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck

from algoforge.core.config import Settings
from algoforge.core.validator import ConfigValidator, validate_settings


# ============================================================================
# Hypothesis Strategies for Generating Test Data
# ============================================================================

@st.composite
def valid_percentage(draw):
    """Generate valid percentage values (0.0 to 100.0)."""
    return draw(st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False))


@st.composite
def invalid_percentage(draw):
    """Generate invalid percentage values (negative or > 100)."""
    return draw(st.one_of(
        st.floats(min_value=-1000.0, max_value=-0.01, allow_nan=False, allow_infinity=False),
        st.floats(min_value=100.01, max_value=1000.0, allow_nan=False, allow_infinity=False)
    ))


@st.composite
def positive_integer(draw, min_value=1, max_value=1000):
    """Generate positive integers."""
    return draw(st.integers(min_value=min_value, max_value=max_value))


@st.composite
def non_positive_integer(draw):
    """Generate non-positive integers."""
    return draw(st.integers(min_value=-1000, max_value=0))


@st.composite
def valid_risk_hierarchy(draw):
    """Generate valid risk parameter hierarchy: daily < drawdown."""
    daily_loss = draw(st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False))
    drawdown = draw(st.floats(min_value=daily_loss + 0.1, max_value=50.0, allow_nan=False, allow_infinity=False))
    return daily_loss, drawdown


@st.composite
def invalid_risk_hierarchy(draw):
    """Generate invalid risk parameter hierarchy: daily >= drawdown."""
    drawdown = draw(st.floats(min_value=0.1, max_value=20.0, allow_nan=False, allow_infinity=False))
    daily_loss = draw(st.floats(min_value=drawdown, max_value=50.0, allow_nan=False, allow_infinity=False))
    return daily_loss, drawdown


@st.composite
def valid_position_sizing(draw):
    """Generate valid position sizing: risk_per_trade <= position_size."""
    risk_per_trade = draw(st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False))
    position_size = draw(st.floats(min_value=risk_per_trade, max_value=20.0, allow_nan=False, allow_infinity=False))
    return risk_per_trade, position_size


@st.composite
def invalid_position_sizing(draw):
    """Generate invalid position sizing: risk_per_trade > position_size."""
    position_size = draw(st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False))
    risk_per_trade = draw(st.floats(min_value=position_size + 0.1, max_value=20.0, allow_nan=False, allow_infinity=False))
    return risk_per_trade, position_size


@st.composite
def valid_queue_config(draw):
    """Generate valid queue config: backpressure < max_queue_size."""
    max_queue = draw(st.integers(min_value=100, max_value=10000))
    backpressure = draw(st.integers(min_value=10, max_value=max_queue - 1))
    return backpressure, max_queue


@st.composite
def invalid_queue_config(draw):
    """Generate invalid queue config: backpressure >= max_queue_size."""
    max_queue = draw(st.integers(min_value=100, max_value=10000))
    backpressure = draw(st.integers(min_value=max_queue, max_value=max_queue + 1000))
    return backpressure, max_queue


# ============================================================================
# Property 7: Configuration Validation Completeness
# ============================================================================

class TestConfigValidatorProperties:
    """Property-based tests for ConfigValidator.
    
    **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5, 16.6**
    """

    # ------------------------------------------------------------------------
    # Property 7.1: Invalid Risk Parameter Hierarchy is Rejected
    # ------------------------------------------------------------------------

    @given(invalid_risk_hierarchy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_invalid_risk_hierarchy_rejected(self, risk_params):
        """Property: Configs with daily_loss >= drawdown are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2, 16.6**
        """
        daily_loss, drawdown = risk_params
        
        settings = Settings()
        settings.risk.max_daily_loss_pct = daily_loss
        settings.risk.max_drawdown_pct = drawdown
        
        result = validate_settings(settings)
        
        # MUST be invalid when daily_loss >= drawdown
        assert not result.valid, (
            f"Config with daily_loss={daily_loss} >= drawdown={drawdown} "
            f"should be rejected but was accepted"
        )
        assert any("max_daily_loss_pct" in error and "max_drawdown_pct" in error 
                   for error in result.errors), (
            f"Expected error about risk hierarchy but got: {result.errors}"
        )

    @given(valid_risk_hierarchy())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_valid_risk_hierarchy_accepted(self, risk_params):
        """Property: Configs with daily_loss < drawdown pass risk hierarchy check.
        
        **Validates: Requirements 16.1, 16.6**
        """
        daily_loss, drawdown = risk_params
        
        settings = Settings()
        settings.risk.max_daily_loss_pct = daily_loss
        settings.risk.max_drawdown_pct = drawdown
        
        result = validate_settings(settings)
        
        # Should NOT have risk hierarchy errors
        assert not any("max_daily_loss_pct" in error and "max_drawdown_pct" in error 
                       for error in result.errors), (
            f"Config with daily_loss={daily_loss} < drawdown={drawdown} "
            f"should pass risk hierarchy check but got error: {result.errors}"
        )

    # ------------------------------------------------------------------------
    # Property 7.2: Invalid Position Sizing is Rejected
    # ------------------------------------------------------------------------

    @given(invalid_position_sizing())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_invalid_position_sizing_rejected(self, sizing_params):
        """Property: Configs with risk_per_trade > position_size are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2, 16.6**
        """
        risk_per_trade, position_size = sizing_params
        
        settings = Settings()
        settings.risk.max_risk_per_trade_pct = risk_per_trade
        settings.risk.max_position_size_pct = position_size
        
        result = validate_settings(settings)
        
        # MUST be invalid when risk_per_trade > position_size
        assert not result.valid, (
            f"Config with risk_per_trade={risk_per_trade} > position_size={position_size} "
            f"should be rejected but was accepted"
        )
        assert any("max_risk_per_trade_pct" in error and "max_position_size_pct" in error 
                   for error in result.errors), (
            f"Expected error about position sizing but got: {result.errors}"
        )

    @given(valid_position_sizing())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50, deadline=None)
    def test_property_valid_position_sizing_accepted(self, sizing_params):
        """Property: Configs with risk_per_trade <= position_size pass sizing check.
        
        **Validates: Requirements 16.1, 16.6**
        """
        risk_per_trade, position_size = sizing_params
        
        settings = Settings()
        settings.risk.max_risk_per_trade_pct = risk_per_trade
        settings.risk.max_position_size_pct = position_size
        
        result = validate_settings(settings)
        
        # Should NOT have position sizing errors
        assert not any("max_risk_per_trade_pct" in error and "max_position_size_pct" in error 
                       for error in result.errors), (
            f"Config with risk_per_trade={risk_per_trade} <= position_size={position_size} "
            f"should pass sizing check but got error: {result.errors}"
        )

    # ------------------------------------------------------------------------
    # Property 7.3: Mandatory Stop Loss Enforcement
    # ------------------------------------------------------------------------

    def test_property_mandatory_stop_loss_false_rejected(self):
        """Property: Configs with mandatory_stop_loss=False are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2**
        """
        settings = Settings()
        settings.risk.mandatory_stop_loss = False
        
        result = validate_settings(settings)
        
        # MUST be invalid when mandatory_stop_loss is False
        assert not result.valid, (
            "Config with mandatory_stop_loss=False should be rejected but was accepted"
        )
        assert any("mandatory_stop_loss" in error for error in result.errors), (
            f"Expected error about mandatory_stop_loss but got: {result.errors}"
        )

    # ------------------------------------------------------------------------
    # Property 7.4: Invalid Max Open Positions is Rejected
    # ------------------------------------------------------------------------

    @given(non_positive_integer())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_non_positive_max_open_positions_rejected(self, max_positions):
        """Property: Configs with max_open_positions <= 0 are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2**
        """
        settings = Settings()
        settings.risk.max_open_positions = max_positions
        
        result = validate_settings(settings)
        
        # MUST be invalid when max_open_positions <= 0
        assert not result.valid, (
            f"Config with max_open_positions={max_positions} should be rejected but was accepted"
        )
        assert any("max_open_positions" in error for error in result.errors), (
            f"Expected error about max_open_positions but got: {result.errors}"
        )

    @given(positive_integer(min_value=1, max_value=50))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_positive_max_open_positions_accepted(self, max_positions):
        """Property: Configs with max_open_positions > 0 pass this check.
        
        **Validates: Requirements 16.1**
        """
        settings = Settings()
        settings.risk.max_open_positions = max_positions
        
        result = validate_settings(settings)
        
        # Should NOT have max_open_positions errors (may have warnings for high values)
        assert not any("max_open_positions" in error and "at least 1" in error 
                       for error in result.errors), (
            f"Config with max_open_positions={max_positions} > 0 "
            f"should pass check but got error: {result.errors}"
        )

    # ------------------------------------------------------------------------
    # Property 7.5: File Path Validation
    # ------------------------------------------------------------------------

    def test_property_log_directory_created_if_missing(self):
        """Property: Validator creates log directory if it doesn't exist.
        
        **Validates: Requirements 16.1, 16.4**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "new_logs" / "test.log"
            
            settings = Settings()
            settings.logging.log_file = str(log_file)
            
            result = validate_settings(settings)
            
            # Directory should be created
            assert log_file.parent.exists(), (
                f"Log directory {log_file.parent} should be created but doesn't exist"
            )
            assert log_file.parent.is_dir(), (
                f"Log path {log_file.parent} should be a directory"
            )

    # ------------------------------------------------------------------------
    # Property 7.6: Credentials Validation
    # ------------------------------------------------------------------------

    def test_property_binance_missing_credentials_rejected(self):
        """Property: Binance provider without API key/secret is ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2, 16.5**
        """
        settings = Settings()
        settings.data_feed.provider = "binance"
        settings.binance.api_key = None
        settings.binance.api_secret = None
        
        result = validate_settings(settings)
        
        # MUST be invalid when Binance credentials are missing
        assert not result.valid, (
            "Config with Binance provider but no credentials should be rejected"
        )
        assert any("Binance API" in error for error in result.errors), (
            f"Expected error about Binance credentials but got: {result.errors}"
        )

    def test_property_alphavantage_missing_credentials_rejected(self):
        """Property: Alpha Vantage provider without API key is ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2, 16.5**
        """
        settings = Settings()
        settings.data_feed.provider = "alphavantage"
        settings.alphavantage.api_key = ""
        
        result = validate_settings(settings)
        
        # MUST be invalid when Alpha Vantage credentials are missing
        assert not result.valid, (
            "Config with Alpha Vantage provider but no API key should be rejected"
        )
        assert any("Alpha Vantage API key" in error for error in result.errors), (
            f"Expected error about Alpha Vantage credentials but got: {result.errors}"
        )

    # ------------------------------------------------------------------------
    # Property 7.7: Data Feed Configuration Validation
    # ------------------------------------------------------------------------

    @given(non_positive_integer())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_negative_max_retries_rejected(self, max_retries):
        """Property: Configs with negative max_retries are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2**
        """
        assume(max_retries < 0)  # Only test negative values
        
        settings = Settings()
        settings.data_feed.max_retries = max_retries
        
        result = validate_settings(settings)
        
        # MUST be invalid when max_retries is negative
        assert not result.valid, (
            f"Config with max_retries={max_retries} should be rejected but was accepted"
        )
        assert any("max_retries" in error and "negative" in error for error in result.errors), (
            f"Expected error about negative max_retries but got: {result.errors}"
        )

    # ------------------------------------------------------------------------
    # Property 7.8: Worker Pool Configuration Validation
    # ------------------------------------------------------------------------

    @given(non_positive_integer())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_non_positive_pool_size_rejected(self, pool_size):
        """Property: Configs with pool_size <= 0 are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2**
        """
        settings = Settings()
        settings.worker_pool.pool_size = pool_size
        
        result = validate_settings(settings)
        
        # MUST be invalid when pool_size <= 0
        assert not result.valid, (
            f"Config with pool_size={pool_size} should be rejected but was accepted"
        )
        assert any("pool_size" in error for error in result.errors), (
            f"Expected error about pool_size but got: {result.errors}"
        )

    @given(invalid_queue_config())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_invalid_queue_config_rejected(self, queue_params):
        """Property: Configs with backpressure >= max_queue_size are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2, 16.6**
        """
        backpressure, max_queue = queue_params
        
        settings = Settings()
        settings.worker_pool.backpressure_threshold = backpressure
        settings.worker_pool.max_queue_size = max_queue
        
        result = validate_settings(settings)
        
        # MUST be invalid when backpressure >= max_queue_size
        assert not result.valid, (
            f"Config with backpressure={backpressure} >= max_queue={max_queue} "
            f"should be rejected but was accepted"
        )
        assert any("backpressure_threshold" in error and "max_queue_size" in error 
                   for error in result.errors), (
            f"Expected error about queue config but got: {result.errors}"
        )

    @given(valid_queue_config())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_valid_queue_config_accepted(self, queue_params):
        """Property: Configs with backpressure < max_queue_size pass queue check.
        
        **Validates: Requirements 16.1, 16.6**
        """
        backpressure, max_queue = queue_params
        
        settings = Settings()
        settings.worker_pool.backpressure_threshold = backpressure
        settings.worker_pool.max_queue_size = max_queue
        
        result = validate_settings(settings)
        
        # Should NOT have queue config errors
        assert not any("backpressure_threshold" in error and "max_queue_size" in error 
                       for error in result.errors), (
            f"Config with backpressure={backpressure} < max_queue={max_queue} "
            f"should pass queue check but got error: {result.errors}"
        )

    # ------------------------------------------------------------------------
    # Property 7.9: Strategy Configuration Validation
    # ------------------------------------------------------------------------

    @given(non_positive_integer())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_property_non_positive_confirmation_candles_rejected(self, candles):
        """Property: Configs with min_confirmation_candles <= 0 are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2**
        """
        settings = Settings()
        settings.strategy.min_confirmation_candles = candles
        
        result = validate_settings(settings)
        
        # MUST be invalid when min_confirmation_candles <= 0
        assert not result.valid, (
            f"Config with min_confirmation_candles={candles} should be rejected but was accepted"
        )
        assert any("min_confirmation_candles" in error for error in result.errors), (
            f"Expected error about min_confirmation_candles but got: {result.errors}"
        )

    def test_property_empty_ema_periods_rejected(self):
        """Property: Configs with empty ema_periods are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2**
        """
        settings = Settings()
        settings.strategy.ema_periods = []
        
        result = validate_settings(settings)
        
        # MUST be invalid when ema_periods is empty
        assert not result.valid, (
            "Config with empty ema_periods should be rejected but was accepted"
        )
        assert any("ema_periods" in error and "empty" in error for error in result.errors), (
            f"Expected error about empty ema_periods but got: {result.errors}"
        )

    @given(st.integers(min_value=0, max_value=1))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
    def test_property_low_indicator_periods_rejected(self, period):
        """Property: Configs with indicator periods < 2 are ALWAYS rejected.
        
        **Validates: Requirements 16.1, 16.2**
        """
        settings = Settings()
        settings.strategy.rsi_period = period
        
        result = validate_settings(settings)
        
        # MUST be invalid when RSI period < 2
        assert not result.valid, (
            f"Config with rsi_period={period} should be rejected but was accepted"
        )
        assert any("rsi_period" in error for error in result.errors), (
            f"Expected error about rsi_period but got: {result.errors}"
        )

    # ------------------------------------------------------------------------
    # Property 7.10: Comprehensive Valid Configuration Acceptance
    # ------------------------------------------------------------------------

    @given(
        valid_risk_hierarchy(),
        valid_position_sizing(),
        positive_integer(min_value=1, max_value=20),
        valid_queue_config()
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
    def test_property_comprehensive_valid_config_accepted(
        self, risk_params, sizing_params, max_positions, queue_params
    ):
        """Property: Configs satisfying ALL validation rules are accepted.
        
        **Validates: Requirements 16.1, 16.6**
        
        This is the positive case - when all parameters are valid, the config
        should pass validation (though it may have warnings).
        """
        daily_loss, drawdown = risk_params
        risk_per_trade, position_size = sizing_params
        backpressure, max_queue = queue_params
        
        settings = Settings()
        
        # Set all valid parameters
        settings.risk.max_daily_loss_pct = daily_loss
        # Ensure weekly falls between daily and drawdown
        settings.risk.max_weekly_loss_pct = (daily_loss + drawdown) / 2.0
        settings.risk.max_drawdown_pct = drawdown
        settings.risk.max_risk_per_trade_pct = risk_per_trade
        settings.risk.max_position_size_pct = position_size
        settings.risk.max_open_positions = max_positions
        settings.risk.mandatory_stop_loss = True
        
        settings.worker_pool.backpressure_threshold = backpressure
        settings.worker_pool.max_queue_size = max_queue
        settings.worker_pool.pool_size = 10
        
        settings.strategy.min_confirmation_candles = 2
        settings.strategy.ema_periods = [5, 9, 21]
        settings.strategy.rsi_period = 14
        settings.strategy.adx_period = 14
        settings.strategy.atr_period = 14
        
        settings.data_feed.max_retries = 3
        settings.data_feed.symbols = ["AAPL", "MSFT"]
        
        result = validate_settings(settings)
        
        # Should be valid (may have warnings, but no errors)
        assert result.valid, (
            f"Comprehensive valid config should be accepted but got errors: {result.errors}"
        )
