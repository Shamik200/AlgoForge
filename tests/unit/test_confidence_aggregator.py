"""Unit tests for the ConfidenceAggregator module."""

import pytest

from algoforge.ml.confidence_aggregator import ConfidenceAggregator, ConvictionScore
from algoforge.ml.fingpt_client import FinGPTPrediction, PricePoint
from algoforge.ml.orchestrator import MLPrediction
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.signals.models import SignalDirection


class TestConfidenceAggregator:
    """Test suite for ConfidenceAggregator class."""
    
    def test_initialization(self):
        """Test ConfidenceAggregator initialization with default thresholds."""
        aggregator = ConfidenceAggregator()
        assert aggregator.skip_threshold == 0.3
        assert aggregator.half_position_threshold == 0.6
    
    def test_initialization_custom_thresholds(self):
        """Test ConfidenceAggregator initialization with custom thresholds."""
        aggregator = ConfidenceAggregator(skip_threshold=0.2, half_position_threshold=0.7)
        assert aggregator.skip_threshold == 0.2
        assert aggregator.half_position_threshold == 0.7
    
    def test_compute_conviction_perfect_alignment(self):
        """Test conviction computation with perfect alignment (all 1.0)."""
        aggregator = ConfidenceAggregator()
        conviction = aggregator.compute_conviction(
            composite_signal=1.0,
            ml_confidence=1.0,
            fingpt_confidence=1.0,
            regime_alignment=1.0,
        )
        
        assert conviction.total_conviction == 1.0
        assert conviction.signal_score == 1.0
        assert conviction.ml_confidence == 1.0
        assert conviction.fingpt_confidence == 1.0
        assert conviction.regime_alignment == 1.0
        assert conviction.decision == "full_position"
    
    def test_compute_conviction_zero_signal(self):
        """Test conviction computation with zero signal (neutral)."""
        aggregator = ConfidenceAggregator()
        conviction = aggregator.compute_conviction(
            composite_signal=0.0,
            ml_confidence=1.0,
            fingpt_confidence=1.0,
            regime_alignment=1.0,
        )
        
        assert conviction.total_conviction == 0.0
        assert conviction.signal_score == 0.0
        assert conviction.decision == "skip"
    
    def test_compute_conviction_negative_signal(self):
        """Test conviction computation with negative signal (short)."""
        aggregator = ConfidenceAggregator()
        conviction = aggregator.compute_conviction(
            composite_signal=-0.8,
            ml_confidence=0.9,
            fingpt_confidence=0.85,
            regime_alignment=0.95,
        )
        
        # Signal score should be absolute value
        assert conviction.signal_score == 0.8
        # Total conviction = 0.8 * 0.9 * 0.85 * 0.95 = 0.5814
        assert 0.58 <= conviction.total_conviction <= 0.59
        assert conviction.decision == "half_position"
    
    def test_compute_conviction_skip_threshold(self):
        """Test conviction below skip threshold results in skip decision."""
        aggregator = ConfidenceAggregator()
        conviction = aggregator.compute_conviction(
            composite_signal=0.5,
            ml_confidence=0.5,
            fingpt_confidence=0.5,
            regime_alignment=0.5,
        )
        
        # 0.5 * 0.5 * 0.5 * 0.5 = 0.0625 < 0.3
        assert conviction.total_conviction < 0.3
        assert conviction.decision == "skip"
    
    def test_compute_conviction_half_position_threshold(self):
        """Test conviction in half position range."""
        aggregator = ConfidenceAggregator()
        conviction = aggregator.compute_conviction(
            composite_signal=0.7,
            ml_confidence=0.8,
            fingpt_confidence=0.9,
            regime_alignment=0.85,
        )
        
        # 0.7 * 0.8 * 0.9 * 0.85 = 0.4284
        assert 0.3 <= conviction.total_conviction < 0.6
        assert conviction.decision == "half_position"
    
    def test_compute_conviction_full_position_threshold(self):
        """Test conviction above full position threshold."""
        aggregator = ConfidenceAggregator()
        conviction = aggregator.compute_conviction(
            composite_signal=0.9,
            ml_confidence=0.9,
            fingpt_confidence=0.9,
            regime_alignment=0.9,
        )
        
        # 0.9 * 0.9 * 0.9 * 0.9 = 0.6561
        assert conviction.total_conviction >= 0.6
        assert conviction.decision == "full_position"
    
    def test_compute_conviction_invalid_signal_range(self):
        """Test that invalid signal range raises ValueError."""
        aggregator = ConfidenceAggregator()
        
        with pytest.raises(ValueError, match="composite_signal must be in"):
            aggregator.compute_conviction(
                composite_signal=1.5,  # Invalid: > 1.0
                ml_confidence=0.8,
                fingpt_confidence=0.8,
                regime_alignment=0.8,
            )
        
        with pytest.raises(ValueError, match="composite_signal must be in"):
            aggregator.compute_conviction(
                composite_signal=-1.5,  # Invalid: < -1.0
                ml_confidence=0.8,
                fingpt_confidence=0.8,
                regime_alignment=0.8,
            )
    
    def test_compute_conviction_invalid_confidence_range(self):
        """Test that invalid confidence ranges raise ValueError."""
        aggregator = ConfidenceAggregator()
        
        with pytest.raises(ValueError, match="ml_confidence must be in"):
            aggregator.compute_conviction(
                composite_signal=0.8,
                ml_confidence=1.5,  # Invalid: > 1.0
                fingpt_confidence=0.8,
                regime_alignment=0.8,
            )
        
        with pytest.raises(ValueError, match="fingpt_confidence must be in"):
            aggregator.compute_conviction(
                composite_signal=0.8,
                ml_confidence=0.8,
                fingpt_confidence=-0.1,  # Invalid: < 0.0
                regime_alignment=0.8,
            )
        
        with pytest.raises(ValueError, match="regime_alignment must be in"):
            aggregator.compute_conviction(
                composite_signal=0.8,
                ml_confidence=0.8,
                fingpt_confidence=0.8,
                regime_alignment=1.1,  # Invalid: > 1.0
            )
    
    def test_compute_conviction_components_breakdown(self):
        """Test that components breakdown is correctly populated."""
        aggregator = ConfidenceAggregator()
        conviction = aggregator.compute_conviction(
            composite_signal=0.7,
            ml_confidence=0.8,
            fingpt_confidence=0.9,
            regime_alignment=0.85,
        )
        
        assert "signal_score" in conviction.components_breakdown
        assert "ml_confidence" in conviction.components_breakdown
        assert "fingpt_confidence" in conviction.components_breakdown
        assert "regime_alignment" in conviction.components_breakdown
        assert "total_conviction" in conviction.components_breakdown
        
        assert conviction.components_breakdown["signal_score"] == 0.7
        assert conviction.components_breakdown["ml_confidence"] == 0.8
        assert conviction.components_breakdown["fingpt_confidence"] == 0.9
        assert conviction.components_breakdown["regime_alignment"] == 0.85


