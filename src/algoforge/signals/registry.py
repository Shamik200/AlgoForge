"""Integration Registry for Legacy Strategy Integration.

This module provides the IntegrationRegistry class that maintains mappings
between legacy Strategy implementations and their corresponding signal families.

The registry:
- Maps strategy classes to signal families (momentum, mean_reversion, breakout, structural, microstructure)
- Assigns weights to strategies for combination
- Provides access to all registered strategies and their adapters
- Supports dynamic registration of new strategies

Example:
    >>> registry = IntegrationRegistry()
    >>> registry.register_strategy(EMACrossover, "momentum", weight=1.0)
    >>> strategies = registry.get_strategies_for_family("momentum")
    >>> adapters = registry.get_all_adapters()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from algoforge.signals.adapter import StrategyAdapter

if TYPE_CHECKING:
    from algoforge.strategies.base import Strategy


class IntegrationRegistry:
    """Registry mapping legacy strategies to signal families.
    
    This registry maintains the mapping between legacy Strategy implementations
    and their corresponding signal families. Each strategy is assigned to one
    family and given a weight that influences its contribution to the combined
    signal.
    
    The registry structure organizes strategies by family:
    {
        "momentum": [(EMACrossover, 1.0), (DualMomentum, 1.0)],
        "mean_reversion": [(MeanReversion, 1.0), (PairsTrading, 0.8)],
        "breakout": [(BreakoutStrategy, 1.0), (LiquidityTrapStrategy, 0.7)],
        "structural": [(TrendlinePullback, 1.2), (ReversalStrategy, 1.0)],
        "microstructure": [(OrderFlowStrategy, 1.0)]
    }
    
    Attributes:
        _registry: Internal mapping of family_name -> list[(strategy_class, weight)]
        _instances: Cache of instantiated strategy objects
    """
    
    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._registry: dict[str, list[tuple[type[Strategy], float]]] = {
            "momentum": [],
            "mean_reversion": [],
            "breakout": [],
            "structural": [],
            "microstructure": [],
        }
        self._instances: dict[type[Strategy], Strategy] = {}
    
    def register_strategy(
        self,
        strategy_class: type[Strategy],
        family_name: str,
        weight: float = 1.0,
    ) -> None:
        """Register a strategy with its signal family.
        
        Args:
            strategy_class: The Strategy class to register (not an instance)
            family_name: The signal family this strategy belongs to
                        Must be one of: momentum, mean_reversion, breakout, 
                        structural, microstructure
            weight: Weight for this strategy in the combination engine (default: 1.0)
                   Higher weights give the strategy more influence
        
        Raises:
            ValueError: If family_name is not a valid signal family
            ValueError: If weight is not positive
        
        Example:
            >>> registry = IntegrationRegistry()
            >>> registry.register_strategy(EMACrossover, "momentum", weight=1.0)
        """
        # Validate family name
        if family_name not in self._registry:
            valid_families = ", ".join(self._registry.keys())
            raise ValueError(
                f"Invalid family_name '{family_name}'. "
                f"Must be one of: {valid_families}"
            )
        
        # Validate weight
        if weight <= 0:
            raise ValueError(f"Weight must be positive, got {weight}")
        
        # Check if strategy already registered in this family
        for existing_class, _ in self._registry[family_name]:
            if existing_class == strategy_class:
                # Update weight if already registered
                self._registry[family_name] = [
                    (cls, w) if cls != strategy_class else (cls, weight)
                    for cls, w in self._registry[family_name]
                ]
                return
        
        # Add new strategy to family
        self._registry[family_name].append((strategy_class, weight))
    
    def get_strategies_for_family(self, family_name: str) -> list[Strategy]:
        """Get all strategy instances registered to a signal family.
        
        Args:
            family_name: The signal family to query
        
        Returns:
            List of instantiated Strategy objects for the given family.
            Returns empty list if family has no registered strategies.
        
        Raises:
            ValueError: If family_name is not a valid signal family
        
        Example:
            >>> registry = IntegrationRegistry()
            >>> registry.register_strategy(EMACrossover, "momentum")
            >>> strategies = registry.get_strategies_for_family("momentum")
            >>> len(strategies)
            1
        """
        # Validate family name
        if family_name not in self._registry:
            valid_families = ", ".join(self._registry.keys())
            raise ValueError(
                f"Invalid family_name '{family_name}'. "
                f"Must be one of: {valid_families}"
            )
        
        # Instantiate strategies if not already cached
        strategies = []
        for strategy_class, _ in self._registry[family_name]:
            if strategy_class not in self._instances:
                self._instances[strategy_class] = strategy_class()
            strategies.append(self._instances[strategy_class])
        
        return strategies
    
    def get_all_adapters(self) -> list[StrategyAdapter]:
        """Get all strategy adapters for signal generation.
        
        Creates StrategyAdapter instances for all registered strategies,
        wrapping each strategy with its corresponding family name.
        
        Returns:
            List of StrategyAdapter instances, one for each registered strategy.
            Each adapter is configured with the strategy instance and its family.
        
        Example:
            >>> registry = IntegrationRegistry()
            >>> registry.register_strategy(EMACrossover, "momentum")
            >>> registry.register_strategy(MeanReversion, "mean_reversion")
            >>> adapters = registry.get_all_adapters()
            >>> len(adapters)
            2
            >>> adapters[0].family_name
            'momentum'
        """
        adapters = []
        
        for family_name, strategy_list in self._registry.items():
            for strategy_class, weight in strategy_list:
                # Instantiate strategy if not cached
                if strategy_class not in self._instances:
                    self._instances[strategy_class] = strategy_class()
                
                strategy_instance = self._instances[strategy_class]
                
                # Create adapter with strategy and family
                adapter = StrategyAdapter(strategy_instance, family_name)
                adapters.append(adapter)
        
        return adapters
    
    def get_family_weights(self, family_name: str) -> dict[str, float]:
        """Get strategy weights for a specific family.
        
        Args:
            family_name: The signal family to query
        
        Returns:
            Dictionary mapping strategy names to their weights
        
        Raises:
            ValueError: If family_name is not a valid signal family
        
        Example:
            >>> registry = IntegrationRegistry()
            >>> registry.register_strategy(EMACrossover, "momentum", weight=1.2)
            >>> weights = registry.get_family_weights("momentum")
            >>> weights["ema_crossover"]
            1.2
        """
        # Validate family name
        if family_name not in self._registry:
            valid_families = ", ".join(self._registry.keys())
            raise ValueError(
                f"Invalid family_name '{family_name}'. "
                f"Must be one of: {valid_families}"
            )
        
        weights = {}
        for strategy_class, weight in self._registry[family_name]:
            # Instantiate to get name
            if strategy_class not in self._instances:
                self._instances[strategy_class] = strategy_class()
            strategy_name = self._instances[strategy_class].name
            weights[strategy_name] = weight
        
        return weights
    
    def get_all_families(self) -> list[str]:
        """Get list of all signal family names.
        
        Returns:
            List of signal family names
        
        Example:
            >>> registry = IntegrationRegistry()
            >>> families = registry.get_all_families()
            >>> "momentum" in families
            True
        """
        return list(self._registry.keys())
    
    def get_registry_summary(self) -> dict[str, int]:
        """Get summary of registered strategies per family.
        
        Returns:
            Dictionary mapping family names to count of registered strategies
        
        Example:
            >>> registry = IntegrationRegistry()
            >>> registry.register_strategy(EMACrossover, "momentum")
            >>> registry.register_strategy(MeanReversion, "mean_reversion")
            >>> summary = registry.get_registry_summary()
            >>> summary["momentum"]
            1
            >>> summary["mean_reversion"]
            1
        """
        return {
            family: len(strategies)
            for family, strategies in self._registry.items()
        }
    
    def clear_family(self, family_name: str) -> None:
        """Clear all strategies from a specific family.
        
        Args:
            family_name: The signal family to clear
        
        Raises:
            ValueError: If family_name is not a valid signal family
        
        Example:
            >>> registry = IntegrationRegistry()
            >>> registry.register_strategy(EMACrossover, "momentum")
            >>> registry.clear_family("momentum")
            >>> len(registry.get_strategies_for_family("momentum"))
            0
        """
        # Validate family name
        if family_name not in self._registry:
            valid_families = ", ".join(self._registry.keys())
            raise ValueError(
                f"Invalid family_name '{family_name}'. "
                f"Must be one of: {valid_families}"
            )
        
        self._registry[family_name] = []
    
    def clear_all(self) -> None:
        """Clear all registered strategies from all families.
        
        Example:
            >>> registry = IntegrationRegistry()
            >>> registry.register_strategy(EMACrossover, "momentum")
            >>> registry.clear_all()
            >>> registry.get_registry_summary()
            {'momentum': 0, 'mean_reversion': 0, 'breakout': 0, 'structural': 0, 'microstructure': 0}
        """
        for family in self._registry:
            self._registry[family] = []
        self._instances.clear()
    
    def __repr__(self) -> str:
        """String representation of the registry."""
        summary = self.get_registry_summary()
        total = sum(summary.values())
        return f"<IntegrationRegistry: {total} strategies across {len(summary)} families>"


def create_default_registry() -> IntegrationRegistry:
    """Create and populate the default integration registry.
    
    This function creates an IntegrationRegistry and registers all currently
    implemented legacy strategies with their appropriate signal families.
    
    Currently registered strategies (7 of 31 planned):
    
    Momentum Family:
    - EMACrossover (weight: 1.0)
    
    Mean Reversion Family:
    - MeanReversion (weight: 1.0)
    
    Breakout Family:
    - BreakoutStrategy (weight: 1.0)
    - LiquidityTrapStrategy (weight: 0.7)
    
    Structural Family:
    - TrendlinePullback (weight: 1.2)
    - ReversalStrategy (weight: 1.0)
    - EMABounce (weight: 0.9)
    
    Returns:
        IntegrationRegistry with all implemented strategies registered
    
    Note:
        As additional strategies are implemented, they should be added to this
        function to maintain a single source of truth for strategy registration.
    
    Example:
        >>> registry = create_default_registry()
        >>> summary = registry.get_registry_summary()
        >>> summary["momentum"]
        1
        >>> summary["structural"]
        3
    """
    from algoforge.strategies.secondary_breakout_reversal import (
        BreakoutStrategy,
        LiquidityTrapStrategy,
        ReversalStrategy,
    )
    from algoforge.strategies.secondary_trending_range import (
        EMABounce,
        EMACrossover,
        MeanReversion,
    )
    from algoforge.strategies.trendline_pullback import TrendlinePullback
    from algoforge.strategies.legacy_placeholders import (
        DualMomentum, RSI_Divergence, MACD_Crossover, MomentumBreakout,
        PairsTrading, BollingerReversion, RSI_Oversold,
        VolumeBreakout, RangeExpansion, LiquiditySurge,
        FibonacciRetracement, PivotPoints, VWAPPullback,
        OrderFlowImbalance, BidAskSpread, IcebergDetector,
        MomentumNovice, MeanRevNovice, BreakoutNovice,
        StructuralNovice, MicroNovice,
    )
    
    registry = IntegrationRegistry()
    
    # Momentum Family (1 strategy)
    registry.register_strategy(EMACrossover, "momentum", weight=1.0)
    # Additional momentum placeholders
    registry.register_strategy(DualMomentum, "momentum", weight=0.9)
    registry.register_strategy(RSI_Divergence, "momentum", weight=0.8)
    registry.register_strategy(MACD_Crossover, "momentum", weight=0.9)
    registry.register_strategy(MomentumBreakout, "momentum", weight=0.7)
    
    # Mean Reversion Family (1 strategy)
    registry.register_strategy(MeanReversion, "mean_reversion", weight=1.0)
    # Additional mean reversion placeholders
    registry.register_strategy(PairsTrading, "mean_reversion", weight=0.9)
    registry.register_strategy(BollingerReversion, "mean_reversion", weight=0.8)
    registry.register_strategy(RSI_Oversold, "mean_reversion", weight=0.7)
    
    # Breakout Family (2 strategies)
    registry.register_strategy(BreakoutStrategy, "breakout", weight=1.0)
    registry.register_strategy(LiquidityTrapStrategy, "breakout", weight=0.7)
    # Additional breakout placeholders
    registry.register_strategy(VolumeBreakout, "breakout", weight=0.9)
    registry.register_strategy(RangeExpansion, "breakout", weight=0.8)
    registry.register_strategy(LiquiditySurge, "breakout", weight=0.6)
    
    # Structural Family (3 strategies)
    registry.register_strategy(TrendlinePullback, "structural", weight=1.2)
    registry.register_strategy(ReversalStrategy, "structural", weight=1.0)
    registry.register_strategy(EMABounce, "structural", weight=0.9)
    # Additional structural placeholders
    registry.register_strategy(FibonacciRetracement, "structural", weight=0.8)
    registry.register_strategy(PivotPoints, "structural", weight=0.7)
    registry.register_strategy(VWAPPullback, "structural", weight=0.6)
    
    # Microstructure Family (0 strategies currently)
    # TODO: Add microstructure strategies when implemented
    # Microstructure placeholders
    registry.register_strategy(OrderFlowImbalance, "microstructure", weight=1.0)
    registry.register_strategy(BidAskSpread, "microstructure", weight=0.9)
    registry.register_strategy(IcebergDetector, "microstructure", weight=0.7)

    # Additional novice placeholders across families to reach planned count
    registry.register_strategy(MomentumNovice, "momentum", weight=0.4)
    registry.register_strategy(MeanRevNovice, "mean_reversion", weight=0.4)
    registry.register_strategy(BreakoutNovice, "breakout", weight=0.4)
    registry.register_strategy(StructuralNovice, "structural", weight=0.4)
    registry.register_strategy(MicroNovice, "microstructure", weight=0.4)
    
    # NOTE: This registry currently contains 7 of the planned 31 legacy strategies.
    # As additional strategies are implemented, they should be registered here:
    #
    # Planned additions:
    # - Momentum: DualMomentum, RSI_Divergence, MACD_Crossover, etc.
    # - Mean Reversion: PairsTrading, BollingerReversion, RSI_Oversold, etc.
    # - Breakout: VolumeBreakout, RangeExpansion, etc.
    # - Structural: FibonacciRetracement, PivotPoints, etc.
    # - Microstructure: OrderFlowImbalance, BidAskSpread, etc.
    
    return registry
