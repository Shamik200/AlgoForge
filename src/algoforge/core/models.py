"""AlgoForge core data models.

Pydantic models for all data structures — OHLCV candles, signals,
positions, and portfolio state. Strict validation ensures data integrity
at the boundary of every component.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from algoforge.core.constants import Direction, MarketRegime, Timeframe


# ---------------------------------------------------------------------------
# Market Data Models
# ---------------------------------------------------------------------------


class OHLCV(BaseModel):
    """Single OHLCV candle — the atomic data unit of the system.

    Every piece of market data flows through the system as an OHLCV record.
    Validation ensures no corrupted data propagates downstream.
    """

    symbol: str = Field(..., min_length=1, description="Ticker symbol (e.g., AAPL, BTC-USD)")
    timeframe: Timeframe = Field(..., description="Candle timeframe")
    timestamp: datetime = Field(..., description="Candle open time (UTC)")
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price in period")
    low: float = Field(..., gt=0, description="Lowest price in period")
    close: float = Field(..., gt=0, description="Closing price")
    volume: float = Field(..., ge=0, description="Trading volume")

    @model_validator(mode="after")
    def validate_hloc_consistency(self) -> OHLCV:
        """Ensure high >= low and high >= open/close, low <= open/close."""
        if self.high < self.low:
            msg = f"high ({self.high}) must be >= low ({self.low})"
            raise ValueError(msg)
        if self.high < max(self.open, self.close):
            msg = f"high ({self.high}) must be >= max(open, close) ({max(self.open, self.close)})"
            raise ValueError(msg)
        if self.low > min(self.open, self.close):
            msg = f"low ({self.low}) must be <= min(open, close) ({min(self.open, self.close)})"
            raise ValueError(msg)
        return self

    def to_redis_key(self) -> str:
        """Generate Redis sorted set key for this candle's symbol/timeframe."""
        return f"ohlcv:{self.symbol}:{self.timeframe.value}"

    def to_redis_score(self) -> float:
        """Generate Redis sorted set score (timestamp as float)."""
        return self.timestamp.timestamp()

    @property
    def body_size(self) -> float:
        """Absolute size of the candle body."""
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        """Size of the upper wick/shadow."""
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        """Size of the lower wick/shadow."""
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        """True if close > open (green candle)."""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """True if close < open (red candle)."""
        return self.close < self.open

    @property
    def range(self) -> float:
        """Total price range (high - low)."""
        return self.high - self.low

    @property
    def mid_price(self) -> float:
        """Mid-price of the candle."""
        return (self.high + self.low) / 2

    def to_timescale_row(self) -> tuple:
        """Convert to a tuple for TimescaleDB INSERT."""
        return (
            self.timestamp,
            self.symbol,
            self.timeframe.value,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
        )

    @classmethod
    def from_timescale_row(cls, row: dict) -> "OHLCV":
        """Create OHLCV from a TimescaleDB row dict."""
        return cls(
            symbol=row["symbol"],
            timeframe=Timeframe(row["timeframe"]),
            timestamp=row["timestamp"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )


class OHLCVSeries(BaseModel):
    """Ordered collection of OHLCV candles for a single symbol/timeframe.

    Used for batch operations, indicator calculation, and resampling.
    """

    symbol: str
    timeframe: Timeframe
    candles: list[OHLCV] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True if no candles in the series."""
        return len(self.candles) == 0

    @property
    def count(self) -> int:
        """Number of candles."""
        return len(self.candles)

    @property
    def latest(self) -> OHLCV | None:
        """Most recent candle (last in list)."""
        return self.candles[-1] if self.candles else None

    @property
    def oldest(self) -> OHLCV | None:
        """Oldest candle (first in list)."""
        return self.candles[0] if self.candles else None

    @property
    def closes(self) -> list[float]:
        """List of close prices — common input for indicators."""
        return [c.close for c in self.candles]

    @property
    def highs(self) -> list[float]:
        """List of high prices."""
        return [c.high for c in self.candles]

    @property
    def lows(self) -> list[float]:
        """List of low prices."""
        return [c.low for c in self.candles]

    @property
    def volumes(self) -> list[float]:
        """List of volumes."""
        return [c.volume for c in self.candles]

    def append(self, candle: OHLCV) -> None:
        """Add a candle to the end of the series."""
        self.candles.append(candle)

    def tail(self, n: int) -> list[OHLCV]:
        """Get the last N candles."""
        return self.candles[-n:]


# ---------------------------------------------------------------------------
# Trading Models
# ---------------------------------------------------------------------------


class Signal(BaseModel):
    """Trading signal generated by a strategy.

    Every signal MUST include stop_loss and take_profit — enforced by
    the risk management engine. No trade is allowed without a stop loss.
    """

    symbol: str
    direction: Direction
    strategy: str = Field(..., min_length=1, description="Strategy name that generated this signal")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Signal confidence 0-1")
    entry_price: float = Field(..., gt=0, description="Target entry price")
    stop_loss: float = Field(..., gt=0, description="Mandatory stop loss price")
    take_profit: float = Field(..., gt=0, description="Take profit price")
    timeframe: Timeframe = Field(default=Timeframe.M1, description="Timeframe the signal was generated on")
    regime: MarketRegime | None = Field(default=None, description="Market regime at signal time")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict, description="Strategy-specific metadata")

    @model_validator(mode="after")
    def validate_stop_loss_direction(self) -> Signal:
        """Ensure stop loss is on the correct side of entry."""
        if self.direction == Direction.LONG and self.stop_loss >= self.entry_price:
            msg = f"Long stop_loss ({self.stop_loss}) must be below entry ({self.entry_price})"
            raise ValueError(msg)
        if self.direction == Direction.SHORT and self.stop_loss <= self.entry_price:
            msg = f"Short stop_loss ({self.stop_loss}) must be above entry ({self.entry_price})"
            raise ValueError(msg)
        return self

    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk/reward ratio."""
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        return reward / risk if risk > 0 else 0.0


class Position(BaseModel):
    """An open trading position."""

    id: str = Field(..., description="Unique position identifier")
    symbol: str
    direction: Direction
    entry_price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    take_profit: float = Field(..., gt=0)
    strategy: str
    opened_at: datetime
    unrealized_pnl: float = 0.0
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        """Current market value of the position."""
        return self.current_price * self.quantity

    @property
    def entry_value(self) -> float:
        """Value at entry."""
        return self.entry_price * self.quantity


class PortfolioState(BaseModel):
    """Current portfolio state — snapshot of account status."""

    capital: float = Field(..., gt=0, description="Available cash")
    initial_capital: float = Field(..., gt=0, description="Starting capital")
    positions: list[Position] = Field(default_factory=list)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    @property
    def open_position_count(self) -> int:
        """Number of open positions."""
        return len(self.positions)

    @property
    def win_rate(self) -> float:
        """Win rate as a percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def drawdown_pct(self) -> float:
        """Current drawdown percentage from initial capital."""
        if self.initial_capital == 0:
            return 0.0
        return ((self.initial_capital - self.capital - self.total_pnl) / self.initial_capital) * 100
