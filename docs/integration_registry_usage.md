# IntegrationRegistry Usage Guide

## Overview

The `IntegrationRegistry` is a central component for managing legacy strategy integration in AlgoForge. It maintains mappings between strategy classes and their corresponding signal families, enabling seamless integration of legacy strategies into the modern signal combination framework.

## Quick Start

### Creating a Registry

```python
from algoforge.signals import IntegrationRegistry, create_default_registry

# Option 1: Create an empty registry
registry = IntegrationRegistry()

# Option 2: Use the pre-configured default registry
registry = create_default_registry()
```

### Registering Strategies

```python
from algoforge.strategies.secondary_trending_range import EMACrossover
from algoforge.signals import IntegrationRegistry

registry = IntegrationRegistry()

# Register a strategy to a signal family
registry.register_strategy(
    strategy_class=EMACrossover,
    family_name="momentum",
    weight=1.0
)
```

### Getting Adapters

```python
# Get all strategy adapters for signal generation
adapters = registry.get_all_adapters()

# Use adapters to generate signals
for adapter in adapters:
    signal_result = await adapter.generate_signal(
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
    print(f"Family: {signal_result.family_name}, Score: {signal_result.score}")
```

## Signal Families

The registry supports five signal families:

1. **momentum** - Trend-following strategies (EMA crossovers, momentum indicators)
2. **mean_reversion** - Mean reversion strategies (Bollinger bands, RSI oversold/overbought)
3. **breakout** - Breakout strategies (S/R breakouts, range expansions)
4. **structural** - Structural strategies (trendline pullbacks, S/R bounces)
5. **microstructure** - Microstructure strategies (order flow, bid-ask spread)

## Registry Methods

### Core Methods

#### `register_strategy(strategy_class, family_name, weight=1.0)`
Register a strategy class to a signal family.

**Parameters:**
- `strategy_class`: The Strategy class (not an instance)
- `family_name`: One of: momentum, mean_reversion, breakout, structural, microstructure
- `weight`: Strategy weight in combination engine (default: 1.0)

**Example:**
```python
registry.register_strategy(EMACrossover, "momentum", weight=1.2)
```

#### `get_strategies_for_family(family_name)`
Get all strategy instances for a specific family.

**Returns:** List of Strategy instances

**Example:**
```python
momentum_strategies = registry.get_strategies_for_family("momentum")
print(f"Found {len(momentum_strategies)} momentum strategies")
```

#### `get_all_adapters()`
Get all strategy adapters for signal generation.

**Returns:** List of StrategyAdapter instances

**Example:**
```python
adapters = registry.get_all_adapters()
for adapter in adapters:
    print(f"{adapter.strategy.name} -> {adapter.family_name}")
```

### Utility Methods

#### `get_family_weights(family_name)`
Get strategy weights for a specific family.

**Returns:** Dictionary mapping strategy names to weights

**Example:**
```python
weights = registry.get_family_weights("momentum")
# {'ema_crossover': 1.0, 'dual_momentum': 1.2}
```

#### `get_all_families()`
Get list of all signal family names.

**Returns:** List of family names

**Example:**
```python
families = registry.get_all_families()
# ['momentum', 'mean_reversion', 'breakout', 'structural', 'microstructure']
```

#### `get_registry_summary()`
Get summary of registered strategies per family.

**Returns:** Dictionary mapping family names to strategy counts

**Example:**
```python
summary = registry.get_registry_summary()
# {'momentum': 2, 'mean_reversion': 1, 'breakout': 2, 'structural': 3, 'microstructure': 0}
```

#### `clear_family(family_name)`
Clear all strategies from a specific family.

**Example:**
```python
registry.clear_family("momentum")
```

#### `clear_all()`
Clear all registered strategies from all families.

**Example:**
```python
registry.clear_all()
```

## Default Registry

The `create_default_registry()` function creates a pre-configured registry with all currently implemented strategies:

### Currently Registered Strategies (7 of 31 planned)

**Momentum Family (1 strategy):**
- EMACrossover (weight: 1.0)

**Mean Reversion Family (1 strategy):**
- MeanReversion (weight: 1.0)

**Breakout Family (2 strategies):**
- BreakoutStrategy (weight: 1.0)
- LiquidityTrapStrategy (weight: 0.7)

**Structural Family (3 strategies):**
- TrendlinePullback (weight: 1.2)
- ReversalStrategy (weight: 1.0)
- EMABounce (weight: 0.9)

