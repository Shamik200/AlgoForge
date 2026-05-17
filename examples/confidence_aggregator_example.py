"""Example usage of ConfidenceAggregator for position sizing decisions.

This example demonstrates how the ConfidenceAggregator integrates multiple
confidence sources to produce a unified conviction score for position sizing.
"""

from datetime import datetime

from algoforge.ml.confidence_aggregator import ConfidenceAggregator
from algoforge.ml.fingpt_client import FinGPTPrediction, PricePoint
from algoforge.ml.orchestrator import MLPrediction
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.signals.models import SignalDirection


def example_basic_conviction():
    """Example: Basic conviction computation from raw scores."""
    print("=" * 60)
    print("Example 1: Basic Conviction Computation")
    print("=" * 60)
    
    aggregator = ConfidenceAggregator()
    
    # Scenario: Strong bullish signal with good ML and FinGPT confidence
    conviction = aggregator.compute_conviction(
        composite_signal=0.8,      # Strong bullish signal from Combination Engine
        ml_confidence=0.85,         # High ML confidence
        fingpt_confidence=0.9,      # High FinGPT confidence
        regime_alignment=0.95,      # Excellent regime alignment
    )
    
    print(f"Composite Signal: {0.8}")
    print(f"ML Confidence: {0.85}")
    print(f"FinGPT Confidence: {0.9}")
    print(f"Regime Alignment: {0.95}")
    print(f"\nTotal Conviction: {conviction.total_conviction:.3f}")
    print(f"Decision: {conviction.decision}")
    print(f"Components Breakdown: {conviction.components_breakdown}")
    print()


def example_low_conviction():
    """Example: Low conviction scenario that skips the trade."""
    print("=" * 60)
    print("Example 2: Low Conviction (Skip Trade)")
    print("=" * 60)
    
    aggregator = ConfidenceAggregator()
    
    # Scenario: Weak signal with low confidence
    conviction = aggregator.compute_conviction(
        composite_signal=0.4,      # Weak signal
        ml_confidence=0.5,         # Low ML confidence
        fingpt_confidence=0.6,     # Moderate FinGPT confidence
        regime_alignment=0.5,      # Neutral regime alignment
    )
    
    print(f"Composite Signal: {0.4}")
    print(f"ML Confidence: {0.5}")
    print(f"FinGPT Confidence: {0.6}")
    print(f"Regime Alignment: {0.5}")
    print(f"\nTotal Conviction: {conviction.total_conviction:.3f}")
    print(f"Decision: {conviction.decision}")
    print(f"Explanation: Conviction {conviction.total_conviction:.3f} < 0.3 threshold, trade skipped")
    print()


def example_half_position():
    """Example: Medium conviction scenario for half position."""
    print("=" * 60)
    print("Example 3: Medium Conviction (Half Position)")
    print("=" * 60)
    
    aggregator = ConfidenceAggregator()
    
    # Scenario: Moderate signal with decent confidence
    conviction = aggregator.compute_conviction(
        composite_signal=0.7,      # Moderate signal
        ml_confidence=0.75,        # Good ML confidence
        fingpt_confidence=0.8,     # Good FinGPT confidence
        regime_alignment=0.7,      # Good regime alignment
    )
    
    print(f"Composite Signal: {0.7}")
    print(f"ML Confidence: {0.75}")
    print(f"FinGPT Confidence: {0.8}")
    print(f"Regime Alignment: {0.7}")
    print(f"\nTotal Conviction: {conviction.total_conviction:.3f}")
    print(f"Decision: {conviction.decision}")
    print(f"Explanation: 0.3 <= Conviction {conviction.total_conviction:.3f} < 0.6, use 50% position size")
    print()


def example_alignment_checking():
    """Example: Checking alignment between different prediction sources."""
    print("=" * 60)
    print("Example 4: Alignment Checking")
    print("=" * 60)
    
    aggregator = ConfidenceAggregator()
    
    # Scenario 1: Perfect alignment
    alignment1 = aggregator.check_alignment(
        signal_direction=SignalDirection.LONG,
        ml_direction="long",
        fingpt_direction="up",
        regime=RegimeState.TREND_UP,
    )
    print("Scenario 1: Perfect Alignment")
    print(f"  Signal: LONG, ML: long, FinGPT: up, Regime: TREND_UP")
    print(f"  Alignment Score: {alignment1:.2f}")
    print()
    
    # Scenario 2: Conflicting signals
    alignment2 = aggregator.check_alignment(
        signal_direction=SignalDirection.LONG,
        ml_direction="short",
        fingpt_direction="down",
        regime=RegimeState.TREND_DOWN,
    )
    print("Scenario 2: Conflicting Signals")
    print(f"  Signal: LONG, ML: short, FinGPT: down, Regime: TREND_DOWN")
    print(f"  Alignment Score: {alignment2:.2f}")
    print()
    
    # Scenario 3: Mixed alignment
    alignment3 = aggregator.check_alignment(
        signal_direction=SignalDirection.LONG,
        ml_direction="long",
        fingpt_direction="neutral",
        regime=RegimeState.MEAN_REVERT,
    )
    print("Scenario 3: Mixed Alignment")
    print(f"  Signal: LONG, ML: long, FinGPT: neutral, Regime: MEAN_REVERT")
    print(f"  Alignment Score: {alignment3:.2f}")
    print()


