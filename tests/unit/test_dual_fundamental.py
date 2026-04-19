"""Tests for Phase 11 (Dual Timeframe) & Phase 12 (Fundamental Analysis)."""

import pytest
from datetime import datetime, timezone

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.strategies.dual_timeframe import DualTimeframeFilter, TIMEFRAME_HIERARCHY
from algoforge.fundamental.analysis import (
    EconomicEvent,
    FundamentalFilter,
    FundamentalSnapshot,
    Sentiment,
)
from algoforge.technical.structural.models import (
    SRLevel,
    SRType,
    StructuralSnapshot,
    TrendDirection,
)


def _sig(
    direction: Direction = Direction.LONG,
    regime: MarketRegime = MarketRegime.TRENDING,
    confidence: float = 0.7,
    entry: float = 100.0, sl: float = 95.0, tp: float = 115.0,
) -> Signal:
    return Signal(
        symbol="TEST", direction=direction, strategy="test",
        confidence=confidence, entry_price=entry, stop_loss=sl, take_profit=tp,
        timeframe=Timeframe.D1, regime=regime,
    )


def _struct(
    trend: TrendDirection = TrendDirection.UP,
    support: list[float] | None = None,
    resistance: list[float] | None = None,
) -> StructuralSnapshot:
    levels = []
    for p in (support or []):
        levels.append(SRLevel(price=p, sr_type=SRType.SUPPORT, strength=50))
    for p in (resistance or []):
        levels.append(SRLevel(price=p, sr_type=SRType.RESISTANCE, strength=50))
    return StructuralSnapshot(symbol="TEST", trend_direction=trend, sr_levels=levels)


# ---------------------------------------------------------------------------
# Dual Timeframe Filter
# ---------------------------------------------------------------------------

class TestDualTimeframeFilter:
    """Test dual timeframe signal filtering."""

    def test_trend_aligned_passes(self) -> None:
        """DUAL-01: Long + HTF UP → approved."""
        dtf = DualTimeframeFilter()
        sig = _sig(Direction.LONG)
        htf = _struct(TrendDirection.UP)
        result = dtf.filter([sig], htf, MarketRegime.TRENDING)
        assert len(result) == 1

    def test_trend_misaligned_rejected(self) -> None:
        """DUAL-01: Long + HTF DOWN → rejected."""
        dtf = DualTimeframeFilter()
        sig = _sig(Direction.LONG)
        htf = _struct(TrendDirection.DOWN)
        result = dtf.filter([sig], htf, MarketRegime.TRENDING)
        assert len(result) == 0

    def test_short_rejected_in_uptrend(self) -> None:
        """DUAL-01: Short + HTF UP → rejected."""
        dtf = DualTimeframeFilter()
        sig = _sig(Direction.SHORT, entry=100, sl=105, tp=85)
        htf = _struct(TrendDirection.UP)
        result = dtf.filter([sig], htf, MarketRegime.TRENDING)
        assert len(result) == 0

    def test_regime_compatible(self) -> None:
        """DUAL-02: Compatible regimes pass."""
        dtf = DualTimeframeFilter()
        sig = _sig(regime=MarketRegime.TRENDING)
        htf = _struct(TrendDirection.UP)
        result = dtf.filter([sig], htf, MarketRegime.TRENDING)
        assert len(result) == 1

    def test_regime_incompatible(self) -> None:
        """DUAL-02: Incompatible regimes rejected."""
        dtf = DualTimeframeFilter()
        sig = _sig(regime=MarketRegime.TRENDING)
        htf = _struct(TrendDirection.UP)
        result = dtf.filter([sig], htf, MarketRegime.RANGE)
        assert len(result) == 0

    def test_target_refinement(self) -> None:
        """DUAL-03: TP refined with HTF S/R."""
        dtf = DualTimeframeFilter()
        sig = _sig(Direction.LONG, entry=100, sl=95, tp=115)
        htf = _struct(TrendDirection.UP, resistance=[110.0])
        result = dtf.filter([sig], htf, MarketRegime.TRENDING)
        assert len(result) == 1
        assert result[0].take_profit == 110.0  # Refined to HTF resistance

    def test_unclear_trend_passes(self) -> None:
        """Unclear HTF trend doesn't block."""
        dtf = DualTimeframeFilter()
        sig = _sig(Direction.LONG)
        htf = _struct(TrendDirection.UNCLEAR)
        result = dtf.filter([sig], htf, MarketRegime.TRENDING)
        assert len(result) == 1

    def test_timeframe_hierarchy(self) -> None:
        """Verify timeframe hierarchy mapping."""
        assert TIMEFRAME_HIERARCHY[Timeframe.M5] == Timeframe.M15
        assert TIMEFRAME_HIERARCHY[Timeframe.H1] == Timeframe.H4
        assert TIMEFRAME_HIERARCHY[Timeframe.D1] == Timeframe.W1

    def test_get_higher_timeframe(self) -> None:
        assert DualTimeframeFilter.get_higher_timeframe(Timeframe.H1) == Timeframe.H4
        assert DualTimeframeFilter.get_higher_timeframe(Timeframe.W1) is None

    def test_multiple_signals_filtered(self) -> None:
        """Mix of approved and rejected signals."""
        dtf = DualTimeframeFilter()
        signals = [
            _sig(Direction.LONG),   # Approved (trend aligned)
            _sig(Direction.SHORT, entry=100, sl=105, tp=85),  # Rejected (against trend)
        ]
        htf = _struct(TrendDirection.UP)
        result = dtf.filter(signals, htf, MarketRegime.TRENDING)
        assert len(result) == 1
        assert result[0].direction == Direction.LONG


