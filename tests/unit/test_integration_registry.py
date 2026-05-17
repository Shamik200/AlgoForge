"""Unit tests for the IntegrationRegistry class.

Tests cover:
- Registry initialization
- Strategy registration
- Retrieving strategies by family
- Getting all adapters
- Weight management
- Error handling for invalid inputs
- Registry summary and utility methods
"""

from __future__ import annotations

import pytest

from algoforge.core.constants import MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.signals.adapter import StrategyAdapter
from algoforge.signals.registry import IntegrationRegistry, create_default_registry
from algoforge.strategies.base import Strategy
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot


# Mock Strategy for testing
class MockStrategy(Strategy):
    """Mock strategy for testing."""
    
    def __init__(self, name: str = "mock_strategy") -> None:
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name
    
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
        return []


class AnotherMockStrategy(Strategy):
    """Another mock strategy for testing multiple registrations."""
    
    @property
    def name(self) -> str:
        return "another_mock_strategy"
    
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
        return []


class TestIntegrationRegistryInitialization:
    """Test IntegrationRegistry initialization."""
    
    def test_init_creates_empty_registry(self):
        """Test that initialization creates an empty registry with all families."""
        registry = IntegrationRegistry()
        
        # Check all families exist
        families = registry.get_all_families()
        assert "momentum" in families
        assert "mean_reversion" in families
        assert "breakout" in families
        assert "structural" in families
        assert "microstructure" in families
        
        # Check all families are empty
        summary = registry.get_registry_summary()
        assert all(count == 0 for count in summary.values())
    
    def test_repr(self):
        """Test string representation of registry."""
        registry = IntegrationRegistry()
        repr_str = repr(registry)
        
        assert "IntegrationRegistry" in repr_str
        assert "0 strategies" in repr_str


class TestStrategyRegistration:
    """Test strategy registration functionality."""
    
    def test_register_strategy_to_momentum(self):
        """Test registering a strategy to momentum family."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        
        strategies = registry.get_strategies_for_family("momentum")
        assert len(strategies) == 1
        assert isinstance(strategies[0], MockStrategy)
    
    def test_register_strategy_to_mean_reversion(self):
        """Test registering a strategy to mean_reversion family."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "mean_reversion", weight=1.0)
        
        strategies = registry.get_strategies_for_family("mean_reversion")
        assert len(strategies) == 1
        assert isinstance(strategies[0], MockStrategy)
    
    def test_register_strategy_to_breakout(self):
        """Test registering a strategy to breakout family."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "breakout", weight=1.0)
        
        strategies = registry.get_strategies_for_family("breakout")
        assert len(strategies) == 1
        assert isinstance(strategies[0], MockStrategy)
    
    def test_register_strategy_to_structural(self):
        """Test registering a strategy to structural family."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "structural", weight=1.0)
        
        strategies = registry.get_strategies_for_family("structural")
        assert len(strategies) == 1
        assert isinstance(strategies[0], MockStrategy)
    
    def test_register_strategy_to_microstructure(self):
        """Test registering a strategy to microstructure family."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "microstructure", weight=1.0)
        
        strategies = registry.get_strategies_for_family("microstructure")
        assert len(strategies) == 1
        assert isinstance(strategies[0], MockStrategy)
    
    def test_register_multiple_strategies_to_same_family(self):
        """Test registering multiple strategies to the same family."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "momentum", weight=0.8)
        
        strategies = registry.get_strategies_for_family("momentum")
        assert len(strategies) == 2
        assert any(isinstance(s, MockStrategy) for s in strategies)
        assert any(isinstance(s, AnotherMockStrategy) for s in strategies)
    
    def test_register_same_strategy_twice_updates_weight(self):
        """Test that registering the same strategy twice updates its weight."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(MockStrategy, "momentum", weight=1.5)
        
        weights = registry.get_family_weights("momentum")
        assert weights["mock_strategy"] == 1.5
        
        # Should still only have one strategy
        strategies = registry.get_strategies_for_family("momentum")
        assert len(strategies) == 1
    
    def test_register_strategy_with_custom_weight(self):
        """Test registering a strategy with a custom weight."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.5)
        
        weights = registry.get_family_weights("momentum")
        assert weights["mock_strategy"] == 1.5
    
    def test_register_strategy_invalid_family_raises_error(self):
        """Test that registering to an invalid family raises ValueError."""
        registry = IntegrationRegistry()
        
        with pytest.raises(ValueError, match="Invalid family_name"):
            registry.register_strategy(MockStrategy, "invalid_family", weight=1.0)
    
    def test_register_strategy_negative_weight_raises_error(self):
        """Test that registering with negative weight raises ValueError."""
        registry = IntegrationRegistry()
        
        with pytest.raises(ValueError, match="Weight must be positive"):
            registry.register_strategy(MockStrategy, "momentum", weight=-1.0)
    
    def test_register_strategy_zero_weight_raises_error(self):
        """Test that registering with zero weight raises ValueError."""
        registry = IntegrationRegistry()
        
        with pytest.raises(ValueError, match="Weight must be positive"):
            registry.register_strategy(MockStrategy, "momentum", weight=0.0)