def example_with_objects():
    """Example: Computing conviction from high-level prediction objects."""
    print("=" * 60)
    print("Example 5: Conviction from Prediction Objects")
    print("=" * 60)
    
    aggregator = ConfidenceAggregator()
    
    # Create ML prediction
    ml_prediction = MLPrediction(
        direction="long",
        probability=0.85,
        confidence=0.8,
        xgboost_score=0.75,
        lstm_forecast=[],
        ensemble_score=0.78,
        feature_importance={"momentum": 0.3, "volatility": 0.25},
    )
    
    # Create FinGPT prediction
    fingpt_prediction = FinGPTPrediction(
        symbol="AAPL",
        timestamp=datetime.now(),
        predictions={
            1: PricePoint(
                price=150.5,
                lower_bound=148.0,
                upper_bound=153.0,
                confidence_interval_width=5.0,
            ),
            5: PricePoint(
                price=152.0,
                lower_bound=147.0,
                upper_bound=157.0,
                confidence_interval_width=10.0,
            ),
        },
        confidence=0.75,
        direction="up",
    )
    
    # Create regime probabilities
    regime_probs = RegimeProbabilities(
        trend_up=0.7,
        trend_down=0.1,
        mean_revert=0.15,
        crisis=0.05,
    )
    
    # Compute conviction
    conviction = aggregator.compute_conviction_from_objects(
        composite_signal=0.8,
        ml_prediction=ml_prediction,
        fingpt_prediction=fingpt_prediction,
        regime_probs=regime_probs,
        signal_direction=SignalDirection.LONG,
    )
    
    print("Input Objects:")
    print(f"  Composite Signal: 0.8 (LONG)")
    print(f"  ML Prediction: {ml_prediction.direction} (confidence: {ml_prediction.confidence})")
    print(f"  FinGPT Prediction: {fingpt_prediction.direction} (confidence: {fingpt_prediction.confidence})")
    print(f"  Regime: {regime_probs.dominant_regime.value}")
    print()
    print("Output:")
    print(f"  Total Conviction: {conviction.total_conviction:.3f}")
    print(f"  Decision: {conviction.decision}")
    print(f"  Signal Score: {conviction.signal_score:.3f}")
    print(f"  ML Confidence: {conviction.ml_confidence:.3f}")
    print(f"  FinGPT Confidence: {conviction.fingpt_confidence:.3f}")
    print(f"  Regime Alignment: {conviction.regime_alignment:.3f}")
    print()


def example_crisis_regime():
    """Example: Conviction during crisis regime."""
    print("=" * 60)
    print("Example 6: Crisis Regime (Reduced Conviction)")
    print("=" * 60)
    
    aggregator = ConfidenceAggregator()
    
    # Scenario: Strong signal but crisis regime
    alignment = aggregator.check_alignment(
        signal_direction=SignalDirection.LONG,
        ml_direction="long",
        fingpt_direction="up",
        regime=RegimeState.CRISIS,
    )
    
    conviction = aggregator.compute_conviction(
        composite_signal=0.9,      # Very strong signal
        ml_confidence=0.9,         # High ML confidence
        fingpt_confidence=0.85,    # High FinGPT confidence
        regime_alignment=alignment, # But crisis regime reduces alignment
    )
    
    print(f"Composite Signal: {0.9} (Very Strong)")
    print(f"ML Confidence: {0.9}")
    print(f"FinGPT Confidence: {0.85}")
    print(f"Regime: CRISIS")
    print(f"Regime Alignment: {alignment:.3f} (reduced due to crisis)")
    print(f"\nTotal Conviction: {conviction.total_conviction:.3f}")
    print(f"Decision: {conviction.decision}")
    print(f"Explanation: Crisis regime reduces conviction despite strong signals")
    print()


def main():
    """Run all examples."""
    print("\n")
    print("*" * 60)
    print("ConfidenceAggregator Usage Examples")
    print("*" * 60)
    print()
    
    example_basic_conviction()
    example_low_conviction()
    example_half_position()
    example_alignment_checking()
    example_with_objects()
    example_crisis_regime()
    
    print("*" * 60)
    print("Examples completed successfully!")
    print("*" * 60)
    print()


if __name__ == "__main__":
    main()
