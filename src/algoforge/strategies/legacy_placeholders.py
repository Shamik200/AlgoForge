"""Placeholder legacy strategies to complete IntegrationRegistry registrations.

These lightweight stubs implement the `Strategy` interface and return no signals.
They allow the registry to reference all planned legacy strategies without changing
core logic. Real implementations can replace these stubs later.
"""

from __future__ import annotations

from typing import List

from algoforge.core.constants import MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.strategies.base import Strategy
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot


class _StubStrategy(Strategy):
    def __init__(self, name: str, regimes: List[MarketRegime] | None = None):
        self._name = name
        self._req = regimes or []

    @property
    def name(self) -> str:
        return self._name

    @property
    def required_regime(self) -> list[MarketRegime]:
        return self._req

    def evaluate(
        self, symbol: str, timeframe: Timeframe,
        indicators: IndicatorSnapshot, structure: StructuralSnapshot,
        closes: list[float], highs: list[float], lows: list[float],
        volumes: list[float], opens: list[float],
    ) -> list[Signal]:
        # Placeholder: no signals generated
        return []


# Momentum family placeholders
DualMomentum = lambda: _StubStrategy("dual_momentum", [MarketRegime.TRENDING])
RSI_Divergence = lambda: _StubStrategy("rsi_divergence", [MarketRegime.RANGE, MarketRegime.TRENDING])
MACD_Crossover = lambda: _StubStrategy("macd_crossover", [MarketRegime.TRENDING])
MomentumBreakout = lambda: _StubStrategy("momentum_breakout", [MarketRegime.TRENDING])

# Mean reversion placeholders
PairsTrading = lambda: _StubStrategy("pairs_trading", [MarketRegime.RANGE])
BollingerReversion = lambda: _StubStrategy("bollinger_reversion", [MarketRegime.RANGE])
RSI_Oversold = lambda: _StubStrategy("rsi_oversold", [MarketRegime.RANGE])

# Breakout placeholders
VolumeBreakout = lambda: _StubStrategy("volume_breakout", [MarketRegime.TRENDING])
RangeExpansion = lambda: _StubStrategy("range_expansion", [MarketRegime.TRENDING])
LiquiditySurge = lambda: _StubStrategy("liquidity_surge", [MarketRegime.TRENDING])

# Structural placeholders
FibonacciRetracement = lambda: _StubStrategy("fibonacci_retracement", [MarketRegime.TRENDING, MarketRegime.RANGE])
PivotPoints = lambda: _StubStrategy("pivot_points", [MarketRegime.RANGE])
VWAPPullback = lambda: _StubStrategy("vwap_pullback", [MarketRegime.TRENDING])

# Microstructure placeholders
OrderFlowImbalance = lambda: _StubStrategy("orderflow_imbalance", [MarketRegime.TRENDING])
BidAskSpread = lambda: _StubStrategy("bidask_spread", [MarketRegime.TRENDING])
IcebergDetector = lambda: _StubStrategy("iceberg_detector", [MarketRegime.TRENDING])

# Additional placeholders to reach planned count
MomentumNovice = lambda: _StubStrategy("momentum_novice", [MarketRegime.TRENDING])
MeanRevNovice = lambda: _StubStrategy("meanrev_novice", [MarketRegime.RANGE])
BreakoutNovice = lambda: _StubStrategy("breakout_novice", [MarketRegime.TRENDING])
StructuralNovice = lambda: _StubStrategy("structural_novice", [MarketRegime.RANGE])
MicroNovice = lambda: _StubStrategy("micro_novice", [MarketRegime.TRENDING])
