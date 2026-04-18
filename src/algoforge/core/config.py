"""AlgoForge configuration system.

Single YAML file (config/settings.yaml) validated by Pydantic at startup.
Priority: env vars (ALGOFORGE_ prefix) > .env > YAML > defaults.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from algoforge.core.constants import (
    DEFAULT_CAPITAL,
    Market,
    Timeframe,
    TimeframeMode,
)

# ---------------------------------------------------------------------------
# Nested config sections
# ---------------------------------------------------------------------------


class RedisConfig(BaseModel):
    """Redis connection settings."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 20
    socket_timeout: float = 5.0


class DataFeedConfig(BaseModel):
    """Data feed settings — which provider, symbols, and timeframes to ingest."""

    provider: str = "yfinance"
    symbols: list[str] = Field(
        default=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
        min_length=1,
    )
    base_timeframe: Timeframe = Timeframe.M1
    history_period: str = "1mo"
    poll_interval_seconds: int = 60
    max_retries: int = 3
    retry_delay_seconds: float = 2.0


class MarketConfig(BaseModel):
    """Market selection and operational mode."""

    selected_market: Market = Market.STOCKS_US
    timeframe_mode: TimeframeMode = TimeframeMode.INTRADAY
    paper_trading_capital: float = Field(default=100_000.0, gt=0)
    currency: str = "USD"

    @field_validator("paper_trading_capital", mode="before")
    @classmethod
    def set_capital_from_market(cls, v: float, info: Any) -> float:
        """Auto-set capital based on market if not explicitly configured."""
        if v == 100_000.0 and info.data.get("selected_market"):
            market = info.data["selected_market"]
            if isinstance(market, str):
                market = Market(market)
            capital, currency = DEFAULT_CAPITAL.get(market, (100_000.0, "USD"))
            return capital
        return v


class LoggingConfig(BaseModel):
    """Structured logging settings."""

    level: str = "INFO"
    format: str = "json"  # "json" or "console"
    log_file: str | None = "logs/algoforge.log"
    log_to_stdout: bool = True


class RiskConfig(BaseModel):
    """Risk management parameters — stub for Phase 6."""

    max_risk_per_trade_pct: float = Field(default=2.0, gt=0, le=100)
    max_position_size_pct: float = Field(default=10.0, gt=0, le=100)
    min_risk_reward_ratio: float = Field(default=2.0, gt=0)
    max_open_positions: int = Field(default=5, gt=0)
    max_daily_loss_pct: float = Field(default=5.0, gt=0, le=100)
    max_drawdown_pct: float = Field(default=20.0, gt=0, le=100)
    mandatory_stop_loss: bool = True  # NEVER set to False


class StrategyConfig(BaseModel):
    """Strategy parameters — stub for Phase 5+."""

    primary_strategy: str = "trendline_pullback"
    min_confirmation_candles: int = Field(default=1, ge=1, le=5)
    ema_periods: list[int] = Field(default=[5, 9, 21, 50, 100, 200])
    rsi_period: int = Field(default=14, gt=0)
    adx_period: int = Field(default=14, gt=0)
    atr_period: int = Field(default=14, gt=0)


# ---------------------------------------------------------------------------
# Root Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Root configuration — loaded from config/settings.yaml with env var overrides.

    Usage:
        from algoforge.core.config import get_settings
        settings = get_settings()
        print(settings.market.selected_market)
    """

    version: str = "0.1.0"
    market: MarketConfig = MarketConfig()
    redis: RedisConfig = RedisConfig()
    data_feed: DataFeedConfig = DataFeedConfig()
    logging: LoggingConfig = LoggingConfig()
    risk: RiskConfig = RiskConfig()
    strategy: StrategyConfig = StrategyConfig()

    # Pydantic Settings configuration
    model_config = SettingsConfigDict(
        yaml_file="config/settings.yaml",
        env_prefix="ALGOFORGE_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Path to the YAML file (for reference)
    CONFIG_PATH: ClassVar[Path] = Path("config/settings.yaml")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings. Call once at startup.

    Returns validated Settings from YAML + env vars.
    Raises ValidationError if config is invalid.
    """
    return Settings()


def reload_settings() -> Settings:
    """Force reload settings (clears cache). Use after config file changes."""
    get_settings.cache_clear()
    return get_settings()