**Microstructure Family (0 strategies):**
- (To be implemented)

## Advanced Usage

### Custom Strategy Registration

```python
from algoforge.strategies.base import Strategy
from algoforge.signals import IntegrationRegistry

class MyCustomStrategy(Strategy):
    @property
    def name(self) -> str:
        return "my_custom_strategy"
    
    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.TRENDING]
    
    def evaluate(self, symbol, timeframe, indicators, structure, 
                 closes, highs, lows, volumes, opens):
        # Your strategy logic here
        return []

# Register your custom strategy
registry = IntegrationRegistry()
registry.register_strategy(MyCustomStrategy, "momentum", weight=1.5)
```

### Updating Strategy Weights

```python
# Registering the same strategy twice updates its weight
registry.register_strategy(EMACrossover, "momentum", weight=1.0)
registry.register_strategy(EMACrossover, "momentum", weight=1.5)  # Updates to 1.5

# Verify the update
weights = registry.get_family_weights("momentum")
assert weights["ema_crossover"] == 1.5
```

### Iterating Over All Strategies

```python
registry = create_default_registry()

for family in registry.get_all_families():
    strategies = registry.get_strategies_for_family(family)
    if strategies:
        print(f"\n{family.upper()} Family:")
        for strategy in strategies:
            print(f"  - {strategy.name}")
```

## Integration with Orchestrator

The registry is designed to integrate with the AlgoForge orchestrator:

```python
from algoforge.signals import create_default_registry

# In your orchestrator initialization
registry = create_default_registry()
adapters = registry.get_all_adapters()

# Store adapters for signal generation
self.strategy_adapters = adapters

# During signal generation loop
for adapter in self.strategy_adapters:
    signal_result = await adapter.generate_signal(
        symbol=symbol,
        timeframe=timeframe,
        indicators=indicators,
        structure=structure,
        closes=closes,
        highs=highs,
        lows=lows,
        volumes=volumes,
        opens=opens,
    )
    
    # Feed signal_result to combination engine
    self.combination_engine.add_signal(signal_result)
```

## Error Handling

The registry validates inputs and raises clear errors:

```python
# Invalid family name
try:
    registry.register_strategy(EMACrossover, "invalid_family")
except ValueError as e:
    print(e)  # "Invalid family_name 'invalid_family'. Must be one of: ..."

# Invalid weight
try:
    registry.register_strategy(EMACrossover, "momentum", weight=-1.0)
except ValueError as e:
    print(e)  # "Weight must be positive, got -1.0"

# Getting strategies from invalid family
try:
    strategies = registry.get_strategies_for_family("invalid_family")
except ValueError as e:
    print(e)  # "Invalid family_name 'invalid_family'. Must be one of: ..."
```

## Best Practices

1. **Use the default registry** for standard deployments:
   ```python
   registry = create_default_registry()
   ```

2. **Create custom registries** for testing or specialized configurations:
   ```python
   test_registry = IntegrationRegistry()
   test_registry.register_strategy(MockStrategy, "momentum")
   ```

3. **Set appropriate weights** based on strategy performance:
   - High-performing strategies: weight > 1.0
   - Average strategies: weight = 1.0
   - Experimental strategies: weight < 1.0

4. **Clear registries** in tests to avoid state leakage:
   ```python
   def teardown():
       registry.clear_all()
   ```

5. **Monitor registry summary** to track strategy distribution:
   ```python
   summary = registry.get_registry_summary()
   total = sum(summary.values())
   print(f"Total strategies: {total}")
   ```

## Future Enhancements

As additional strategies are implemented, they should be added to the `create_default_registry()` function:

```python
# Planned additions (24 more strategies to reach 31 total):
# - Momentum: DualMomentum, RSI_Divergence, MACD_Crossover, etc.
# - Mean Reversion: PairsTrading, BollingerReversion, RSI_Oversold, etc.
# - Breakout: VolumeBreakout, RangeExpansion, etc.
# - Structural: FibonacciRetracement, PivotPoints, etc.
# - Microstructure: OrderFlowImbalance, BidAskSpread, etc.
```

## See Also

- [StrategyAdapter Documentation](./strategy_adapter_usage.md)
- [Signal Combination Engine](./combination_engine.md)
- [Strategy Development Guide](./strategy_development.md)
