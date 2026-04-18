"""AlgoForge constants and enumerations.

All enums are str-based for YAML serialization and logging readability.
"""

from enum import Enum


class Market(str, Enum):
    """Supported markets — selected via config/settings.yaml."""

    STOCKS_INDIA = "stocks_india"
    STOCKS_US = "stocks_us"
    CRYPTO = "crypto"
    FOREX = "forex"


class Timeframe(str, Enum):
    """OHLCV timeframe intervals."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1wk"
    MO1 = "1mo"


class TimeframeMode(str, Enum):
    """Operational timeframe mode — determines which timeframes are used for S/R, trendlines, execution."""

    INTRADAY = "intraday"  # 1min exec, 15min-1h hold
    SWING = "swing"  # 1H/4H exec, 1week-1month hold


class Direction(str, Enum):
    """Trade direction."""

    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class MarketRegime(str, Enum):
    """Market regime classification — one of 5 categories."""

    TRENDING = "trending"
    RANGE = "range"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    LIQUIDITY_TRAP = "liquidity_trap"


class OrderType(str, Enum):
    """Order types for execution."""

    LIMIT = "limit"
    MARKET = "market"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


# ---------------------------------------------------------------------------
# Market Hours (UTC-based trading windows)
# ---------------------------------------------------------------------------

MARKET_HOURS: dict[Market, dict[str, str]] = {
    Market.STOCKS_INDIA: {"open": "03:45", "close": "10:00", "tz": "Asia/Kolkata"},
    Market.STOCKS_US: {"open": "14:30", "close": "21:00", "tz": "America/New_York"},
    Market.CRYPTO: {"open": "00:00", "close": "23:59", "tz": "UTC"},
    Market.FOREX: {"open": "00:00", "close": "23:59", "tz": "UTC"},
}

# ---------------------------------------------------------------------------
# Market-specific fee structures (for paper trading simulation)
# ---------------------------------------------------------------------------

MARKET_FEES: dict[Market, dict[str, float]] = {
    Market.STOCKS_INDIA: {
        "brokerage_pct": 0.03,  # Zerodha-like flat ₹20 or 0.03%
        "stt_pct": 0.1,  # Securities Transaction Tax
        "exchange_pct": 0.00345,
        "gst_pct": 18.0,  # on brokerage
        "stamp_duty_pct": 0.015,
    },
    Market.STOCKS_US: {
        "commission_per_share": 0.0,  # Most brokers now zero-commission
        "sec_fee_pct": 0.000008,
        "taf_per_share": 0.000166,
    },
    Market.CRYPTO: {
        "maker_pct": 0.1,
        "taker_pct": 0.1,
    },
    Market.FOREX: {
        "spread_pips": 1.0,
        "commission_per_lot": 3.5,
    },
}

# ---------------------------------------------------------------------------
# Default timeframe mappings per operational mode
# ---------------------------------------------------------------------------

TIMEFRAME_CONFIG: dict[TimeframeMode, dict[str, list[Timeframe] | Timeframe]] = {
    TimeframeMode.INTRADAY: {
        "sr_timeframes": [Timeframe.D1, Timeframe.H1],
        "trendline_timeframes": [Timeframe.M15, Timeframe.M5],
        "execution_timeframe": Timeframe.M1,
    },
    TimeframeMode.SWING: {
        "sr_timeframes": [Timeframe.MO1, Timeframe.W1],
        "trendline_timeframes": [Timeframe.W1, Timeframe.D1],
        "execution_timeframe": Timeframe.H1,
    },
}

# ---------------------------------------------------------------------------
# Default paper trading capital per market
# ---------------------------------------------------------------------------

DEFAULT_CAPITAL: dict[Market, tuple[float, str]] = {
    Market.STOCKS_INDIA: (10_000_000.0, "INR"),  # ₹1 Crore
    Market.STOCKS_US: (100_000.0, "USD"),  # $100K
    Market.CRYPTO: (100_000.0, "USD"),  # $100K
    Market.FOREX: (100_000.0, "USD"),  # $100K
}