# ---------------------------------------------------------------------------
# Fundamental Analysis Filter
# ---------------------------------------------------------------------------

class TestFundamentalSnapshot:
    """Test fundamental data models."""

    def test_default_snapshot(self) -> None:
        snap = FundamentalSnapshot(symbol="AAPL")
        assert snap.sentiment == Sentiment.NEUTRAL
        assert snap.sentiment_score == 0.0

    def test_economic_event(self) -> None:
        ev = EconomicEvent(
            name="NFP", currency="USD", importance="high",
            timestamp=datetime.now(timezone.utc),
        )
        assert ev.importance == "high"


class TestFundamentalFilter:
    """Test fundamental signal filtering."""

    def test_no_data_passes(self) -> None:
        """No fundamental data → signal passes through."""
        ff = FundamentalFilter()
        sig = _sig()
        result = ff.filter([sig], {})
        assert len(result) == 1

    def test_earnings_blackout(self) -> None:
        """FUND-04: Block during earnings."""
        ff = FundamentalFilter(earnings_blackout=True)
        sig = _sig()
        snap = FundamentalSnapshot(symbol="TEST", has_earnings_soon=True)
        result = ff.filter([sig], {"TEST": snap})
        assert len(result) == 0

    def test_high_impact_event_blocks(self) -> None:
        """FUND-02: High-impact event blocks trading."""
        ff = FundamentalFilter(block_high_impact=True)
        sig = _sig()
        snap = FundamentalSnapshot(
            symbol="TEST",
            upcoming_events=[
                EconomicEvent(
                    name="FOMC", currency="USD", importance="high",
                    timestamp=datetime.now(timezone.utc),
                ),
            ],
        )
        result = ff.filter([sig], {"TEST": snap})
        assert len(result) == 0

    def test_sentiment_contradiction_blocks(self) -> None:
        """FUND-01: Very bearish sentiment blocks LONG."""
        ff = FundamentalFilter()
        sig = _sig(Direction.LONG)
        snap = FundamentalSnapshot(symbol="TEST", sentiment=Sentiment.VERY_BEARISH)
        result = ff.filter([sig], {"TEST": snap})
        assert len(result) == 0

    def test_bullish_sentiment_boosts_long(self) -> None:
        """FUND-03: Bullish sentiment boosts LONG confidence."""
        ff = FundamentalFilter(sentiment_boost=0.1)
        sig = _sig(Direction.LONG, confidence=0.6)
        snap = FundamentalSnapshot(symbol="TEST", sentiment=Sentiment.VERY_BULLISH)
        result = ff.filter([sig], {"TEST": snap})
        assert len(result) == 1
        assert result[0].confidence > 0.6

    def test_bearish_sentiment_reduces_long(self) -> None:
        """FUND-03: Bearish sentiment reduces LONG confidence."""
        ff = FundamentalFilter(sentiment_penalty=0.15)
        sig = _sig(Direction.LONG, confidence=0.7)
        snap = FundamentalSnapshot(symbol="TEST", sentiment=Sentiment.BEARISH)
        result = ff.filter([sig], {"TEST": snap})
        assert len(result) == 1
        assert result[0].confidence < 0.7

    def test_neutral_no_adjustment(self) -> None:
        """Neutral sentiment → no confidence change."""
        ff = FundamentalFilter()
        sig = _sig(confidence=0.7)
        snap = FundamentalSnapshot(symbol="TEST", sentiment=Sentiment.NEUTRAL)
        result = ff.filter([sig], {"TEST": snap})
        assert len(result) == 1
        assert result[0].confidence == 0.7

    def test_very_bullish_blocks_short(self) -> None:
        """FUND-01: Very bullish blocks SHORT."""
        ff = FundamentalFilter()
        sig = _sig(Direction.SHORT, entry=100, sl=105, tp=85)
        snap = FundamentalSnapshot(symbol="TEST", sentiment=Sentiment.VERY_BULLISH)
        result = ff.filter([sig], {"TEST": snap})
        assert len(result) == 0
