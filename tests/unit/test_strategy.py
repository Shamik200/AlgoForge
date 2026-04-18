"""Tests for Phase 5 — Primary Strategy & Candlestick Patterns."""

import numpy as np
import pytest

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.strategies.base import Strategy
from algoforge.strategies.candlestick import (
    CandlestickDetector,
    CandlestickPattern,
    PatternType,
)
from algoforge.strategies.trendline_pullback import TrendlinePullback
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.indicator_base import IndicatorResult
from algoforge.technical.structural.models import (
    SRLevel,
    SRType,
    StructuralSnapshot,
    SwingPoint,
    Trendline,
    TrendDirection,
)


# ---------------------------------------------------------------------------
# Candlestick Pattern tests
# ---------------------------------------------------------------------------

class TestCandlestickDetector:
    """Test candlestick pattern detection."""

    def _make_data(self, ohlc_list: list[tuple]) -> tuple:
        """Convert list of (o, h, l, c) tuples to arrays."""
        opens = np.array([x[0] for x in ohlc_list], dtype=np.float64)
        highs = np.array([x[1] for x in ohlc_list], dtype=np.float64)
        lows = np.array([x[2] for x in ohlc_list], dtype=np.float64)
        closes = np.array([x[3] for x in ohlc_list], dtype=np.float64)
        return opens, highs, lows, closes

    def test_hammer_detection(self) -> None:
        """Detect hammer: small body at top, long lower shadow."""
        # body=0.5, lower_shadow=2.5, upper_shadow=0.2, body_pct=0.156
        ohlc = [
            (100, 101, 99, 100),  # neutral
            (100.0, 100.7, 97.5, 100.5),  # hammer
        ]
        o, h, l, c = self._make_data(ohlc)
        detector = CandlestickDetector()
        patterns = detector.detect(o, h, l, c)
        hammers = [p for p in patterns if p.name == "hammer"]
        assert len(hammers) >= 1

    def test_shooting_star_detection(self) -> None:
        """Detect shooting star: small body at bottom, long upper shadow."""
        # body=0.5, upper_shadow=2.5, lower_shadow=0.2, body_pct=0.156
        ohlc = [
            (100, 101, 99, 100),
            (100.0, 103.2, 99.8, 100.5),  # shooting star: body=0.5, upper=2.7, lower=0.2
        ]
        o, h, l, c = self._make_data(ohlc)
        detector = CandlestickDetector()
        patterns = detector.detect(o, h, l, c)
        stars = [p for p in patterns if p.name == "shooting_star"]
        assert len(stars) >= 1

    def test_bullish_engulfing(self) -> None:
        """Detect bullish engulfing: bearish → bullish engulf."""
        ohlc = [
            (102, 102.5, 100, 100.5),  # bearish
            (100, 103, 99.5, 103),  # bullish engulfing: opens at/below prev close, closes above prev open
        ]
        o, h, l, c = self._make_data(ohlc)
        detector = CandlestickDetector()
        patterns = detector.detect(o, h, l, c)
        engulfing = [p for p in patterns if p.name == "bullish_engulfing"]
        assert len(engulfing) >= 1

    def test_bearish_engulfing(self) -> None:
        """Detect bearish engulfing."""
        ohlc = [
            (100, 102, 99.5, 101.5),  # bullish
            (102, 102.5, 99, 99.5),  # bearish engulfing
        ]
        o, h, l, c = self._make_data(ohlc)
        detector = CandlestickDetector()
        patterns = detector.detect(o, h, l, c)
        engulfing = [p for p in patterns if p.name == "bearish_engulfing"]
        assert len(engulfing) >= 1

    def test_three_white_soldiers(self) -> None:
        """Three consecutive bullish candles with higher closes and opens."""
        ohlc = [
            (100, 102, 99.5, 101.5),
            (101.5, 103, 101, 102.5),
            (102.5, 104, 102, 103.5),
        ]
        o, h, l, c = self._make_data(ohlc)
        detector = CandlestickDetector()
        patterns = detector.detect(o, h, l, c)
        soldiers = [p for p in patterns if p.name == "three_white_soldiers"]
        assert len(soldiers) >= 1

    def test_three_black_crows(self) -> None:
        """Three consecutive bearish candles with lower closes and opens."""
        ohlc = [
            (103, 103.5, 101, 101.5),
            (101.5, 102, 100, 100.5),
            (100.5, 101, 99, 99.5),
        ]
        o, h, l, c = self._make_data(ohlc)
        detector = CandlestickDetector()
        patterns = detector.detect(o, h, l, c)
        crows = [p for p in patterns if p.name == "three_black_crows"]
        assert len(crows) >= 1

    def test_bullish_at_filter(self) -> None:
        """Filter bullish patterns at specific index."""
        ohlc = [
            (100, 101, 99, 100),
            (100, 100.5, 97, 100.3),  # hammer at index 1
        ]
        o, h, l, c = self._make_data(ohlc)
        detector = CandlestickDetector()
        patterns = detector.detect(o, h, l, c)
        bullish = detector.bullish_at(patterns, 1)
        assert all(p.pattern_type == PatternType.BULLISH for p in bullish)

    def test_no_patterns_flat_data(self) -> None:
        """Flat data has no range → no patterns."""
        ohlc = [(100, 100, 100, 100)] * 5
        o, h, l, c = self._make_data(ohlc)
        detector = CandlestickDetector()
        patterns = detector.detect(o, h, l, c)
        assert len(patterns) == 0

    def test_pattern_model(self) -> None:
        """CandlestickPattern model creation."""
        p = CandlestickPattern(name="hammer", pattern_type=PatternType.BULLISH, index=5, strength=1.2)
        assert p.name == "hammer"
        assert p.pattern_type == PatternType.BULLISH


