"""Configuration and data models for the Paper Trading Engine."""

from dataclasses import dataclass, field
from enum import Enum


class AssetClass(str, Enum):
    """Supported asset classes."""
    US_STOCKS = "us_stocks"
    INDIAN_STOCKS = "indian_stocks"
    CRYPTO = "crypto"
    FOREX = "forex"


# Commission schedules per asset class
COMMISSION_SCHEDULES: dict[AssetClass, dict] = {
    AssetClass.US_STOCKS: {
        "model": "per_share",
        "rate": 0.005,           # $0.005 per share
        "minimum": 1.00,         # $1.00 minimum per order
    },
    AssetClass.INDIAN_STOCKS: {
        "model": "percentage",
        "brokerage_pct": 0.0003,  # 0.03% brokerage
        "stt_pct": 0.001,         # 0.1% STT on sell side
        "gst_pct": 0.18,          # 18% GST on brokerage
    },
    AssetClass.CRYPTO: {
        "model": "percentage",
        "maker_pct": 0.001,       # 0.1% maker fee
        "taker_pct": 0.001,       # 0.1% taker fee
    },
    AssetClass.FOREX: {
        "model": "spread",
        "spread_pips": 1.5,       # 1.5 pip spread
    },
}


@dataclass
class PaperTradingConfig:
    """Configuration for the paper trading simulator."""

    asset_class: AssetClass = AssetClass.US_STOCKS
    starting_capital: float = 100_000.0

    # Slippage
    slippage_pct: float = 0.0005     # 0.05% default

    # Latency
    latency_min_ms: int = 50
    latency_max_ms: int = 200
    adverse_drift_pct: float = 0.0002  # 0.02% adverse drift during latency

    # Market impact
    avg_daily_volume: float = 1_000_000.0  # Default ADV for impact calc
    impact_coefficient: float = 0.1         # sqrt impact multiplier


@dataclass
class FillResult:
    """Result of a simulated order fill."""

    filled: bool
    fill_price: float = 0.0
    slippage_cost: float = 0.0
    commission_cost: float = 0.0
    latency_cost: float = 0.0
    impact_cost: float = 0.0
    total_friction: float = 0.0
    details: dict = field(default_factory=dict)
