"""Tests for TimescaleDB storage adapter — mocked asyncpg, no real DB needed."""

from datetime import datetime, timezone

import pytest

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV


class TestOHLCVTimescaleSerialization:
    """Test OHLCV to/from TimescaleDB row conversion."""

    def _make_candle(self) -> OHLCV:
        return OHLCV(
            symbol="AAPL",
            timeframe=Timeframe.M1,
            timestamp=datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc),
            open=150.0,
            high=152.0,
            low=149.0,
            close=151.0,
            volume=10000.0,
        )

    def test_to_timescale_row_returns_tuple(self) -> None:
        candle = self._make_candle()
        row = candle.to_timescale_row()
        assert isinstance(row, tuple)
        assert len(row) == 8

    def test_to_timescale_row_values(self) -> None:
        candle = self._make_candle()
        row = candle.to_timescale_row()
        assert row[0] == datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)
        assert row[1] == "AAPL"
        assert row[2] == "1m"
        assert row[3] == 150.0
        assert row[4] == 152.0
        assert row[5] == 149.0
        assert row[6] == 151.0
        assert row[7] == 10000.0

    def test_from_timescale_row(self) -> None:
        row = {
            "symbol": "MSFT",
            "timeframe": "5m",
            "timestamp": datetime(2024, 1, 15, 14, 35, tzinfo=timezone.utc),
            "open": 400.0,
            "high": 405.0,
            "low": 399.0,
            "close": 403.0,
            "volume": 5000.0,
        }
        candle = OHLCV.from_timescale_row(row)
        assert candle.symbol == "MSFT"
        assert candle.timeframe == Timeframe.M5
        assert candle.open == 400.0
        assert candle.volume == 5000.0

    def test_roundtrip_serialization(self) -> None:
        """to_timescale_row → dict → from_timescale_row should produce equal candle."""
        original = self._make_candle()
        row = original.to_timescale_row()
        keys = ["timestamp", "symbol", "timeframe", "open", "high", "low", "close", "volume"]
        row_dict = dict(zip(keys, row))
        restored = OHLCV.from_timescale_row(row_dict)
        assert restored.symbol == original.symbol
        assert restored.timeframe == original.timeframe
        assert restored.timestamp == original.timestamp
        assert restored.open == original.open
        assert restored.close == original.close
        assert restored.volume == original.volume


class TestTimescaleStoreInstantiation:
    """Test TimescaleStore can be imported and instantiated."""

    def test_import(self) -> None:
        from algoforge.data.storage.timescale_store import TimescaleStore
        store = TimescaleStore()
        assert store._pool is None

    def test_has_connect_method(self) -> None:
        from algoforge.data.storage.timescale_store import TimescaleStore
        store = TimescaleStore()
        assert hasattr(store, "connect")
        assert hasattr(store, "disconnect")
        assert hasattr(store, "health_check")

    def test_has_crud_methods(self) -> None:
        from algoforge.data.storage.timescale_store import TimescaleStore
        store = TimescaleStore()
        assert hasattr(store, "store_candle")
        assert hasattr(store, "store_candles")
        assert hasattr(store, "query_candles")
        assert hasattr(store, "get_latest_candle")
        assert hasattr(store, "get_candle_count")

    def test_schema_constants_defined(self) -> None:
        from algoforge.data.storage.timescale_store import (
            CREATE_HYPERTABLE,
            CREATE_INDEX,
            CREATE_OHLCV_TABLE,
        )
        assert "CREATE TABLE" in CREATE_OHLCV_TABLE
        assert "create_hypertable" in CREATE_HYPERTABLE
        assert "CREATE INDEX" in CREATE_INDEX
