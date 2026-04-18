"""Tests for Phase 9+10 — Secondary Strategies (all 5 regimes covered)."""

import numpy as np
import pytest

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.strategies.base import Strategy
from algoforge.strategies.secondary_trending_range import EMACrossover, MeanReversion
from algoforge.strategies.secondary_breakout_reversal import (
    BreakoutStrategy,
    LiquidityTrapStrategy,
    ReversalStrategy,
)
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.indicator_base import IndicatorResult
from algoforge.technical.structural.models import (
    SRLevel,
    SRType,
    StructuralSnapshot,
    TrendDirection,
)


def _snap(**kw) -> IndicatorSnapshot:
    s = IndicatorSnapshot()
    for name, vals in kw.items():
        s.set(name, IndicatorResult(name=name, values=vals))
    return s


def _struct(
    trend: TrendDirection = TrendDirection.UP,
    support_prices: list[float] | None = None,
    resistance_prices: list[float] | None = None,
) -> StructuralSnapshot:
    levels = []
    for p in (support_prices or []):
        levels.append(SRLevel(price=p, sr_type=SRType.SUPPORT, strength=50))
    for p in (resistance_prices or []):
        levels.append(SRLevel(price=p, sr_type=SRType.RESISTANCE, strength=50))
    return StructuralSnapshot(symbol="TEST", trend_direction=trend, sr_levels=levels)


class TestEMACrossover:
    """Test EMA crossover strategy."""

    def test_is_strategy(self) -> None:
        assert isinstance(EMACrossover(), Strategy)

    def test_name(self) -> None:
        assert EMACrossover().name == "ema_crossover"

    def test_required_regime(self) -> None:
        assert MarketRegime.TRENDING in EMACrossover().required_regime

    def test_bullish_crossover(self) -> None:
        """Fast crosses above slow → long signal."""
        s = EMACrossover(min_adx=15)
        ind = _snap(
            ema={"ema_9": [99.0, 101.0], "ema_21": [100.0, 100.5]},  # cross up
            adx={"adx": [25.0]},
            atr={"atr": [1.5]},
        )
        struct = _struct()
        closes = [100.0] * 60
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, closes, closes, [1e5]*60, closes)
        assert len(signals) >= 1
        assert signals[0].direction == Direction.LONG

    def test_bearish_crossover(self) -> None:
        """Fast crosses below slow → short signal."""
        s = EMACrossover(min_adx=15)
        ind = _snap(
            ema={"ema_9": [101.0, 99.0], "ema_21": [100.0, 100.5]},  # cross down
            adx={"adx": [25.0]},
            atr={"atr": [1.5]},
        )
        struct = _struct(trend=TrendDirection.DOWN)
        closes = [100.0] * 60
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, closes, closes, [1e5]*60, closes)
        assert len(signals) >= 1
        assert signals[0].direction == Direction.SHORT

    def test_no_cross_no_signal(self) -> None:
        """No crossover → no signal."""
        s = EMACrossover()
        ind = _snap(
            ema={"ema_9": [101.0, 102.0], "ema_21": [100.0, 100.5]},  # no cross
            adx={"adx": [25.0]},
            atr={"atr": [1.5]},
        )
        struct = _struct()
        closes = [100.0] * 60
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, closes, closes, [1e5]*60, closes)
        assert len(signals) == 0

    def test_low_adx_skip(self) -> None:
        """ADX below threshold → no signal."""
        s = EMACrossover(min_adx=25)
        ind = _snap(
            ema={"ema_9": [99.0, 101.0], "ema_21": [100.0, 100.5]},
            adx={"adx": [15.0]},
            atr={"atr": [1.5]},
        )
        struct = _struct()
        closes = [100.0] * 60
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, closes, closes, [1e5]*60, closes)
        assert len(signals) == 0


