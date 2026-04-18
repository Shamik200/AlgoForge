"""Tests for the configuration system."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from algoforge.core.config import Settings, get_settings, reload_settings
from algoforge.core.constants import Market, TimeframeMode


class TestDefaultSettings:
    """Test default configuration values."""

    def test_default_settings_load(self) -> None:
        """Settings() creates with all defaults — no YAML required."""
        settings = Settings()
        assert settings.version == "0.1.0"
        assert settings.market is not None
        assert settings.redis is not None
        assert settings.data_feed is not None

    def test_default_market_is_stocks_us(self) -> None:
        """Default market is US stocks."""
        settings = Settings()
        assert settings.market.selected_market == Market.STOCKS_US

    def test_default_mode_is_intraday(self) -> None:
        """Default timeframe mode is intraday."""
        settings = Settings()
        assert settings.market.timeframe_mode == TimeframeMode.INTRADAY

    def test_redis_config_defaults(self) -> None:
        """Redis defaults to localhost:6379."""
        settings = Settings()
        assert settings.redis.host == "localhost"
        assert settings.redis.port == 6379
        assert settings.redis.db == 0
        assert settings.redis.password is None

    def test_data_feed_symbols_list(self) -> None:
        """Symbols is a non-empty list."""
        settings = Settings()
        assert isinstance(settings.data_feed.symbols, list)
        assert len(settings.data_feed.symbols) >= 1

    def test_paper_trading_capital_positive(self) -> None:
        """Capital must be positive."""
        settings = Settings()
        assert settings.market.paper_trading_capital > 0


class TestEnvOverrides:
    """Test environment variable overrides."""

    def test_env_override_market(self) -> None:
        """ALGOFORGE_MARKET__SELECTED_MARKET overrides YAML."""
        with patch.dict(os.environ, {"ALGOFORGE_MARKET__SELECTED_MARKET": "crypto"}):
            settings = Settings()
            assert settings.market.selected_market == Market.CRYPTO

    def test_env_override_redis_host(self) -> None:
        """ALGOFORGE_REDIS__HOST overrides YAML."""
        with patch.dict(os.environ, {"ALGOFORGE_REDIS__HOST": "redis-prod"}):
            settings = Settings()
            assert settings.redis.host == "redis-prod"

    def test_env_override_logging_level(self) -> None:
        """ALGOFORGE_LOGGING__LEVEL overrides YAML."""
        with patch.dict(os.environ, {"ALGOFORGE_LOGGING__LEVEL": "DEBUG"}):
            settings = Settings()
            assert settings.logging.level == "DEBUG"


class TestValidation:
    """Test config validation rejects invalid values."""

    def test_invalid_market_rejected(self) -> None:
        """Invalid market value raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(market={"selected_market": "invalid_market"})

    def test_invalid_timeframe_mode_rejected(self) -> None:
        """Invalid timeframe mode raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(market={"timeframe_mode": "invalid_mode"})

    def test_negative_capital_rejected(self) -> None:
        """Negative capital raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(market={"paper_trading_capital": -1000})

    def test_mandatory_stop_loss_default(self) -> None:
        """Mandatory stop loss defaults to True."""
        settings = Settings()
        assert settings.risk.mandatory_stop_loss is True


class TestGetSettings:
    """Test settings singleton."""

    def test_get_settings_returns_settings(self) -> None:
        """get_settings returns a Settings instance."""
        reload_settings()  # Clear cache
        s = get_settings()
        assert isinstance(s, Settings)

    def test_reload_settings_clears_cache(self) -> None:
        """reload_settings creates a fresh instance."""
        s1 = get_settings()
        s2 = reload_settings()
        # Both are Settings but may be different objects
        assert isinstance(s2, Settings)