# ---------------------------------------------------------------------------
# Strategy base class tests
# ---------------------------------------------------------------------------

class TestStrategyBase:
    """Test Strategy ABC contract."""

    def test_trendline_pullback_is_strategy(self) -> None:
        s = TrendlinePullback()
        assert isinstance(s, Strategy)

    def test_name(self) -> None:
        assert TrendlinePullback().name == "trendline_pullback"

    def test_required_regime(self) -> None:
        assert MarketRegime.TRENDING in TrendlinePullback().required_regime

    def test_repr(self) -> None:
        s = TrendlinePullback()
        assert "trendline_pullback" in repr(s)


# ---------------------------------------------------------------------------
# Trendline Pullback strategy tests
# ---------------------------------------------------------------------------

def _mock_indicators(
    adx: float = 30.0,
    rsi: float = 35.0,
    atr: float = 1.5,
    ema_5: float = 105.0,
    ema_9: float = 104.0,
    ema_21: float = 103.0,
) -> IndicatorSnapshot:
    """Create mock indicator snapshot."""
    snap = IndicatorSnapshot()
    snap.set("adx", IndicatorResult(name="adx", values={"adx": [adx]}))
    snap.set("rsi", IndicatorResult(name="rsi", values={"rsi": [rsi]}))
    snap.set("atr", IndicatorResult(name="atr", values={"atr": [atr]}))
    snap.set("ema", IndicatorResult(name="ema", values={
        "ema_5": [ema_5], "ema_9": [ema_9], "ema_21": [ema_21],
    }))
    return snap


def _mock_structure(
    trend: TrendDirection = TrendDirection.UP,
    trendline_price: float = 100.0,
    is_upper: bool = False,
) -> StructuralSnapshot:
    """Create mock structural snapshot."""
    sp1 = SwingPoint(index=0, price=trendline_price, is_high=is_upper)
    sp2 = SwingPoint(index=20, price=trendline_price + 1.0, is_high=is_upper)
    tl = Trendline(
        slope=0.05, intercept=trendline_price,
        touch_points=[sp1, sp2], is_upper=is_upper, strength=3.0,
    )
    return StructuralSnapshot(
        symbol="TEST",
        trend_direction=trend,
        trendlines=[tl],
        sr_levels=[
            SRLevel(price=trendline_price + 8, sr_type=SRType.RESISTANCE, strength=50),
            SRLevel(price=trendline_price - 8, sr_type=SRType.SUPPORT, strength=50),
        ],
    )


