"""Demonstration of RL Agent integration in AlgoForge.

This script demonstrates how the RL Threshold Adjuster learns from trade
outcomes and dynamically adjusts system thresholds to improve performance.

Features demonstrated:
1. RL Agent initialization with custom configuration
2. Recording trade outcomes for learning
3. Applying threshold adjustments based on performance
4. Exploration vs exploitation (10%/90%)
5. Reversion to baseline after poor performance
6. Comprehensive logging of all adjustments

Run this script to see the RL agent in action:
    python examples/rl_agent_demo.py
"""

from datetime import datetime, timezone
import random

from algoforge.core.orchestrator import Orchestrator
from algoforge.core.constants import Direction
from algoforge.execution.paper import TradeRecord
from algoforge.ml.rl_adjuster import RLConfig


def create_trade(
    trade_id: str,
    symbol: str,
    direction: Direction,
    pnl: float,
    signal_family: str = "momentum",
) -> TradeRecord:
    """Create a sample trade record."""
    entry_price = 50000.0
    exit_price = entry_price + (pnl / 0.1)  # Assuming 0.1 quantity
    
    return TradeRecord(
        id=trade_id,
        symbol=symbol,
        direction=direction,
        strategy=signal_family,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=0.1,
        entry_time=datetime.now(timezone.utc),
        exit_time=datetime.now(timezone.utc),
        pnl=pnl,
        commission=5.0,
        slippage=2.0,
        bars_held=random.randint(5, 20),
        metadata={"signal_family": signal_family},
    )


def simulate_trading_session(orch: Orchestrator, num_trades: int, win_rate: float):
    """Simulate a trading session with specified win rate."""
    print(f"\n{'='*60}")
    print(f"Simulating {num_trades} trades with {win_rate*100:.0f}% win rate")
    print(f"{'='*60}")
    
    for i in range(num_trades):
        # Randomly determine if trade is a winner
        is_winner = random.random() < win_rate
        
        # Generate P&L
        if is_winner:
            pnl = random.uniform(50, 200)  # Winning trade
        else:
            pnl = random.uniform(-150, -30)  # Losing trade
        
        # Create and record trade
        trade = create_trade(
            trade_id=f"trade-{i+1}",
            symbol="BTCUSDT",
            direction=Direction.LONG,
            pnl=pnl,
            signal_family=random.choice(["momentum", "mean_reversion", "breakout"]),
        )
        
        orch.record_trade_outcome(trade, signal_family=trade.metadata["signal_family"])
        
        print(f"Trade {i+1}: {trade.metadata['signal_family']:15s} "
              f"P&L: ${pnl:7.2f} {'✓' if is_winner else '✗'}")


def print_rl_stats(orch: Orchestrator):
    """Print current RL agent statistics."""
    stats = orch.stats["rl_agent"]
    
    print(f"\n{'='*60}")
    print("RL Agent Statistics")
    print(f"{'='*60}")
    print(f"Total Trades Observed:      {stats['total_trades_observed']}")
    print(f"Consecutive Poor Trades:    {stats['consecutive_poor_trades']}")
    print(f"Cumulative R-Multiple:      {stats['cumulative_r_multiple']:.2f}")
    print(f"Conviction Thresholds:      {stats['conviction_thresholds']}")
    print(f"ML Confidence Threshold:    {stats['ml_confidence_threshold']:.2f}")
    print(f"Last Adjustment Reason:     {stats['last_adjustment_reason']}")
    print(f"{'='*60}\n")


def main():
    """Run the RL agent demonstration."""
    print("\n" + "="*60)
    print("AlgoForge RL Threshold Adjuster Demonstration")
    print("="*60)
    
    # Create custom RL configuration
    rl_config = RLConfig(
        baseline_conviction_thresholds=(0.3, 0.6),
        exploration_rate=0.1,  # 10% exploration
        revert_threshold=10,   # Revert after 10 poor trades
        poor_trade_r_multiple=-0.5,
    )
    
    # Initialize Orchestrator with RL agent
    print("\nInitializing Orchestrator with RL Agent...")
    orch = Orchestrator(
        capital=100_000,
        validate_config=False,
        enable_rl_adjustment=True,
        rl_config=rl_config,
    )
    
    print(f"✓ RL Agent initialized")
    print(f"  - Exploration Rate: {rl_config.exploration_rate*100:.0f}%")
    print(f"  - Revert Threshold: {rl_config.revert_threshold} poor trades")
    print(f"  - Baseline Conviction: {rl_config.baseline_conviction_thresholds}")
    
    # Phase 1: Good performance (60% win rate)
    print("\n" + "="*60)
    print("PHASE 1: Good Performance Period")
    print("="*60)
    simulate_trading_session(orch, num_trades=20, win_rate=0.60)
    print_rl_stats(orch)
    
    # Apply RL adjustments after good performance
    print("Applying RL adjustments after good performance...")
    orch.apply_rl_adjustments()
    print_rl_stats(orch)
    
    # Phase 2: Poor performance (30% win rate)
    print("\n" + "="*60)
    print("PHASE 2: Poor Performance Period")
    print("="*60)
    simulate_trading_session(orch, num_trades=12, win_rate=0.30)
    print_rl_stats(orch)
    
    # Check if reversion to baseline occurred
    if orch._rl_agent.state.consecutive_poor_trades == 0:
        print("✓ RL Agent automatically reverted to baseline parameters!")
    
    # Phase 3: Recovery (55% win rate)
    print("\n" + "="*60)
    print("PHASE 3: Recovery Period")
    print("="*60)
    simulate_trading_session(orch, num_trades=15, win_rate=0.55)
    print_rl_stats(orch)
    
    # Apply final adjustments
    print("Applying final RL adjustments...")
    orch.apply_rl_adjustments()
    print_rl_stats(orch)
    
    # Summary
    print("\n" + "="*60)
    print("Demonstration Complete")
    print("="*60)
    print("\nKey Takeaways:")
    print("1. RL Agent learns from trade outcomes in real-time")
    print("2. Thresholds adjust based on performance (good → lower, poor → higher)")
    print("3. Automatic reversion to baseline after consecutive poor trades")
    print("4. Exploration (10%) vs Exploitation (90%) for continuous learning")
    print("5. All adjustments are logged for transparency and debugging")
    print("\nThe RL Agent helps the system continuously improve by:")
    print("- Lowering thresholds when performance is good (take more trades)")
    print("- Raising thresholds when performance is poor (be more selective)")
    print("- Adjusting signal family weights based on per-family performance")
    print("- Adapting ML confidence thresholds based on prediction accuracy")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Set random seed for reproducibility
    random.seed(42)
    main()
