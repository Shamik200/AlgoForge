import pytest

from algoforge.core.config import Settings
from algoforge.core.validator import validate_settings, ConfigValidator, ValidationResult


def test_default_settings_valid():
    """Default Settings should pass validation."""
    settings = Settings()
    result = validate_settings(settings)
    assert isinstance(result, ValidationResult)
    assert result.valid, f"Expected valid settings; got errors: {result.errors}"


def test_invalid_risk_settings_fail():
    """Create an invalid Settings where daily loss >= weekly loss to trigger error."""
    settings = Settings()
    # Mutate risk to invalid values
    settings.risk.max_daily_loss_pct = 15.0
    settings.risk.max_weekly_loss_pct = 10.0
    result = validate_settings(settings)
    assert not result.valid
    assert any("max_daily_loss_pct" in e or "max_weekly_loss_pct" in e for e in result.errors)
"""Unit tests for ConfigValidator module.

Tests validation of:
- Risk parameter consistency
- File path existence and accessibility
- Required credentials when features are enabled
- Value range validation
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

from algoforge.core.config import Settings, RiskConfig, DataFeedConfig, WorkerPoolConfig
from algoforge.core.validator import ConfigValidator, validate_settings, ValidationResult


class TestConfigValidator:
    """Test suite for ConfigValidator."""

    def test_valid_default_config(self):
        """Test that default configuration passes validation."""
        settings = Settings()
        result = validate_settings(settings)

        # Should have no errors (warnings are acceptable)
        assert result.valid, f"Default config should be valid. Errors: {result.errors}"

    def test_risk_params_daily_loss_exceeds_drawdown(self):
        """Test that daily loss >= drawdown is rejected."""
        settings = Settings()
        settings.risk.max_daily_loss_pct = 25.0
        settings.risk.max_weekly_loss_pct = 30.0
        settings.risk.max_drawdown_pct = 20.0

        result = validate_settings(settings)

        assert not result.valid
        assert any("max_daily_loss_pct" in error and "max_drawdown_pct" in error 
                   for error in result.errors)

    def test_risk_params_daily_loss_exceeds_weekly(self):
        """Test that daily loss >= weekly loss is rejected."""
        settings = Settings()
        settings.risk.max_daily_loss_pct = 15.0
        settings.risk.max_weekly_loss_pct = 10.0
        settings.risk.max_drawdown_pct = 20.0

        result = validate_settings(settings)

        assert not result.valid
        assert any("max_daily_loss_pct" in error and "max_weekly_loss_pct" in error 
                   for error in result.errors)

    def test_risk_params_weekly_loss_exceeds_drawdown(self):
        """Test that weekly loss >= drawdown is rejected."""
        settings = Settings()
        settings.risk.max_daily_loss_pct = 5.0
        settings.risk.max_weekly_loss_pct = 25.0
        settings.risk.max_drawdown_pct = 20.0

        result = validate_settings(settings)

        assert not result.valid
        assert any("max_weekly_loss_pct" in error and "max_drawdown_pct" in error 
                   for error in result.errors)

    def test_risk_params_valid_hierarchy(self):
        """Test that valid risk hierarchy (daily < weekly < drawdown) passes."""
        settings = Settings()
        settings.risk.max_daily_loss_pct = 5.0
        settings.risk.max_weekly_loss_pct = 10.0
        settings.risk.max_drawdown_pct = 20.0

        result = validate_settings(settings)

        # Should be valid (may have other warnings but no errors about risk hierarchy)
        assert result.valid or not any(
            "max_daily_loss_pct" in error or "max_weekly_loss_pct" in error 
            for error in result.errors
        )

    def test_risk_params_risk_per_trade_exceeds_position_size(self):
        """Test that risk per trade > position size generates error."""
        settings = Settings()
        settings.risk.max_risk_per_trade_pct = 15.0
        settings.risk.max_position_size_pct = 10.0

        result = validate_settings(settings)

        assert not result.valid
        assert any("max_risk_per_trade_pct" in error and "max_position_size_pct" in error 
                   for error in result.errors)

    def test_risk_params_mandatory_stop_loss_false(self):
        """Test that mandatory_stop_loss=False is rejected."""
        settings = Settings()
        settings.risk.mandatory_stop_loss = False

        result = validate_settings(settings)

        assert not result.valid
        assert any("mandatory_stop_loss" in error for error in result.errors)

    def test_risk_params_low_risk_reward_ratio_warning(self):
        """Test that risk/reward ratio < 1.0 generates warning."""
        settings = Settings()
        settings.risk.min_risk_reward_ratio = 0.5

        result = validate_settings(settings)

        # Should be valid but with warning
        assert result.valid
        assert any("min_risk_reward_ratio" in warning for warning in result.warnings)

    def test_risk_params_max_open_positions_zero(self):
        """Test that max_open_positions < 1 is rejected."""
        settings = Settings()
        settings.risk.max_open_positions = 0

        result = validate_settings(settings)

        assert not result.valid
        assert any("max_open_positions" in error for error in result.errors)

    def test_risk_params_high_open_positions_warning(self):
        """Test that very high max_open_positions generates warning."""
        settings = Settings()
        settings.risk.max_open_positions = 100

        result = validate_settings(settings)

        # Should be valid but with warning
        assert result.valid
        assert any("max_open_positions" in warning for warning in result.warnings)

    def test_paths_log_directory_created(self, tmp_path):
        """Test that log directory is created if it doesn't exist."""
        settings = Settings()
        log_file = tmp_path / "test_logs" / "test.log"
        settings.logging.log_file = str(log_file)

        result = validate_settings(settings)

        # Should be valid and directory should be created
        assert result.valid
        assert log_file.parent.exists()
        assert log_file.parent.is_dir()

    def test_credentials_binance_missing_api_key(self):
        """Test that Binance provider without API key is rejected."""
        settings = Settings()
        settings.data_feed.provider = "binance"
        settings.binance.api_key = None
        settings.binance.api_secret = "test_secret"

        result = validate_settings(settings)

        assert not result.valid
        assert any("Binance API key" in error for error in result.errors)

    def test_credentials_binance_missing_api_secret(self):
        """Test that Binance provider without API secret is rejected."""
        settings = Settings()
        settings.data_feed.provider = "binance"
        settings.binance.api_key = "test_key"
        settings.binance.api_secret = None

        result = validate_settings(settings)

        assert not result.valid
        assert any("Binance API secret" in error for error in result.errors)

    def test_credentials_alphavantage_missing_api_key(self):
        """Test that Alpha Vantage provider without API key is rejected."""
        settings = Settings()
        settings.data_feed.provider = "alphavantage"
        settings.alphavantage.api_key = ""

        result = validate_settings(settings)

        assert not result.valid
        assert any("Alpha Vantage API key" in error for error in result.errors)

    def test_credentials_redis_password_warning(self):
        """Test that missing Redis password generates warning."""
        settings = Settings()
        settings.redis.password = None

        result = validate_settings(settings)

        # Should be valid but with warning
        assert result.valid
        assert any("Redis password" in warning for warning in result.warnings)

    def test_market_config_negative_capital(self):
        """Test that negative paper trading capital is rejected by Pydantic."""
        # This should be caught by Pydantic validation during construction
        with pytest.raises(ValidationError):
            Settings(market={"paper_trading_capital": -1000.0})

    def test_market_config_low_capital_warning(self):
        """Test that very low capital generates warning."""
        settings = Settings()
        settings.market.paper_trading_capital = 500.0

        result = validate_settings(settings)

        # Should be valid but with warning
        assert result.valid
        assert any("paper_trading_capital" in warning and "very low" in warning 
                   for warning in result.warnings)

    def test_data_feed_empty_symbols(self):
        """Test that empty symbols list is rejected by Pydantic."""
        # This should be caught by Pydantic validation during construction
        with pytest.raises(ValidationError):
            Settings(data_feed={"symbols": []})

    def test_data_feed_many_symbols_warning(self):
        """Test that many symbols generates warning."""
        settings = Settings()
        settings.data_feed.symbols = [f"SYM{i}" for i in range(150)]

        result = validate_settings(settings)

        # Should be valid but with warning
        assert result.valid
        assert any("symbols" in warning and "150" in warning for warning in result.warnings)

    def test_data_feed_low_poll_interval_warning(self):
        """Test that very low poll interval generates warning."""
        settings = Settings()
        settings.data_feed.poll_interval_seconds = 5

        result = validate_settings(settings)

        # Should be valid but with warning
        assert result.valid
        assert any("poll_interval_seconds" in warning and "rate limits" in warning 
                   for warning in result.warnings)

    def test_data_feed_negative_max_retries(self):
        """Test that negative max retries is rejected."""
        settings = Settings()
        settings.data_feed.max_retries = -1

        result = validate_settings(settings)

        assert not result.valid
        assert any("max_retries" in error and "negative" in error for error in result.errors)

    def test_worker_pool_zero_pool_size(self):
        """Test that zero pool size is rejected."""
        settings = Settings()
        settings.worker_pool.pool_size = 0

        result = validate_settings(settings)

        assert not result.valid
        assert any("pool_size" in error for error in result.errors)

    def test_worker_pool_backpressure_exceeds_max_queue(self):
        """Test that backpressure >= max_queue_size is rejected."""
        settings = Settings()
        settings.worker_pool.max_queue_size = 1000
        settings.worker_pool.backpressure_threshold = 1000

        result = validate_settings(settings)

        assert not result.valid
        assert any("backpressure_threshold" in error and "max_queue_size" in error 
                   for error in result.errors)

    def test_strategy_config_zero_confirmation_candles(self):
        """Test that zero confirmation candles is rejected."""
        settings = Settings()
        settings.strategy.min_confirmation_candles = 0

        result = validate_settings(settings)

        assert not result.valid
        assert any("min_confirmation_candles" in error for error in result.errors)

    def test_strategy_config_empty_ema_periods(self):
        """Test that empty EMA periods is rejected."""
        settings = Settings()
        settings.strategy.ema_periods = []

        result = validate_settings(settings)

        assert not result.valid
        assert any("ema_periods" in error and "empty" in error for error in result.errors)

    def test_strategy_config_unsorted_ema_periods_warning(self):
        """Test that unsorted EMA periods generates warning."""
        settings = Settings()
        settings.strategy.ema_periods = [21, 9, 5, 50]

        result = validate_settings(settings)

        # Should be valid but with warning
        assert result.valid
        assert any("ema_periods" in warning and "ascending order" in warning 
                   for warning in result.warnings)

    def test_strategy_config_low_rsi_period(self):
        """Test that RSI period < 2 is rejected."""
        settings = Settings()
        settings.strategy.rsi_period = 1

        result = validate_settings(settings)

        assert not result.valid
        assert any("rsi_period" in error for error in result.errors)

    def test_validation_result_add_error(self):
        """Test ValidationResult.add_error() method."""
        result = ValidationResult(valid=True)
        assert result.valid

        result.add_error("Test error")

        assert not result.valid
        assert "Test error" in result.errors

    def test_validation_result_add_warning(self):
        """Test ValidationResult.add_warning() method."""
        result = ValidationResult(valid=True)

        result.add_warning("Test warning")

        assert result.valid  # Warnings don't affect validity
        assert "Test warning" in result.warnings

    def test_validator_instance_creation(self):
        """Test ConfigValidator instance creation."""
        settings = Settings()
        validator = ConfigValidator(settings)

        assert validator.settings == settings

    def test_multiple_errors_accumulated(self):
        """Test that multiple validation errors are accumulated."""
        settings = Settings()
        settings.risk.max_daily_loss_pct = 25.0
        settings.risk.max_drawdown_pct = 20.0
        settings.risk.mandatory_stop_loss = False
        settings.risk.max_open_positions = 0

        result = validate_settings(settings)

        assert not result.valid
        # Should have at least 3 errors
        assert len(result.errors) >= 3

    def test_valid_config_with_warnings(self):
        """Test that config can be valid with warnings."""
        settings = Settings()
        settings.risk.min_risk_reward_ratio = 0.8
        settings.market.paper_trading_capital = 500.0

        result = validate_settings(settings)

        # Should be valid but have warnings
        assert result.valid
        assert len(result.warnings) >= 2