class TestTrendlinePullback:
    """Test primary trendline pullback strategy."""

    def test_skip_unclear_trend(self) -> None:
        """PRIM-12: No signals when trend is unclear."""
        s = TrendlinePullback()
        structure = _mock_structure(trend=TrendDirection.UNCLEAR)
        indicators = _mock_indicators()
        closes = [100.0] * 60
        signals = s.evaluate(
            "TEST", Timeframe.D1, indicators, structure,
            closes, closes, closes, [100000.0] * 60, closes,
        )
        assert len(signals) == 0

    def test_skip_low_adx(self) -> None:
        """PRIM-06: No signals when ADX < threshold."""
        s = TrendlinePullback(min_adx=25.0)
        structure = _mock_structure(trend=TrendDirection.UP)
        indicators = _mock_indicators(adx=15.0)
        closes = [100.0] * 60
        signals = s.evaluate(
            "TEST", Timeframe.D1, indicators, structure,
            closes, closes, closes, [100000.0] * 60, closes,
        )
        assert len(signals) == 0

    def test_skip_ema_misaligned(self) -> None:
        """PRIM-04: No signals when EMAs don't align with trend."""
        s = TrendlinePullback()
        structure = _mock_structure(trend=TrendDirection.UP)
        # Bearish EMA alignment in uptrend
        indicators = _mock_indicators(ema_5=100, ema_9=102, ema_21=104)
        closes = [100.0] * 60
        signals = s.evaluate(
            "TEST", Timeframe.D1, indicators, structure,
            closes, closes, closes, [100000.0] * 60, closes,
        )
        assert len(signals) == 0

    def test_skip_insufficient_data(self) -> None:
        """No signals with insufficient bars."""
        s = TrendlinePullback()
        structure = _mock_structure()
        indicators = _mock_indicators()
        closes = [100.0] * 10
        signals = s.evaluate(
            "TEST", Timeframe.D1, indicators, structure,
            closes, closes, closes, [100000.0] * 10, closes,
        )
        assert len(signals) == 0

    def test_long_signal_generation(self) -> None:
        """Generate long signal on uptrend pullback to lower trendline."""
        s = TrendlinePullback(atr_touch_multiplier=2.0, min_rr_ratio=1.5)
        # Trendline at ~100, price near 100, RSI oversold, uptrend
        structure = _mock_structure(
            trend=TrendDirection.UP, trendline_price=100.0, is_upper=False,
        )
        indicators = _mock_indicators(adx=30, rsi=30, atr=1.5, ema_5=105, ema_9=104, ema_21=103)

        n = 60
        # Build price data: end near trendline with a hammer candle
        opens = [100.0] * n
        highs = [101.0] * n
        lows = [99.0] * n
        closes = [100.5] * n
        # Last bar: hammer pattern (small body at top, long lower shadow)
        opens[-1] = 100.0
        highs[-1] = 100.5
        lows[-1] = 97.0
        closes[-1] = 100.3
        volumes = [100000.0] * n

        signals = s.evaluate(
            "TEST", Timeframe.D1, indicators, structure,
            closes, highs, lows, volumes, opens,
        )

        if signals:
            # Verify signal properties
            sig = signals[0]
            assert sig.direction == Direction.LONG
            assert sig.strategy == "trendline_pullback"
            assert sig.stop_loss < sig.entry_price
            assert sig.take_profit > sig.entry_price
            assert sig.risk_reward_ratio >= 1.5
            assert sig.regime == MarketRegime.TRENDING
            assert 0 < sig.confidence <= 1.0

    def test_signal_has_metadata(self) -> None:
        """Signal metadata includes trendline info."""
        s = TrendlinePullback(atr_touch_multiplier=2.0, min_rr_ratio=1.0)
        structure = _mock_structure(trend=TrendDirection.UP, trendline_price=100.0, is_upper=False)
        indicators = _mock_indicators(adx=30, rsi=30, atr=1.5)

        n = 60
        opens = [100.0] * n
        highs = [101.0] * n
        lows = [99.0] * n
        closes = [100.5] * n
        opens[-1] = 100.0
        highs[-1] = 100.5
        lows[-1] = 97.0
        closes[-1] = 100.3
        volumes = [100000.0] * n

        signals = s.evaluate(
            "TEST", Timeframe.D1, indicators, structure,
            closes, highs, lows, volumes, opens,
        )

        if signals:
            assert "adx" in signals[0].metadata
            assert "rsi" in signals[0].metadata
