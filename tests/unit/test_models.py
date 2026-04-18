"""Tests for core data models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from algoforge.core.constants import Direction, Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries, PortfolioState, Signal


class TestOHLCV:
    """Test OHLCV candle model validation."""

    def _make_candle(self, **kwargs) -> OHLCV:
        """Helper to create a valid candle with overrides."""
        defaults = {
            "symbol": "AAPL",
            "timeframe": Timeframe.M1,
            "timestamp": datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 1000.0,
        }
        defaults.update(kwargs)
        return OHLCV(**defaults)

    def test_ohlcv_valid_creation(self) -> None:
        """Valid OHLCV creates successfully."""
        candle = self._make_candle()
        assert candle.symbol == "AAPL"
        assert candle.open == 100.0
        assert candle.high == 102.0
        assert candle.low == 99.0
        assert candle.close == 101.0
        assert candle.volume == 1000.0

    def test_ohlcv_high_must_be_gte_low(self) -> None:
        """High < low raises ValidationError."""
        with pytest.raises(ValidationError, match="high.*must be >= low"):
            self._make_candle(high=98.0, low=99.0)

    def test_ohlcv_negative_price_rejected(self) -> None:
        """Negative open price raises ValidationError."""
        with pytest.raises(ValidationError):
            self._make_candle(open=-1.0)

    def test_ohlcv_zero_price_rejected(self) -> None:
        """Zero close price raises ValidationError."""
        with pytest.raises(ValidationError):
            self._make_candle(close=0.0)

    def test_ohlcv_negative_volume_rejected(self) -> None:
        """Negative volume raises ValidationError."""
        with pytest.raises(ValidationError):
            self._make_candle(volume=-100)

    def test_ohlcv_zero_volume_allowed(self) -> None:
        """Zero volume is valid (some candles have zero volume)."""
        candle = self._make_candle(volume=0.0)
        assert candle.volume == 0.0

    def test_ohlcv_redis_key_format(self) -> None:
        """to_redis_key returns correct ohlcv:{symbol}:{timeframe} format."""
        candle = self._make_candle()
        key = candle.to_redis_key()
        assert key == "ohlcv:AAPL:1m"

    def test_ohlcv_is_bullish(self) -> None:
        """Bullish candle has close > open."""
        candle = self._make_candle(open=100.0, high=106.0, close=105.0)
        assert candle.is_bullish is True
        assert candle.is_bearish is False

    def test_ohlcv_is_bearish(self) -> None:
        """Bearish candle has close < open."""
        candle = self._make_candle(open=105.0, close=100.0, high=106.0, low=99.0)
        assert candle.is_bearish is True
        assert candle.is_bullish is False

    def test_ohlcv_body_size(self) -> None:
        """Body size is abs(close - open)."""
        candle = self._make_candle(open=100.0, high=106.0, close=105.0)
        assert candle.body_size == 5.0

    def test_ohlcv_range(self) -> None:
        """Range is high - low."""
        candle = self._make_candle(high=110.0, low=90.0)
        assert candle.range == 20.0

    def test_ohlcv_high_must_be_gte_open_close(self) -> None:
        """High must be >= max(open, close)."""
        with pytest.raises(ValidationError, match="high.*must be >= max"):
            self._make_candle(open=100.0, high=99.0, low=95.0, close=98.0)


class TestOHLCVSeries:
    """Test OHLCVSeries collection model."""

    def _make_series(self, n: int = 5) -> OHLCVSeries:
        """Create a series with N candles."""
        candles = []
        for i in range(n):
            candles.append(
                OHLCV(
                    symbol="AAPL",
                    timeframe=Timeframe.M1,
                    timestamp=datetime(2024, 1, 15, 9, 30 + i, tzinfo=timezone.utc),
                    open=100.0 + i,
                    high=102.0 + i,
                    low=99.0 + i,
                    close=101.0 + i,
                    volume=1000.0 * (i + 1),
                )
            )
        return OHLCVSeries(symbol="AAPL", timeframe=Timeframe.M1, candles=candles)

    def test_series_latest(self) -> None:
        """latest returns the last candle in the series."""
        series = self._make_series(5)
        assert series.latest is not None
        assert series.latest.close == 105.0

    def test_series_oldest(self) -> None:
        """oldest returns the first candle."""
        series = self._make_series(5)
        assert series.oldest is not None
        assert series.oldest.close == 101.0

    def test_series_empty(self) -> None:
        """Empty series reports is_empty=True."""
        series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.M1)
        assert series.is_empty is True
        assert series.latest is None
        assert series.count == 0

    def test_series_closes(self) -> None:
        """closes property returns list of close prices."""
        series = self._make_series(3)
        assert series.closes == [101.0, 102.0, 103.0]

    def test_series_tail(self) -> None:
        """tail(2) returns last 2 candles."""
        series = self._make_series(5)
        tail = series.tail(2)
        assert len(tail) == 2


class TestSignal:
    """Test Signal model validation."""

    def test_signal_valid_creation(self) -> None:
        """Valid signal creates successfully."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="trendline_pullback",
            confidence=0.85,
            entry_price=150.0,
            stop_loss=145.0,
            take_profit=160.0,
        )
        assert signal.confidence == 0.85
        assert signal.strategy == "trendline_pullback"

    def test_signal_confidence_bounds(self) -> None:
        """Confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            Signal(
                symbol="AAPL",
                direction=Direction.LONG,
                strategy="test",
                confidence=1.5,
                entry_price=150.0,
                stop_loss=145.0,
                take_profit=160.0,
            )

    def test_signal_long_stop_loss_must_be_below(self) -> None:
        """Long signal stop_loss must be below entry."""
        with pytest.raises(ValidationError, match="Long stop_loss.*must be below"):
            Signal(
                symbol="AAPL",
                direction=Direction.LONG,
                strategy="test",
                confidence=0.8,
                entry_price=150.0,
                stop_loss=155.0,
                take_profit=160.0,
            )

    def test_signal_short_stop_loss_must_be_above(self) -> None:
        """Short signal stop_loss must be above entry."""
        with pytest.raises(ValidationError, match="Short stop_loss.*must be above"):
            Signal(
                symbol="AAPL",
                direction=Direction.SHORT,
                strategy="test",
                confidence=0.8,
                entry_price=150.0,
                stop_loss=145.0,
                take_profit=140.0,
            )

    def test_signal_risk_reward_ratio(self) -> None:
        """Risk/reward ratio calculation."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test",
            confidence=0.8,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=115.0,
        )
        assert signal.risk_reward_ratio == 3.0  # 15 reward / 5 risk


class TestPortfolioState:
    """Test PortfolioState model."""

    def test_win_rate_zero_trades(self) -> None:
        """Win rate is 0% with no trades."""
        state = PortfolioState(capital=100000.0, initial_capital=100000.0)
        assert state.win_rate == 0.0

    def test_win_rate_calculation(self) -> None:
        """Win rate correctly calculated."""
        state = PortfolioState(
            capital=110000.0,
            initial_capital=100000.0,
            total_trades=10,
            winning_trades=7,
        )
        assert state.win_rate == 70.0
