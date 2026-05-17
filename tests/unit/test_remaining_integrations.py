"""Regression tests for the remaining integration slices."""

from datetime import datetime, timedelta, timezone

import numpy as np

from algoforge.core.constants import Timeframe
from algoforge.core.error_recovery import ErrorRecoveryManager
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.core.pairs_coordinator import PairTradingCoordinator
from algoforge.core.timeframe_coordinator import TimeframeCoordinator
from algoforge.signals.microstructure.family import MicrostructureFamily
from algoforge.technical.engine import IndicatorEngine
from algoforge.technical.regime import RegimeClassifier
from algoforge.technical.structural.engine import StructuralEngine


def _m1_series(symbol: str = "TEST", n: int = 120) -> OHLCVSeries:
    candles = []
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    for index in range(n):
        price += 0.2 if index % 4 != 0 else -0.1
        candles.append(
            OHLCV(
                symbol=symbol,
                timeframe=Timeframe.M1,
                timestamp=base_time + timedelta(minutes=index),
                open=price - 0.1,
                high=price + 0.4,
                low=price - 0.5,
                close=price,
                volume=1000 + index,
            )
        )
    return OHLCVSeries(symbol=symbol, timeframe=Timeframe.M1, candles=candles)


def test_error_recovery_manager_classifies_retryable_errors() -> None:
    manager = ErrorRecoveryManager(default_retry_delay_seconds=3.0)
    decision = manager.handle_exception(ConnectionError("socket closed"), "live_tick")
    assert decision.should_retry is True
    assert decision.retry_delay_seconds == 3.0
    assert "retry:live_tick" in decision.fallback_message

    non_retry = manager.handle_exception(ValueError("bad input"), "live_tick")
    assert non_retry.should_retry is False
    assert non_retry.retry_delay_seconds == 0.0


def test_timeframe_coordinator_builds_context() -> None:
    series = _m1_series()
    coordinator = TimeframeCoordinator()
    context = coordinator.build_context(
        "TEST",
        series,
        IndicatorEngine(),
        StructuralEngine(),
        RegimeClassifier(),
    )

    assert context is not None
    assert context.target_timeframe == Timeframe.M5
    assert context.htf_series.timeframe == Timeframe.M5
    assert context.htf_structure.symbol == "TEST"


def test_pairs_coordinator_generates_signal() -> None:
    np.random.seed(42)
    n = 160
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    b_prices = np.cumsum(np.random.randn(n)) + 100
    noise = np.random.randn(n) * 0.25
    a_prices = 2.0 * b_prices + 50 + noise

    def build_series(symbol: str, prices: np.ndarray) -> list[OHLCV]:
        return [
            OHLCV(
                symbol=symbol,
                timeframe=Timeframe.M1,
                timestamp=base_time + timedelta(minutes=index),
                open=float(price - 0.2),
                high=float(price + 0.5),
                low=float(price - 0.5),
                close=float(price),
                volume=1000 + index,
            )
            for index, price in enumerate(prices)
        ]

    buffers = {
        "A": build_series("A", a_prices),
        "B": build_series("B", b_prices),
    }
    coordinator = PairTradingCoordinator()
    context = coordinator.build_signal("A", ["A", "B"], buffers)

    assert context is not None
    assert context.primary_symbol == "A"
    assert context.partner_symbol == "B"
    assert context.signal.family_name == "pairs"


def test_microstructure_family_uses_order_book_l2() -> None:
    family = MicrostructureFamily(timeframe="5m")
    result = None
    for index in range(25):
        price = 100 + index * 0.4
        result = family.generate(
            high=price + 1,
            low=price - 1,
            close=price,
            volume=1000,
            order_book={"bid": price - 0.1, "ask": price + 0.1, "bid_qty": 900, "ask_qty": 100},
        )

    assert result is not None
    assert result.is_valid is True
    assert result.metadata["mode"] == "L2"
    assert "book_imbalance" in result.metadata