class TestGetStrategiesForFamily:
    """Test retrieving strategies by family."""
    
    def test_get_strategies_for_empty_family(self):
        """Test getting strategies from an empty family returns empty list."""
        registry = IntegrationRegistry()
        strategies = registry.get_strategies_for_family("momentum")
        assert strategies == []
    
    def test_get_strategies_for_family_with_one_strategy(self):
        """Test getting strategies from a family with one strategy."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        
        strategies = registry.get_strategies_for_family("momentum")
        assert len(strategies) == 1
        assert isinstance(strategies[0], MockStrategy)
    
    def test_get_strategies_for_family_with_multiple_strategies(self):
        """Test getting strategies from a family with multiple strategies."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "momentum", weight=0.8)
        
        strategies = registry.get_strategies_for_family("momentum")
        assert len(strategies) == 2
    
    def test_get_strategies_returns_same_instances(self):
        """Test that getting strategies multiple times returns the same instances."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        
        strategies1 = registry.get_strategies_for_family("momentum")
        strategies2 = registry.get_strategies_for_family("momentum")
        
        # Should be the same instance (cached)
        assert strategies1[0] is strategies2[0]
    
    def test_get_strategies_invalid_family_raises_error(self):
        """Test that getting strategies from invalid family raises ValueError."""
        registry = IntegrationRegistry()
        
        with pytest.raises(ValueError, match="Invalid family_name"):
            registry.get_strategies_for_family("invalid_family")


class TestGetAllAdapters:
    """Test getting all strategy adapters."""
    
    def test_get_all_adapters_empty_registry(self):
        """Test getting adapters from empty registry returns empty list."""
        registry = IntegrationRegistry()
        adapters = registry.get_all_adapters()
        assert adapters == []
    
    def test_get_all_adapters_single_strategy(self):
        """Test getting adapters with one registered strategy."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        
        adapters = registry.get_all_adapters()
        assert len(adapters) == 1
        assert isinstance(adapters[0], StrategyAdapter)
        assert adapters[0].family_name == "momentum"
        assert isinstance(adapters[0].strategy, MockStrategy)
    
    def test_get_all_adapters_multiple_strategies_same_family(self):
        """Test getting adapters with multiple strategies in same family."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "momentum", weight=0.8)
        
        adapters = registry.get_all_adapters()
        assert len(adapters) == 2
        assert all(isinstance(a, StrategyAdapter) for a in adapters)
        assert all(a.family_name == "momentum" for a in adapters)
    
    def test_get_all_adapters_multiple_strategies_different_families(self):
        """Test getting adapters with strategies in different families."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "mean_reversion", weight=0.8)
        
        adapters = registry.get_all_adapters()
        assert len(adapters) == 2
        
        families = {a.family_name for a in adapters}
        assert "momentum" in families
        assert "mean_reversion" in families
    
    def test_get_all_adapters_returns_correct_family_names(self):
        """Test that adapters have correct family names."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "breakout", weight=1.0)
        
        adapters = registry.get_all_adapters()
        
        momentum_adapters = [a for a in adapters if a.family_name == "momentum"]
        breakout_adapters = [a for a in adapters if a.family_name == "breakout"]
        
        assert len(momentum_adapters) == 1
        assert len(breakout_adapters) == 1


class TestWeightManagement:
    """Test weight management functionality."""
    
    def test_get_family_weights_empty_family(self):
        """Test getting weights from empty family returns empty dict."""
        registry = IntegrationRegistry()
        weights = registry.get_family_weights("momentum")
        assert weights == {}
    
    def test_get_family_weights_single_strategy(self):
        """Test getting weights with one strategy."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.5)
        
        weights = registry.get_family_weights("momentum")
        assert "mock_strategy" in weights
        assert weights["mock_strategy"] == 1.5
    
    def test_get_family_weights_multiple_strategies(self):
        """Test getting weights with multiple strategies."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "momentum", weight=0.8)
        
        weights = registry.get_family_weights("momentum")
        assert len(weights) == 2
        assert weights["mock_strategy"] == 1.0
        assert weights["another_mock_strategy"] == 0.8
    
    def test_get_family_weights_invalid_family_raises_error(self):
        """Test that getting weights from invalid family raises ValueError."""
        registry = IntegrationRegistry()
        
        with pytest.raises(ValueError, match="Invalid family_name"):
            registry.get_family_weights("invalid_family")


class TestRegistrySummary:
    """Test registry summary and utility methods."""
    
    def test_get_all_families(self):
        """Test getting all family names."""
        registry = IntegrationRegistry()
        families = registry.get_all_families()
        
        assert len(families) == 5
        assert "momentum" in families
        assert "mean_reversion" in families
        assert "breakout" in families
        assert "structural" in families
        assert "microstructure" in families
    
    def test_get_registry_summary_empty(self):
        """Test getting summary of empty registry."""
        registry = IntegrationRegistry()
        summary = registry.get_registry_summary()
        
        assert summary["momentum"] == 0
        assert summary["mean_reversion"] == 0
        assert summary["breakout"] == 0
        assert summary["structural"] == 0
        assert summary["microstructure"] == 0
    
    def test_get_registry_summary_with_strategies(self):
        """Test getting summary with registered strategies."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "momentum", weight=0.8)
        registry.register_strategy(MockStrategy, "breakout", weight=1.0)
        
        summary = registry.get_registry_summary()
        assert summary["momentum"] == 2
        assert summary["breakout"] == 1
        assert summary["mean_reversion"] == 0
    
    def test_repr_with_strategies(self):
        """Test string representation with registered strategies."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "breakout", weight=1.0)
        
        repr_str = repr(registry)
        assert "IntegrationRegistry" in repr_str
        assert "2 strategies" in repr_str


class TestClearMethods:
    """Test clearing strategies from registry."""
    
    def test_clear_family(self):
        """Test clearing a specific family."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "breakout", weight=1.0)
        
        registry.clear_family("momentum")
        
        assert len(registry.get_strategies_for_family("momentum")) == 0
        assert len(registry.get_strategies_for_family("breakout")) == 1
    
    def test_clear_family_invalid_family_raises_error(self):
        """Test that clearing invalid family raises ValueError."""
        registry = IntegrationRegistry()
        
        with pytest.raises(ValueError, match="Invalid family_name"):
            registry.clear_family("invalid_family")
    
    def test_clear_all(self):
        """Test clearing all families."""
        registry = IntegrationRegistry()
        registry.register_strategy(MockStrategy, "momentum", weight=1.0)
        registry.register_strategy(AnotherMockStrategy, "breakout", weight=1.0)
        
        registry.clear_all()
        
        summary = registry.get_registry_summary()
        assert all(count == 0 for count in summary.values())
        assert len(registry.get_all_adapters()) == 0