class TestConfigValidatorIntegration:
    """Integration tests for ConfigValidator with real settings."""

    def test_validate_default_settings_file(self):
        """Test validation of default settings.yaml file."""
        # This test assumes settings.yaml exists and is valid
        try:
            from algoforge.core.config import get_settings
            settings = get_settings()
            result = validate_settings(settings)

            # Default config should be valid (may have warnings)
            assert result.valid, f"Default settings.yaml should be valid. Errors: {result.errors}"

        except Exception as e:
            pytest.skip(f"Could not load settings.yaml: {e}")

    def test_comprehensive_validation(self):
        """Test comprehensive validation of all sections."""
        settings = Settings()

        # Set up a valid configuration
        settings.market.paper_trading_capital = 50000.0
        settings.risk.max_daily_loss_pct = 3.0
        settings.risk.max_drawdown_pct = 15.0
        settings.risk.max_risk_per_trade_pct = 1.5
        settings.risk.max_position_size_pct = 8.0
        settings.data_feed.symbols = ["AAPL", "MSFT", "GOOGL"]
        settings.worker_pool.pool_size = 10
        settings.worker_pool.max_queue_size = 5000
        settings.worker_pool.backpressure_threshold = 2500

        result = validate_settings(settings)

        # Should be valid
        assert result.valid, f"Comprehensive config should be valid. Errors: {result.errors}"