class TestAlignmentChecking:
    """Test suite for alignment checking methods."""
    
    def test_check_alignment_all_long(self):
        """Test alignment when all sources predict long."""
        aggregator = ConfidenceAggregator()
        alignment = aggregator.check_alignment(
            signal_direction=SignalDirection.LONG,
            ml_direction="long",
            fingpt_direction="up",
            regime=RegimeState.TREND_UP,
        )
        
        # Perfect alignment: (1.0 + 1.0 + 1.0) / 3 = 1.0
        assert alignment == 1.0
    
    def test_check_alignment_all_short(self):
        """Test alignment when all sources predict short."""
        aggregator = ConfidenceAggregator()
        alignment = aggregator.check_alignment(
            signal_direction=SignalDirection.SHORT,
            ml_direction="short",
            fingpt_direction="down",
            regime=RegimeState.TREND_DOWN,
        )
        
        # Perfect alignment: (1.0 + 1.0 + 1.0) / 3 = 1.0
        assert alignment == 1.0
    
    def test_check_alignment_conflicting_directions(self):
        """Test alignment when sources conflict."""
        aggregator = ConfidenceAggregator()
        alignment = aggregator.check_alignment(
            signal_direction=SignalDirection.LONG,
            ml_direction="short",
            fingpt_direction="down",
            regime=RegimeState.TREND_DOWN,
        )
        
        # All conflict: (0.0 + 0.0 + 0.0) / 3 = 0.0
        assert alignment == 0.0
    
    def test_check_alignment_neutral_signal(self):
        """Test alignment with neutral signal."""
        aggregator = ConfidenceAggregator()
        alignment = aggregator.check_alignment(
            signal_direction=SignalDirection.NEUTRAL,
            ml_direction="long",
            fingpt_direction="up",
            regime=RegimeState.TREND_UP,
        )
        
        # Neutral signal: (0.5 + 0.5 + 0.5) / 3 = 0.5
        assert alignment == 0.5
    
    def test_check_alignment_neutral_ml(self):
        """Test alignment with neutral ML prediction."""
        aggregator = ConfidenceAggregator()
        alignment = aggregator.check_alignment(
            signal_direction=SignalDirection.LONG,
            ml_direction="neutral",
            fingpt_direction="up",
            regime=RegimeState.TREND_UP,
        )
        
        # ML neutral: (0.5 + 1.0 + 1.0) / 3 = 0.833...
        assert 0.83 <= alignment <= 0.84
    
    def test_check_alignment_mean_revert_regime(self):
        """Test alignment with mean reversion regime."""
        aggregator = ConfidenceAggregator()
        alignment = aggregator.check_alignment(
            signal_direction=SignalDirection.LONG,
            ml_direction="long",
            fingpt_direction="up",
            regime=RegimeState.MEAN_REVERT,
        )
        
        # Mean revert regime is neutral: (1.0 + 1.0 + 0.7) / 3 = 0.9
        assert 0.89 <= alignment <= 0.91
    
    def test_check_alignment_crisis_regime(self):
        """Test alignment with crisis regime."""
        aggregator = ConfidenceAggregator()
        alignment = aggregator.check_alignment(
            signal_direction=SignalDirection.LONG,
            ml_direction="long",
            fingpt_direction="up",
            regime=RegimeState.CRISIS,
        )
        
        # Crisis regime discourages positions: (1.0 + 1.0 + 0.3) / 3 = 0.766...
        assert 0.76 <= alignment <= 0.77
    
    def test_normalize_fingpt_direction(self):
        """Test FinGPT direction normalization."""
        aggregator = ConfidenceAggregator()
        
        assert aggregator._normalize_fingpt_direction("up") == "long"
        assert aggregator._normalize_fingpt_direction("down") == "short"
        assert aggregator._normalize_fingpt_direction("neutral") == "neutral"
    
    def test_compute_directional_alignment(self):
        """Test directional alignment computation."""
        aggregator = ConfidenceAggregator()
        
        # Same direction
        assert aggregator._compute_directional_alignment("long", "long") == 1.0
        assert aggregator._compute_directional_alignment("short", "short") == 1.0
        
        # Opposite direction
        assert aggregator._compute_directional_alignment("long", "short") == 0.0
        assert aggregator._compute_directional_alignment("short", "long") == 0.0
        
        # Neutral
        assert aggregator._compute_directional_alignment("long", "neutral") == 0.5
        assert aggregator._compute_directional_alignment("neutral", "long") == 0.5
        assert aggregator._compute_directional_alignment("neutral", "neutral") == 0.5
    
    def test_compute_regime_alignment(self):
        """Test regime alignment computation."""
        aggregator = ConfidenceAggregator()
        
        # Trend up regime
        assert aggregator._compute_regime_alignment("long", RegimeState.TREND_UP) == 1.0
        assert aggregator._compute_regime_alignment("short", RegimeState.TREND_UP) == 0.0
        assert aggregator._compute_regime_alignment("neutral", RegimeState.TREND_UP) == 0.5
        
        # Trend down regime
        assert aggregator._compute_regime_alignment("short", RegimeState.TREND_DOWN) == 1.0
        assert aggregator._compute_regime_alignment("long", RegimeState.TREND_DOWN) == 0.0
        assert aggregator._compute_regime_alignment("neutral", RegimeState.TREND_DOWN) == 0.5
        
        # Mean revert regime
        assert aggregator._compute_regime_alignment("long", RegimeState.MEAN_REVERT) == 0.7
        assert aggregator._compute_regime_alignment("short", RegimeState.MEAN_REVERT) == 0.7
        assert aggregator._compute_regime_alignment("neutral", RegimeState.MEAN_REVERT) == 0.7
        
        # Crisis regime
        assert aggregator._compute_regime_alignment("neutral", RegimeState.CRISIS) == 0.8
        assert aggregator._compute_regime_alignment("long", RegimeState.CRISIS) == 0.3
        assert aggregator._compute_regime_alignment("short", RegimeState.CRISIS) == 0.3


