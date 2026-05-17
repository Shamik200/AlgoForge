"""Configuration validation module for AlgoForge.

Validates all configuration parameters on startup to ensure:
- Risk parameters are internally consistent
- File paths exist and are accessible
- Required credentials are present when features are enabled
- All values are within valid ranges
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from algoforge.core.config import Settings


class ValidationResult(BaseModel):
    """Result of configuration validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)


class ConfigValidator:
    """Validates system configuration on startup.

    Performs comprehensive validation of all configuration sections:
    - Risk parameter consistency
    - File path existence and accessibility
    - Required credentials when features are enabled
    - Value range validation
    """

    def __init__(self, settings: Settings):
        """Initialize validator with settings instance.

        Args:
            settings: The Settings instance to validate
        """
        self.settings = settings

    def validate_config(self) -> ValidationResult:
        """Validate entire configuration.

        Returns:
            ValidationResult with all errors and warnings
        """
        result = ValidationResult(valid=True)

        # Validate each section
        self._validate_risk_params(result)
        self._validate_paths(result)
        self._validate_credentials(result)
        self._validate_market_config(result)
        self._validate_data_feed_config(result)
        self._validate_worker_pool_config(result)
        self._validate_event_bus_config(result)
        self._validate_strategy_config(result)

        return result

    def _validate_risk_params(self, result: ValidationResult) -> None:
        """Validate risk parameter consistency.

        Ensures:
        - daily_loss_limit < weekly_loss_limit < drawdown_limit
        - max_risk_per_trade < max_position_size
        - All percentages are in valid ranges
        """
        risk = self.settings.risk

        # Check risk parameter hierarchy: daily < weekly < drawdown
        if risk.max_daily_loss_pct >= risk.max_weekly_loss_pct:
            result.add_error(
                f"max_daily_loss_pct ({risk.max_daily_loss_pct}%) must be less than "
                f"max_weekly_loss_pct ({risk.max_weekly_loss_pct}%)"
            )

        if risk.max_weekly_loss_pct >= risk.max_drawdown_pct:
            result.add_error(
                f"max_weekly_loss_pct ({risk.max_weekly_loss_pct}%) must be less than "
                f"max_drawdown_pct ({risk.max_drawdown_pct}%)"
            )

        if risk.max_daily_loss_pct >= risk.max_drawdown_pct:
            result.add_error(
                f"max_daily_loss_pct ({risk.max_daily_loss_pct}%) must be less than "
                f"max_drawdown_pct ({risk.max_drawdown_pct}%)"
            )

        # Check risk per trade vs position size
        if risk.max_risk_per_trade_pct > risk.max_position_size_pct:
            result.add_error(
                f"max_risk_per_trade_pct ({risk.max_risk_per_trade_pct}%) should not exceed "
                f"max_position_size_pct ({risk.max_position_size_pct}%)"
            )

        # Validate mandatory stop loss
        if not risk.mandatory_stop_loss:
            result.add_error(
                "mandatory_stop_loss must be True - trading without stop losses is not allowed"
            )

        # Validate risk/reward ratio
        if risk.min_risk_reward_ratio < 1.0:
            result.add_warning(
                f"min_risk_reward_ratio ({risk.min_risk_reward_ratio}) is less than 1.0 - "
                "this means accepting trades with negative expected value"
            )

        # Validate max open positions
        if risk.max_open_positions < 1:
            result.add_error("max_open_positions must be at least 1")

        if risk.max_open_positions > 50:
            result.add_warning(
                f"max_open_positions ({risk.max_open_positions}) is very high - "
                "this may lead to over-diversification and increased management complexity"
            )

    def _validate_paths(self, result: ValidationResult) -> None:
        """Validate all file paths exist and are accessible.

        Checks:
        - Log file directory exists and is writable
        - Config directory exists
        - Data directory exists
        """
        # Validate log file path
        if self.settings.logging.log_file:
            log_path = Path(self.settings.logging.log_file)
            log_dir = log_path.parent

            # Create log directory if it doesn't exist
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                result.add_error(f"Cannot create log directory {log_dir}: {e}")

            # Check if directory is writable
            if log_dir.exists() and not log_dir.is_dir():
                result.add_error(f"Log directory path {log_dir} exists but is not a directory")
            elif log_dir.exists():
                # Try to write a test file
                test_file = log_dir / ".write_test"
                try:
                    test_file.touch()
                    test_file.unlink()
                except Exception as e:
                    result.add_error(f"Log directory {log_dir} is not writable: {e}")

        # Validate config directory
        config_dir = Path("config")
        if not config_dir.exists():
            result.add_error(f"Config directory {config_dir} does not exist")
        elif not config_dir.is_dir():
            result.add_error(f"Config path {config_dir} exists but is not a directory")

        # Validate data directory
        data_dir = Path("data")
        if not data_dir.exists():
            result.add_warning(
                f"Data directory {data_dir} does not exist - it will be created on first use"
            )
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                result.add_error(f"Cannot create data directory {data_dir}: {e}")

    def _validate_credentials(self, result: ValidationResult) -> None:
        """Validate required credentials are present when features are enabled.

        Checks:
        - Binance API keys when using Binance provider
        - Alpha Vantage API key when using Alpha Vantage provider
        - TimescaleDB credentials when using TimescaleDB
        """
        # Check Binance credentials
        if self.settings.data_feed.provider.lower() == "binance":
            if not self.settings.binance.api_key:
                result.add_error(
                    "Binance API key is required when using Binance data provider. "
                    "Set ALGOFORGE_BINANCE__API_KEY or configure in settings.yaml"
                )
            if not self.settings.binance.api_secret:
                result.add_error(
                    "Binance API secret is required when using Binance data provider. "
                    "Set ALGOFORGE_BINANCE__API_SECRET or configure in settings.yaml"
                )

        # Check Alpha Vantage credentials
        if self.settings.data_feed.provider.lower() == "alphavantage":
            if not self.settings.alphavantage.api_key:
                result.add_error(
                    "Alpha Vantage API key is required when using Alpha Vantage data provider. "
                    "Set ALGOFORGE_ALPHAVANTAGE__API_KEY or configure in settings.yaml"
                )

        # Check TimescaleDB credentials
        if self.settings.timescaledb.password == "":
            result.add_warning(
                "TimescaleDB password is empty - this may be intentional for local development "
                "but is not recommended for production"
            )

        # Check Redis password
        if self.settings.redis.password is None:
            result.add_warning(
                "Redis password is not set - this may be intentional for local development "
                "but is not recommended for production"
            )

    def _validate_market_config(self, result: ValidationResult) -> None:
        """Validate market configuration parameters."""
        market = self.settings.market

        # Validate paper trading capital
        if market.paper_trading_capital <= 0:
            result.add_error(
                f"paper_trading_capital must be positive, got {market.paper_trading_capital}"
            )

        if market.paper_trading_capital < 1000:
            result.add_warning(
                f"paper_trading_capital ({market.paper_trading_capital}) is very low - "
                "this may limit position sizing and testing effectiveness"
            )

        # Validate currency
        valid_currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY"]
        if market.currency not in valid_currencies:
            result.add_warning(
                f"Currency {market.currency} is not in common list: {valid_currencies}"
            )

    def _validate_data_feed_config(self, result: ValidationResult) -> None:
        """Validate data feed configuration parameters."""
        feed = self.settings.data_feed

        # Validate symbols list
        if not feed.symbols:
            result.add_error("data_feed.symbols cannot be empty - at least one symbol is required")

        if len(feed.symbols) > 100:
            result.add_warning(
                f"data_feed.symbols has {len(feed.symbols)} symbols - "
                "this may impact performance and rate limits"
            )

        # Validate poll interval
        if feed.poll_interval_seconds < 1:
            result.add_error(
                f"data_feed.poll_interval_seconds must be at least 1, got {feed.poll_interval_seconds}"
            )

        if feed.poll_interval_seconds < 10:
            result.add_warning(
                f"data_feed.poll_interval_seconds ({feed.poll_interval_seconds}) is very low - "
                "this may hit rate limits"
            )

        # Validate max retries
        if feed.max_retries < 0:
            result.add_error(f"data_feed.max_retries cannot be negative, got {feed.max_retries}")

        if feed.max_retries > 10:
            result.add_warning(
                f"data_feed.max_retries ({feed.max_retries}) is very high - "
                "this may cause long delays on persistent failures"
            )

        # Validate retry delay
        if feed.retry_delay_seconds <= 0:
            result.add_error(
                f"data_feed.retry_delay_seconds must be positive, got {feed.retry_delay_seconds}"
            )

    def _validate_worker_pool_config(self, result: ValidationResult) -> None:
        """Validate worker pool configuration parameters."""
        pool = self.settings.worker_pool

        # Validate pool size
        if pool.pool_size < 1:
            result.add_error(f"worker_pool.pool_size must be at least 1, got {pool.pool_size}")

        if pool.pool_size > 100:
            result.add_warning(
                f"worker_pool.pool_size ({pool.pool_size}) is very high - "
                "this may cause excessive resource usage"
            )

        # Validate queue sizes
        if pool.max_queue_size < 100:
            result.add_warning(
                f"worker_pool.max_queue_size ({pool.max_queue_size}) is very low - "
                "this may cause backpressure issues"
            )

        if pool.backpressure_threshold >= pool.max_queue_size:
            result.add_error(
                f"worker_pool.backpressure_threshold ({pool.backpressure_threshold}) "
                f"must be less than max_queue_size ({pool.max_queue_size})"
            )

    def _validate_event_bus_config(self, result: ValidationResult) -> None:
        """Validate event bus configuration parameters."""
        bus = self.settings.event_bus

        # Validate queue size
        if bus.max_queue_size < 100:
            result.add_warning(
                f"event_bus.max_queue_size ({bus.max_queue_size}) is very low - "
                "this may cause event loss under high load"
            )

        # Validate stream max length
        if bus.enable_streams and bus.stream_max_len < 1000:
            result.add_warning(
                f"event_bus.stream_max_len ({bus.stream_max_len}) is very low - "
                "this may limit event history for debugging"
            )

    def _validate_strategy_config(self, result: ValidationResult) -> None:
        """Validate strategy configuration parameters."""
        strategy = self.settings.strategy

        # Validate confirmation candles
        if strategy.min_confirmation_candles < 1:
            result.add_error(
                f"strategy.min_confirmation_candles must be at least 1, "
                f"got {strategy.min_confirmation_candles}"
            )

        if strategy.min_confirmation_candles > 5:
            result.add_warning(
                f"strategy.min_confirmation_candles ({strategy.min_confirmation_candles}) is high - "
                "this may cause missed opportunities"
            )

        # Validate EMA periods
        if not strategy.ema_periods:
            result.add_error("strategy.ema_periods cannot be empty")

        if len(strategy.ema_periods) < 2:
            result.add_warning(
                "strategy.ema_periods should have at least 2 periods for crossover strategies"
            )

        # Check EMA periods are sorted
        if strategy.ema_periods != sorted(strategy.ema_periods):
            result.add_warning(
                f"strategy.ema_periods {strategy.ema_periods} should be in ascending order"
            )

        # Validate indicator periods
        if strategy.rsi_period < 2:
            result.add_error(f"strategy.rsi_period must be at least 2, got {strategy.rsi_period}")

        if strategy.adx_period < 2:
            result.add_error(f"strategy.adx_period must be at least 2, got {strategy.adx_period}")

        if strategy.atr_period < 2:
            result.add_error(f"strategy.atr_period must be at least 2, got {strategy.atr_period}")

        # Validate primary strategy
        valid_strategies = [
            "trendline_pullback",
            "ema_crossover",
            "breakout",
            "mean_reversion",
            "momentum",
        ]
        if strategy.primary_strategy not in valid_strategies:
            result.add_warning(
                f"strategy.primary_strategy '{strategy.primary_strategy}' is not in "
                f"known strategies: {valid_strategies}"
            )


def validate_settings(settings: Settings) -> ValidationResult:
    """Convenience function to validate settings.

    Args:
        settings: The Settings instance to validate

    Returns:
        ValidationResult with all errors and warnings

    Example:
        >>> from algoforge.core.config import get_settings
        >>> from algoforge.core.validator import validate_settings
        >>> settings = get_settings()
        >>> result = validate_settings(settings)
        >>> if not result.valid:
        ...     for error in result.errors:
        ...         print(f"ERROR: {error}")
        ...     raise SystemExit(1)
    """
    validator = ConfigValidator(settings)
    return validator.validate_config()