class TestCreateDefaultRegistry:
    """Test the create_default_registry factory function."""
    
    def test_create_default_registry_returns_registry(self):
        """Test that create_default_registry returns an IntegrationRegistry."""
        registry = create_default_registry()
        assert isinstance(registry, IntegrationRegistry)
    
    def test_create_default_registry_has_strategies(self):
        """Test that default registry has strategies registered."""
        registry = create_default_registry()
        summary = registry.get_registry_summary()
        
        # Should have at least some strategies registered
        total_strategies = sum(summary.values())
        assert total_strategies > 0
    
    def test_create_default_registry_has_momentum_strategies(self):
        """Test that default registry has momentum strategies."""
        registry = create_default_registry()
        strategies = registry.get_strategies_for_family("momentum")
        assert len(strategies) > 0
    
    def test_create_default_registry_has_mean_reversion_strategies(self):
        """Test that default registry has mean reversion strategies."""
        registry = create_default_registry()
        strategies = registry.get_strategies_for_family("mean_reversion")
        assert len(strategies) > 0
    
    def test_create_default_registry_has_breakout_strategies(self):
        """Test that default registry has breakout strategies."""
        registry = create_default_registry()
        strategies = registry.get_strategies_for_family("breakout")
        assert len(strategies) > 0
    
    def test_create_default_registry_has_structural_strategies(self):
        """Test that default registry has structural strategies."""
        registry = create_default_registry()
        strategies = registry.get_strategies_for_family("structural")
        assert len(strategies) > 0
    
    def test_create_default_registry_adapters_work(self):
        """Test that adapters from default registry are functional."""
        registry = create_default_registry()
        adapters = registry.get_all_adapters()
        
        # Should have multiple adapters
        assert len(adapters) > 0
        
        # All should be StrategyAdapter instances
        assert all(isinstance(a, StrategyAdapter) for a in adapters)
        
        # All should have valid family names
        valid_families = {"momentum", "mean_reversion", "breakout", "structural", "microstructure"}
        assert all(a.family_name in valid_families for a in adapters)