class TestConvictionFromObjects:
    """Test suite for compute_conviction_from_objects method."""
    
    def test_compute_conviction_from_objects_all_available(self):
        """Test conviction computation with all prediction objects available."""
        from datetime import datetime
        
        aggregator = ConfidenceAggregator()
        
        # Create ML prediction
        ml_prediction = MLPrediction(
            direction="long",
            probability=0.85,
            confidence=0.8,
            xgboost_score=0.7,
            lstm_forecast=[],
            ensemble_score=0.75,
            feature_importance={},
        )
        
        # Create FinGPT prediction
        fingpt_prediction = FinGPTPrediction(
            symbol="AAPL",
            timestamp=datetime.now(),
            predictions={
                1: PricePoint(price=150.0, lower_bound=148.0, upper_bound=152.0, confidence_interval_width=4.0)
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
        
        conviction = aggregator.compute_conviction_from_objects(
            composite_signal=0.8,
            ml_prediction=ml_prediction,
            fingpt_prediction=fingpt_prediction,
            regime_probs=regime_probs,
            signal_direction=SignalDirection.LONG,
        )
        
        assert conviction.signal_score == 0.8
        assert conviction.ml_confidence == 0.8
        assert conviction.fingpt_confidence == 0.75
        assert conviction.total_conviction > 0.0
    
    def test_compute_conviction_from_objects_no_ml(self):
        """Test conviction computation without ML prediction."""
        from datetime import datetime
        
        aggregator = ConfidenceAggregator()
        
        # Create FinGPT prediction
        fingpt_prediction = FinGPTPrediction(
            symbol="AAPL",
            timestamp=datetime.now(),
            predictions={
                1: PricePoint(price=150.0, lower_bound=148.0, upper_bound=152.0, confidence_interval_width=4.0)
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
        
        conviction = aggregator.compute_conviction_from_objects(
            composite_signal=0.8,
            ml_prediction=None,
            fingpt_prediction=fingpt_prediction,
            regime_probs=regime_probs,
            signal_direction=SignalDirection.LONG,
        )
        
        # ML confidence should default to 1.0
        assert conviction.ml_confidence == 1.0
        assert conviction.fingpt_confidence == 0.75
    
    def test_compute_conviction_from_objects_no_fingpt(self):
        """Test conviction computation without FinGPT prediction."""
        aggregator = ConfidenceAggregator()
        
        # Create ML prediction
        ml_prediction = MLPrediction(
            direction="long",
            probability=0.85,
            confidence=0.8,
            xgboost_score=0.7,
            lstm_forecast=[],
            ensemble_score=0.75,
            feature_importance={},
        )
        
        # Create regime probabilities
        regime_probs = RegimeProbabilities(
            trend_up=0.7,
            trend_down=0.1,
            mean_revert=0.15,
            crisis=0.05,
        )
        
        conviction = aggregator.compute_conviction_from_objects(
            composite_signal=0.8,
            ml_prediction=ml_prediction,
            fingpt_prediction=None,
            regime_probs=regime_probs,
            signal_direction=SignalDirection.LONG,
        )
        
        # FinGPT confidence should default to 1.0
        assert conviction.ml_confidence == 0.8
        assert conviction.fingpt_confidence == 1.0
    
    def test_compute_conviction_from_objects_no_predictions(self):
        """Test conviction computation without any predictions."""
        aggregator = ConfidenceAggregator()
        
        # Create regime probabilities
        regime_probs = RegimeProbabilities(
            trend_up=0.7,
            trend_down=0.1,
            mean_revert=0.15,
            crisis=0.05,
        )
        
        conviction = aggregator.compute_conviction_from_objects(
            composite_signal=0.8,
            ml_prediction=None,
            fingpt_prediction=None,
            regime_probs=regime_probs,
            signal_direction=SignalDirection.LONG,
        )
        
        # Both should default to 1.0
        assert conviction.ml_confidence == 1.0
        assert conviction.fingpt_confidence == 1.0


class TestConvictionScoreModel:
    """Test suite for ConvictionScore Pydantic model."""
    
    def test_conviction_score_creation(self):
        """Test ConvictionScore model creation."""
        score = ConvictionScore(
            total_conviction=0.75,
            signal_score=0.8,
            ml_confidence=0.9,
            fingpt_confidence=0.85,
            regime_alignment=0.95,
            components_breakdown={},
            decision="full_position",
        )
        
        assert score.total_conviction == 0.75
        assert score.signal_score == 0.8
        assert score.ml_confidence == 0.9
        assert score.fingpt_confidence == 0.85
        assert score.regime_alignment == 0.95
        assert score.decision == "full_position"
    
    def test_conviction_score_validation(self):
        """Test ConvictionScore validation."""
        # Valid score
        score = ConvictionScore(
            total_conviction=0.5,
            signal_score=0.5,
            ml_confidence=0.5,
            fingpt_confidence=0.5,
            regime_alignment=0.5,
            components_breakdown={},
            decision="half_position",
        )
        assert score.total_conviction == 0.5
        
        # Invalid total_conviction (> 1.0)
        with pytest.raises(ValueError):
            ConvictionScore(
                total_conviction=1.5,
                signal_score=0.5,
                ml_confidence=0.5,
                fingpt_confidence=0.5,
                regime_alignment=0.5,
                components_breakdown={},
                decision="full_position",
            )
        
        # Invalid signal_score (< 0.0)
        with pytest.raises(ValueError):
            ConvictionScore(
                total_conviction=0.5,
                signal_score=-0.1,
                ml_confidence=0.5,
                fingpt_confidence=0.5,
                regime_alignment=0.5,
                components_breakdown={},
                decision="half_position",
            )
