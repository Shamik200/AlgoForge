"""Unit tests for the Signal Combination Engine."""

import pytest

from algoforge.combination.correlation import SignalCorrelationMatrix, cull_redundant_signals
from algoforge.combination.engine import CombinationEngine
from algoforge.combination.normalization import RollingNormalizer
from algoforge.combination.weighting import calculate_softmax_weights
from algoforge.signals.models import SignalDirection, SignalResult


def test_rolling_normalizer():
    """Test z-score calculation and clipping."""
    normalizer = RollingNormalizer(window_size=10)
    
    # Not enough data (len < 2) -> just clip
    assert normalizer.get_normalized_score("mom", 5.0) == 1.0
    assert normalizer.get_normalized_score("mom", -5.0) == -1.0
    assert normalizer.get_normalized_score("mom", 0.5) == 0.5
    
    # Add data to build history (mean = 0, std = 10)
    for score in [10, -10, 10, -10, 10, -10, 10, -10, 10, -10]:
        normalizer.add_score("mom", score)
        
    # Current score = 10
    # Mean = 0, Std = 10. Z-score = (10 - 0) / 10 = 1.0.
    # We divide by 3: 1.0 / 3.0 = 0.333
    assert normalizer.get_normalized_score("mom", 10.0) == pytest.approx(0.333, 0.01)
    
    # Extreme score = 50. Z-score = 5. Divided by 3 = 1.666. Clipped to 1.0.
    assert normalizer.get_normalized_score("mom", 50.0) == 1.0


def test_softmax_weights():
    """Test softmax calculation over sharpe ratios."""
    # Negative sharpes get penalized but still positive weights
    sharpes = {"mom": 1.0, "rev": -1.0, "str": 0.0}
    weights = calculate_softmax_weights(sharpes)
    
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["mom"] > weights["str"] > weights["rev"]
    
    # Single signal gets 100% weight
    assert calculate_softmax_weights({"mom": 5.0}) == {"mom": 1.0}


def test_correlation_culling():
    """Test pairwise culling based on correlation threshold."""
    corr_matrix = SignalCorrelationMatrix(window_size=5)
    
    # Fam_A and Fam_B are perfectly correlated (1, 2, 3, 4, 5)
    # Fam_C is inversely correlated (-1, -2, -3, -4, -5)
    for i in range(1, 6):
        corr_matrix.add_signals({
            "fam_a": float(i),
            "fam_b": float(i),
            "fam_c": float(-i)
        })
        
    sharpes = {"fam_a": 1.5, "fam_b": 2.0, "fam_c": 1.0}
    
    # fam_a and fam_b are correlated. fam_b has higher Sharpe (2.0 vs 1.5).
    # fam_a should be dropped. fam_c remains.
    culled = cull_redundant_signals(sharpes, corr_matrix, max_correlation=0.7)
    
    assert "fam_a" not in culled
    assert "fam_b" in culled
    assert "fam_c" in culled


def test_combination_engine_integration():
    """Test full engine flow from raw signals to composite score."""
    engine = CombinationEngine(norm_window=5, corr_window=5, max_corr=0.7)
    
    # Feed some history to prime the normalizer
    for i in range(5):
        engine.normalizer.add_score("momentum", i)
        engine.normalizer.add_score("reversion", -i)
        
    signals = [
        SignalResult(family_name="momentum", score=0.5, direction=SignalDirection.LONG, is_valid=True),
        SignalResult(family_name="reversion", score=-0.5, direction=SignalDirection.SHORT, is_valid=True)
    ]
    
    sharpes = {"momentum": 1.5, "reversion": 0.5}
    
    # Run composite
    composite = engine.combine(signals, sharpes)
    
    assert composite.is_valid is True
    assert composite.family_name == "composite"
    
    import json
    weights = json.loads(composite.metadata["weights"])
    raw_scores = json.loads(composite.metadata["raw_scores"])
    
    # Momentum weight > Reversion weight because of Sharpe 1.5 > 0.5
    assert weights["momentum"] > weights["reversion"]
    assert "composite" not in raw_scores # Sanity check
