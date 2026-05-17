"""Integration tests for IntegrationRegistry and StrategyAdapter.

Tests the complete flow of:
1. Registering strategies in the registry
2. Getting adapters from the registry
3. Using adapters to generate signals
"""

from __future__ import annotations

import pytest

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.signals.models import SignalDirection
from algoforge.signals.registry import IntegrationRegistry, create_default_registry
from algoforge.strategies.base import Strategy
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot


# Mock Strategy for testing
class TestMomentumStrategy(Strategy):
    """Mock momentum strategy for testing."""
    
    @property
    def name(self) -> str:
        return "test_momentum"
    
    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.TRENDING]
    
    def evaluate(
        self,
        symbol: str,
        timeframe: Timeframe,
        indicators: IndicatorSnapshot,
        structure: StructuralSnapshot,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[float],
        opens: list[float],
    ) -> list[Signal]:
        # Generate a simple long signal
        return [
            Signal(
                strategy="test_momentum",
                symbol=symbol,
                timeframe=timeframe,
                direction=Direction.LONG,
                confidence=0.8,
                entry_price=closes[-1],
                stop_loss=closes[-1] * 0.98,
                take_profit=closes[-1] * 1.05,
                risk_reward_ratio=2.5,
            )
        ]


class TestMeanReversionStrategy(Strategy):
    """Mock mean reversion strategy for testing."""
    
    @property
    def name(self) -> str:
        return "test_mean_reversion"
    
    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.RANGING]
    
    def evaluate(
        self,
        symbol: str,
        timeframe: Timeframe,
        indicators: IndicatorSnapshot,
        structure: StructuralSnapshot,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[float],
        opens: list[float],
    ) -> list[Signal]:
        # Generate a simple short signal
        return [
            Signal(
                strategy="test_mean_reversion",
                symbol=symbol,
                timeframe=timeframe,
                direction=Direction.SHORT,
                confidence=0.6,
                entry_price=closes[-1],
                stop_loss=closes[-1] * 1.02,
                take_profit=closes[-1] * 0.95,
                risk_reward_ratio=2.0,
            )
        ]


@pytest.mark.asyncio
class TestRegistryAdapterIntegration:
    """Test integration between registry and adapter."""
    
    async def test_register_and_get_adapters(self):
        """Test registering strategies and getting adapters."""
        registry = IntegrationRegistry()
        registry.register_strategy(TestMomentumStrategy, "momentum", weight=1.0)
        registry.register_strategy(TestMeanReversionStrategy, "mean_reversion", weight=0.8)
        
        adapters = registry.get_all_adapters()
        
        assert len(adapters) == 2
        assert any(a.family_name == "momentum" for a in adapters)
        assert any(a.family_name == "mean_reversion" for a in adapters)
    
    async def test_adapters_generate_signals(self):
        """Test that adapters from registry can generate signals."""
        registry = IntegrationRegistry()
        registry.register_strategy(TestMomentumStrategy, "momentum", weight=1.0)
        
        adapters = registry.get_all_adapters()
        adapter = adapters[0]
        
        # Create test data
        indicators = IndicatorSnapshot()
        structure = StructuralSnapshot(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            support_levels=[],
            resistance_levels=[],
            trend_direction="up",
        )
        closes = [100.0, 101.0, 102.0, 103.0, 104.0]
        highs = [101.0, 102.0, 103.0, 104.0, 105.0]
        lows = [99.0, 100.0, 101.0, 102.0, 103.0]
        volumes = [1000.0] * 5
        opens = [100.0, 101.0, 102.0, 103.0, 104.0]
        
        # Generate signal
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=indicators,
            structure=structure,
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            opens=opens,
        )
        
        assert result.family_name == "momentum"
        assert result.direction == SignalDirection.LONG
        assert result.score > 0  # Long signal should have positive score
        assert result.is_valid
        assert "strategy_name" in result.metadata
        assert result.metadata["strategy_name"] == "test_momentum"
    
    async def test_multiple_adapters_generate_different_signals(self):
        """Test that different adapters generate different signals."""
        registry = IntegrationRegistry()
        registry.register_strategy(TestMomentumStrategy, "momentum", weight=1.0)
        registry.register_strategy(TestMeanReversionStrategy, "mean_reversion", weight=0.8)
        
        adapters = registry.get_all_adapters()
        
        # Create test data
        indicators = IndicatorSnapshot()
        structure = StructuralSnapshot(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            support_levels=[],
            resistance_levels=[],
            trend_direction="up",
        )
        closes = [100.0, 101.0, 102.0, 103.0, 104.0]
        highs = [101.0, 102.0, 103.0, 104.0, 105.0]
        lows = [99.0, 100.0, 101.0, 102.0, 103.0]
        volumes = [1000.0] * 5
        opens = [100.0, 101.0, 102.0, 103.0, 104.0]
        
        # Generate signals from all adapters
        results = []
        for adapter in adapters:
            result = await adapter.generate_signal(
                symbol="AAPL",
                timeframe=Timeframe.M5,
                indicators=indicators,
                structure=structure,
                closes=closes,
                highs=highs,
                lows=lows,
                volumes=volumes,
                opens=opens,
            )
            results.append(result)
        
        # Check we got different signals
        assert len(results) == 2
        
        # One should be momentum (long), one should be mean_reversion (short)
        momentum_result = next(r for r in results if r.family_name == "momentum")
        mean_rev_result = next(r for r in results if r.family_name == "mean_reversion")
        
        assert momentum_result.direction == SignalDirection.LONG
        assert momentum_result.score > 0
        
        assert mean_rev_result.direction == SignalDirection.SHORT
        assert mean_rev_result.score < 0
    
    async def test_default_registry_adapters_work(self):
        """Test that adapters from default registry are functional."""
        registry = create_default_registry()
        adapters = registry.get_all_adapters()
        
        # Should have multiple adapters
        assert len(adapters) > 0
        
        # Pick one adapter and test it
        adapter = adapters[0]
        
        # Create test data
        indicators = IndicatorSnapshot()
        structure = StructuralSnapshot(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            support_levels=[],
            resistance_levels=[],
            trend_direction="up",
        )
        closes = [100.0, 101.0, 102.0, 103.0, 104.0]
        highs = [101.0, 102.0, 103.0, 104.0, 105.0]
        lows = [99.0, 100.0, 101.0, 102.0, 103.0]
        volumes = [1000.0] * 5
        opens = [100.0, 101.0, 102.0, 103.0, 104.0]
        
        # Generate signal - should not raise an error
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=indicators,
            structure=structure,
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            opens=opens,
        )
        
        # Basic validation
        assert result.family_name in ["momentum", "mean_reversion", "breakout", "structural", "microstructure"]
        assert -1.0 <= result.score <= 1.0
        assert result.direction in [SignalDirection.LONG, SignalDirection.SHORT, SignalDirection.NEUTRAL]
    
    async def test_registry_weights_preserved(self):
        """Test that strategy weights are preserved in registry."""
        registry = IntegrationRegistry()
        registry.register_strategy(TestMomentumStrategy, "momentum", weight=1.5)
        registry.register_strategy(TestMeanReversionStrategy, "mean_reversion", weight=0.7)
        
        momentum_weights = registry.get_family_weights("momentum")
        mean_rev_weights = registry.get_family_weights("mean_reversion")
        
        assert momentum_weights["test_momentum"] == 1.5
        assert mean_rev_weights["test_mean_reversion"] == 0.7
