"""Example usage of RLThresholdAdjuster.

This example demonstrates how to use the RLThresholdAdjuster to adaptively
adjust system thresholds based on trade outcomes.
"""

from datetime import datetime, timezone, timedelta

from algoforge.ml import (
    RLThresholdAdjuster,
    RLConfig,
    TradeOutcome,
)


def main():
    """Demonstrate RLThresholdAdjuster usage."""
    
    # Configure the RL agent
    config = RLConfig(
        baseline_conviction_thresholds=(0.3, 0.6),
        baseline_ml_confidence_threshold=0.5,
        exploration_rate=0.1,  # 10% exploration
        revert_threshold=20,  # Revert after 20 poor trades
        poor_trade_r_multiple=-0.5,
        state_file="data/rl_agent_state.json",
    )
    
    # Initialize the adjuster
    adjuster = RLThresholdAdjuster(config=config)
    
    print("=" * 60)
    print("RLThresholdAdjuster Example")
    print("=" * 60)
    
    # Get initial thresholds
    initial = adjuster.get_current_adjustments()
    print(f"\nInitial Thresholds:")
    print(f"  Conviction: {initial.conviction_thresholds}")
    print(f"  ML Confidence: {initial.ml_confidence_threshold}")
    print(f"  Signal Family Weights: {initial.signal_family_weights}")
    
    # Simulate some trades
    print("\n" + "=" * 60)
    print("Simulating Trade Outcomes")
    print("=" * 60)
    
    # Good momentum trades
    print("\n1. Observing 10 good momentum trades...")
    for i in range(10):
        trade = TradeOutcome(
            trade_id=f"momentum_{i}",
            symbol="AAPL",
            direction="long",
            entry_price=150.0,
            exit_price=153.0,
            quantity=100.0,
            pnl_dollars=300.0,
            r_multiple=1.5,  # Good trade
            conviction_score=0.7,
            signal_family="momentum",
            market_regime={"bull": 0.7, "bear": 0.1, "sideways": 0.2},
            signal_scores={"momentum": 0.6, "mean_reversion": -0.2},
            ml_confidence=0.8,
            entry_time=datetime.now(timezone.utc) - timedelta(hours=2),
            exit_time=datetime.now(timezone.utc),
            bars_in_trade=10,
            exit_reason="take_profit",
        )
        adjuster.observe_trade_outcome(trade)
    
    # Poor breakout trades
    print("2. Observing 10 poor breakout trades...")
    for i in range(10):
        trade = TradeOutcome(
            trade_id=f"breakout_{i}",
            symbol="TSLA",
            direction="long",
            entry_price=200.0,
            exit_price=198.0,
            quantity=50.0,
            pnl_dollars=-100.0,
            r_multiple=-0.5,  # Poor trade
            conviction_score=0.5,
            signal_family="breakout",
            market_regime={"bull": 0.3, "bear": 0.5, "sideways": 0.2},
            signal_scores={"breakout": 0.4, "momentum": 0.1},
            ml_confidence=0.4,
            entry_time=datetime.now(timezone.utc) - timedelta(hours=1),
            exit_time=datetime.now(timezone.utc),
            bars_in_trade=5,
            exit_reason="stop_loss",
        )
        adjuster.observe_trade_outcome(trade)
    
    # Check state
    print(f"\nState after 20 trades:")
    print(f"  Total trades observed: {adjuster.state.total_trades_observed}")
    print(f"  Cumulative R-multiple: {adjuster.state.cumulative_r_multiple:.2f}")
    print(f"  Consecutive poor trades: {adjuster.state.consecutive_poor_trades}")
    print(f"\nPer-family performance:")
    for family, avg_r in adjuster.state.avg_r_multiple_by_family.items():
        count = adjuster.state.trade_count_by_family[family]
        print(f"  {family}: {avg_r:.2f} (n={count})")
    
    # Adjust thresholds
    print("\n" + "=" * 60)
    print("Adjusting Thresholds")
    print("=" * 60)
    
    adjustments = adjuster.adjust_thresholds()
    
    print(f"\nNew Thresholds:")
    print(f"  Conviction: {adjustments.conviction_thresholds}")
    print(f"  ML Confidence: {adjustments.ml_confidence_threshold}")
    print(f"  Signal Family Weights:")
    for family, weight in adjustments.signal_family_weights.items():
        print(f"    {family}: {weight:.2f}")
    print(f"\nReason: {adjustments.adjustments_reason}")
    print(f"Trades analyzed: {adjustments.trades_analyzed}")
    
    # Demonstrate revert to baseline
    print("\n" + "=" * 60)
    print("Testing Revert to Baseline")
    print("=" * 60)
    
    print("\nSimulating 5 consecutive poor trades...")
    for i in range(5):
        trade = TradeOutcome(
            trade_id=f"poor_{i}",
            symbol="SPY",
            direction="short",
            entry_price=400.0,
            exit_price=402.0,
            quantity=10.0,
            pnl_dollars=-20.0,
            r_multiple=-0.8,  # Very poor trade
            conviction_score=0.4,
            signal_family="mean_reversion",
            market_regime={"bull": 0.6, "bear": 0.2, "sideways": 0.2},
            signal_scores={"mean_reversion": -0.3},
            ml_confidence=0.3,
            entry_time=datetime.now(timezone.utc) - timedelta(minutes=30),
            exit_time=datetime.now(timezone.utc),
            bars_in_trade=3,
            exit_reason="stop_loss",
        )
        adjuster.observe_trade_outcome(trade)
    
    # Should have reverted to baseline
    final = adjuster.get_current_adjustments()
    print(f"\nAfter consecutive poor trades:")
    print(f"  Conviction: {final.conviction_thresholds}")
    print(f"  ML Confidence: {final.ml_confidence_threshold}")
    print(f"  Reason: {final.adjustments_reason}")
    
    print("\n" + "=" * 60)
    print("Example Complete")
    print("=" * 60)
    print(f"\nState persisted to: {config.state_file}")


if __name__ == "__main__":
    main()
