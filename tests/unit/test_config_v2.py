"""Tests for Phase 1 config upgrades — TimescaleDB, Binance, AlphaVantage configs."""

from algoforge.core.config import (
    AlphaVantageConfig,
    BinanceConfig,
    Settings,
    TimescaleDBConfig,
)


class TestTimescaleDBConfig:
    """TimescaleDB configuration defaults."""

    def test_defaults(self) -> None:
        cfg = TimescaleDBConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 5432
        assert cfg.database == "algoforge"
        assert cfg.user == "algoforge"
        assert cfg.password == ""
        assert cfg.min_connections == 5
        assert cfg.max_connections == 20
        assert cfg.ssl is False

    def test_custom_values(self) -> None:
        cfg = TimescaleDBConfig(host="db.example.com", port=5433, database="prod", ssl=True)
        assert cfg.host == "db.example.com"
        assert cfg.port == 5433
        assert cfg.database == "prod"
        assert cfg.ssl is True


class TestBinanceConfig:
    """Binance configuration defaults."""

    def test_defaults(self) -> None:
        cfg = BinanceConfig()
        assert cfg.base_url == "https://api.binance.com"
        assert cfg.ws_url == "wss://stream.binance.com:9443/ws"
        assert cfg.api_key is None
        assert cfg.api_secret is None
        assert cfg.rate_limit_per_minute == 1200

    def test_with_credentials(self) -> None:
        cfg = BinanceConfig(api_key="key123", api_secret="secret456")
        assert cfg.api_key == "key123"
        assert cfg.api_secret == "secret456"


class TestAlphaVantageConfig:
    """Alpha Vantage configuration defaults."""

    def test_defaults(self) -> None:
        cfg = AlphaVantageConfig()
        assert cfg.api_key == ""
        assert cfg.base_url == "https://www.alphavantage.co/query"
        assert cfg.rate_limit_per_minute == 25

    def test_with_api_key(self) -> None:
        cfg = AlphaVantageConfig(api_key="DEMO_KEY")
        assert cfg.api_key == "DEMO_KEY"


class TestSettingsV2:
    """Settings contains all new config sections."""

    def test_settings_has_timescaledb(self) -> None:
        settings = Settings()
        assert hasattr(settings, "timescaledb")
        assert isinstance(settings.timescaledb, TimescaleDBConfig)
        assert settings.timescaledb.host == "localhost"

    def test_settings_has_binance(self) -> None:
        settings = Settings()
        assert hasattr(settings, "binance")
        assert isinstance(settings.binance, BinanceConfig)

    def test_settings_has_alphavantage(self) -> None:
        settings = Settings()
        assert hasattr(settings, "alphavantage")
        assert isinstance(settings.alphavantage, AlphaVantageConfig)

    def test_version_is_0_2_0(self) -> None:
        settings = Settings()
        assert settings.version == "0.2.0"

    def test_data_feed_has_provider(self) -> None:
        settings = Settings()
        assert settings.data_feed.provider == "yfinance"