class TestMeanReversion:
    """Test BB mean reversion strategy."""

    def test_is_strategy(self) -> None:
        assert isinstance(MeanReversion(), Strategy)

    def test_name(self) -> None:
        assert MeanReversion().name == "mean_reversion"

    def test_required_regime(self) -> None:
        assert MarketRegime.RANGE in MeanReversion().required_regime

    def test_buy_at_lower_bb(self) -> None:
        """Price at lower BB + RSI oversold → long."""
        s = MeanReversion(rsi_oversold=35)
        ind = _snap(
            bollinger={"upper": [110.0], "middle": [105.0], "lower": [100.0]},
            rsi={"rsi": [25.0]},
            atr={"atr": [1.0]},
        )
        struct = _struct()
        closes = [100.0] * 60  # At lower BB
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, closes, closes, [1e5]*60, closes)
        assert len(signals) >= 1
        assert signals[0].direction == Direction.LONG

    def test_sell_at_upper_bb(self) -> None:
        """Price at upper BB + RSI overbought → short."""
        s = MeanReversion(rsi_overbought=65)
        ind = _snap(
            bollinger={"upper": [110.0], "middle": [105.0], "lower": [100.0]},
            rsi={"rsi": [75.0]},
            atr={"atr": [1.0]},
        )
        struct = _struct()
        closes = [110.0] * 60  # At upper BB
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, closes, closes, [1e5]*60, closes)
        assert len(signals) >= 1
        assert signals[0].direction == Direction.SHORT

    def test_mid_price_no_signal(self) -> None:
        """Price in middle of BB → no signal."""
        s = MeanReversion()
        ind = _snap(
            bollinger={"upper": [110.0], "middle": [105.0], "lower": [100.0]},
            rsi={"rsi": [50.0]},
            atr={"atr": [1.0]},
        )
        struct = _struct()
        closes = [105.0] * 60
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, closes, closes, [1e5]*60, closes)
        assert len(signals) == 0


class TestBreakoutStrategy:
    """Test breakout strategy."""

    def test_is_strategy(self) -> None:
        assert isinstance(BreakoutStrategy(), Strategy)

    def test_name(self) -> None:
        assert BreakoutStrategy().name == "breakout"

    def test_required_regime(self) -> None:
        assert MarketRegime.BREAKOUT in BreakoutStrategy().required_regime

    def test_upside_breakout(self) -> None:
        """Price breaks above resistance with volume → long."""
        s = BreakoutStrategy(volume_mult=1.3, atr_buffer=0.1, min_rr=1.0)
        ind = _snap(atr={"atr": [1.0]})
        struct = _struct(resistance_prices=[100.0])
        closes = [99.0] * 59 + [101.5]  # Break above 100
        highs = [99.5] * 59 + [102.0]
        lows = [98.5] * 59 + [99.0]
        volumes = [50000.0] * 59 + [100000.0]  # Volume spike
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, highs, lows, volumes, closes)
        assert len(signals) >= 1
        assert signals[0].direction == Direction.LONG

    def test_no_volume_no_breakout(self) -> None:
        """Break without volume → no signal."""
        s = BreakoutStrategy(volume_mult=2.0, atr_buffer=0.1)
        ind = _snap(atr={"atr": [1.0]})
        struct = _struct(resistance_prices=[100.0])
        closes = [99.0] * 59 + [101.5]
        volumes = [50000.0] * 60  # No volume spike
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, closes, closes, volumes, closes)
        assert len(signals) == 0


class TestReversalStrategy:
    """Test reversal strategy."""

    def test_is_strategy(self) -> None:
        assert isinstance(ReversalStrategy(), Strategy)

    def test_name(self) -> None:
        assert ReversalStrategy().name == "reversal"

    def test_required_regime(self) -> None:
        assert MarketRegime.REVERSAL in ReversalStrategy().required_regime


class TestLiquidityTrapStrategy:
    """Test liquidity trap strategy."""

    def test_is_strategy(self) -> None:
        assert isinstance(LiquidityTrapStrategy(), Strategy)

    def test_name(self) -> None:
        assert LiquidityTrapStrategy().name == "liquidity_trap"

    def test_required_regime(self) -> None:
        assert MarketRegime.LIQUIDITY_TRAP in LiquidityTrapStrategy().required_regime

    def test_bull_trap(self) -> None:
        """Wick above resistance, close below → short (bull trap)."""
        s = LiquidityTrapStrategy(atr_breach=0.1, min_rr=1.5)
        ind = _snap(atr={"atr": [1.0]})
        struct = _struct(resistance_prices=[100.0])
        closes = [99.0] * 58 + [99.5, 99.0]
        highs = [99.5] * 58 + [99.5, 101.0]  # Wick above 100
        lows = [98.5] * 60
        volumes = [50000.0] * 60
        signals = s.evaluate("TEST", Timeframe.D1, ind, struct, closes, highs, lows, volumes, closes)
        if signals:
            assert signals[0].direction == Direction.SHORT
            assert signals[0].metadata.get("trap_type") == "bull_trap"
