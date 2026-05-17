"""Confidence Aggregator for computing composite conviction scores.

This module aggregates confidence scores from multiple sources to produce
a unified conviction score that drives position sizing decisions:
- Combination Engine composite signal score
- ML Pipeline confidence
- FinGPT confidence
- Regime alignment

The aggregator implements Requirement 7.1 from the AlgoForge System Integration spec.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from algoforge.ml.fingpt_client import FinGPTPrediction
from algoforge.ml.orchestrator import MLPrediction
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.signals.models import SignalDirection

logger = logging.getLogger(__name__)


class ConvictionScore(BaseModel):
    """Composite conviction score breakdown.
    
    This model represents the final conviction score computed from all sources,
    along with a detailed breakdown of contributing factors.
    
    Attributes:
        total_conviction: Final composite conviction score in [0, 1]
        signal_score: Normalized signal score from Combination Engine
        ml_confidence: ML Pipeline confidence score
        fingpt_confidence: FinGPT confidence score (1.0 if not available)
        regime_alignment: Regime alignment score in [0, 1]
        components_breakdown: Detailed breakdown of all components
        decision: Trading decision based on conviction thresholds
    """
    
    total_conviction: float = Field(..., ge=0.0, le=1.0, description="Final conviction score")
    signal_score: float = Field(..., ge=0.0, le=1.0, description="Normalized signal score")
    ml_confidence: float = Field(..., ge=0.0, le=1.0, description="ML confidence")
    fingpt_confidence: float = Field(..., ge=0.0, le=1.0, description="FinGPT confidence")
    regime_alignment: float = Field(..., ge=0.0, le=1.0, description="Regime alignment score")
    components_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Detailed breakdown of conviction components"
    )
    decision: Literal["skip", "half_position", "full_position"] = Field(
        ...,
        description="Position sizing decision based on conviction"
    )


class ConfidenceAggregator:
    """Aggregates confidence scores from multiple sources.
    
    This class implements the confidence aggregation logic defined in Requirement 7
    of the AlgoForge System Integration spec. It computes a composite conviction
    score by multiplying confidence scores from:
    
    1. Combination Engine signal score (normalized to [0, 1])
    2. ML Pipeline confidence
    3. FinGPT confidence (if available)
    4. Regime alignment score
    
    The final conviction score determines position sizing:
    - < 0.3: Skip trade
    - 0.3 - 0.6: Half position (50%)
    - >= 0.6: Full position (100%)
    
    Example:
        >>> aggregator = ConfidenceAggregator()
        >>> conviction = aggregator.compute_conviction(
        ...     composite_signal=0.7,
        ...     ml_confidence=0.8,
        ...     fingpt_confidence=0.75,
        ...     regime_alignment=0.9
        ... )
        >>> print(f"Conviction: {conviction.total_conviction:.2f}")
        >>> print(f"Decision: {conviction.decision}")
    """
    
    def __init__(
        self,
        skip_threshold: float = 0.3,
        half_position_threshold: float = 0.6,
    ) -> None:
        """Initialize the Confidence Aggregator.
        
        Args:
            skip_threshold: Conviction below this value skips the trade (default: 0.3)
            half_position_threshold: Conviction above this value uses full position (default: 0.6)
        """
        self.skip_threshold = skip_threshold
        self.half_position_threshold = half_position_threshold
        
        logger.info(
            f"ConfidenceAggregator initialized: skip_threshold={skip_threshold}, "
            f"half_position_threshold={half_position_threshold}"
        )
    
    def compute_conviction(
        self,
        composite_signal: float,
        ml_confidence: float,
        fingpt_confidence: float,
        regime_alignment: float,
    ) -> ConvictionScore:
        """Compute composite conviction score from all sources.
        
        The conviction score is computed as the product of all confidence components:
        conviction = signal_score × ml_confidence × fingpt_confidence × regime_alignment
        
        Each component is expected to be in the range [0, 1].
        
        Args:
            composite_signal: Composite signal score from Combination Engine [-1, 1]
            ml_confidence: ML Pipeline confidence [0, 1]
            fingpt_confidence: FinGPT confidence [0, 1]
            regime_alignment: Regime alignment score [0, 1]
        
        Returns:
            ConvictionScore with total conviction and detailed breakdown
        
        Raises:
            ValueError: If any input is outside valid range
        """
        # Validate inputs
        if not -1.0 <= composite_signal <= 1.0:
            raise ValueError(f"composite_signal must be in [-1, 1], got {composite_signal}")
        if not 0.0 <= ml_confidence <= 1.0:
            raise ValueError(f"ml_confidence must be in [0, 1], got {ml_confidence}")
        if not 0.0 <= fingpt_confidence <= 1.0:
            raise ValueError(f"fingpt_confidence must be in [0, 1], got {fingpt_confidence}")
        if not 0.0 <= regime_alignment <= 1.0:
            raise ValueError(f"regime_alignment must be in [0, 1], got {regime_alignment}")
        
        # Normalize signal score to [0, 1] by taking absolute value
        # This represents the strength of the signal regardless of direction
        signal_score = abs(composite_signal)
        
        # Compute total conviction as product of all components
        total_conviction = signal_score * ml_confidence * fingpt_confidence * regime_alignment
        
        # Ensure result is in [0, 1] (should be guaranteed by inputs, but clip for safety)
        total_conviction = max(0.0, min(1.0, total_conviction))
        
        # Determine position sizing decision
        if total_conviction < self.skip_threshold:
            decision = "skip"
        elif total_conviction < self.half_position_threshold:
            decision = "half_position"
        else:
            decision = "full_position"
        
        # Build detailed breakdown
        components_breakdown = {
            "signal_score": signal_score,
            "ml_confidence": ml_confidence,
            "fingpt_confidence": fingpt_confidence,
            "regime_alignment": regime_alignment,
            "total_conviction": total_conviction,
        }
        
        logger.debug(
            f"Conviction computed: {total_conviction:.3f} -> {decision} "
            f"(signal={signal_score:.3f}, ml={ml_confidence:.3f}, "
            f"fingpt={fingpt_confidence:.3f}, regime={regime_alignment:.3f})"
        )
        
        return ConvictionScore(
            total_conviction=total_conviction,
            signal_score=signal_score,
            ml_confidence=ml_confidence,
            fingpt_confidence=fingpt_confidence,
            regime_alignment=regime_alignment,
            components_breakdown=components_breakdown,
            decision=decision,
        )
    
    def check_alignment(
        self,
        signal_direction: SignalDirection,
        ml_direction: str,
        fingpt_direction: str,
        regime: RegimeState,
    ) -> float:
        """Compute alignment score between different prediction sources.
        
        This method checks how well the signal direction aligns with:
        - ML Pipeline prediction direction
        - FinGPT prediction direction
        - Current market regime
        
        The alignment score is computed as the average of individual alignments:
        - ML alignment: 1.0 if directions match, 0.0 if opposite, 0.5 if neutral
        - FinGPT alignment: 1.0 if directions match, 0.0 if opposite, 0.5 if neutral
        - Regime alignment: 1.0 if signal matches regime, 0.5 if neutral regime, 0.0 if opposite
        
        Args:
            signal_direction: Direction from Combination Engine
            ml_direction: Direction from ML Pipeline ("long", "short", "neutral")
            fingpt_direction: Direction from FinGPT ("up", "down", "neutral")
            regime: Current market regime from HMM detector
        
        Returns:
            Alignment score in [0, 1] where 1.0 is perfect alignment
        """
        # Convert signal direction to comparable format
        if signal_direction == SignalDirection.LONG:
            signal_dir = "long"
        elif signal_direction == SignalDirection.SHORT:
            signal_dir = "short"
        else:
            signal_dir = "neutral"
        
        # Check ML alignment
        ml_alignment = self._compute_directional_alignment(signal_dir, ml_direction)
        
        # Check FinGPT alignment (convert "up"/"down" to "long"/"short")
        fingpt_dir_normalized = self._normalize_fingpt_direction(fingpt_direction)
        fingpt_alignment = self._compute_directional_alignment(signal_dir, fingpt_dir_normalized)
        
        # Check regime alignment
        regime_alignment = self._compute_regime_alignment(signal_dir, regime)
        
        # Average all alignments
        total_alignment = (ml_alignment + fingpt_alignment + regime_alignment) / 3.0
        
        logger.debug(
            f"Alignment check: signal={signal_dir}, ml={ml_direction}, "
            f"fingpt={fingpt_direction}, regime={regime.value} -> "
            f"ml_align={ml_alignment:.2f}, fingpt_align={fingpt_alignment:.2f}, "
            f"regime_align={regime_alignment:.2f}, total={total_alignment:.2f}"
        )
        
        return total_alignment
    
    def _compute_directional_alignment(self, dir1: str, dir2: str) -> float:
        """Compute alignment between two directions.
        
        Args:
            dir1: First direction ("long", "short", "neutral")
            dir2: Second direction ("long", "short", "neutral")
        
        Returns:
            Alignment score: 1.0 (match), 0.5 (neutral), 0.0 (opposite)
        """
        if dir1 == "neutral" or dir2 == "neutral":
            return 0.5
        elif dir1 == dir2:
            return 1.0
        else:
            return 0.0
    
    def _normalize_fingpt_direction(self, fingpt_direction: str) -> str:
        """Normalize FinGPT direction to standard format.
        
        Args:
            fingpt_direction: FinGPT direction ("up", "down", "neutral")
        
        Returns:
            Normalized direction ("long", "short", "neutral")
        """
        if fingpt_direction == "up":
            return "long"
        elif fingpt_direction == "down":
            return "short"
        else:
            return "neutral"
    
    def _compute_regime_alignment(self, signal_direction: str, regime: RegimeState) -> float:
        """Compute alignment between signal direction and market regime.
        
        Args:
            signal_direction: Signal direction ("long", "short", "neutral")
            regime: Current market regime
        
        Returns:
            Alignment score in [0, 1]
        """
        # Map regimes to preferred directions
        if regime == RegimeState.TREND_UP:
            if signal_direction == "long":
                return 1.0
            elif signal_direction == "short":
                return 0.0
            else:
                return 0.5
        
        elif regime == RegimeState.TREND_DOWN:
            if signal_direction == "short":
                return 1.0
            elif signal_direction == "long":
                return 0.0
            else:
                return 0.5
        
        elif regime == RegimeState.MEAN_REVERT:
            # Mean reversion regime is neutral - any direction is acceptable
            return 0.7
        
        elif regime == RegimeState.CRISIS:
            # Crisis regime - prefer no position or very cautious
            if signal_direction == "neutral":
                return 0.8
            else:
                return 0.3
        
        else:
            # Unknown regime - neutral alignment
            return 0.5
    
    def compute_conviction_from_objects(
        self,
        composite_signal: float,
        ml_prediction: MLPrediction | None,
        fingpt_prediction: FinGPTPrediction | None,
        regime_probs: RegimeProbabilities,
        signal_direction: SignalDirection,
    ) -> ConvictionScore:
        """Compute conviction from high-level objects.
        
        This is a convenience method that extracts the necessary values from
        prediction objects and computes the conviction score.
        
        Args:
            composite_signal: Composite signal score from Combination Engine
            ml_prediction: ML Pipeline prediction (None if not available)
            fingpt_prediction: FinGPT prediction (None if not available)
            regime_probs: Regime probabilities from HMM detector
            signal_direction: Signal direction from Combination Engine
        
        Returns:
            ConvictionScore with total conviction and breakdown
        """
        # Extract ML confidence
        ml_confidence = ml_prediction.confidence if ml_prediction else 1.0
        ml_direction = ml_prediction.direction if ml_prediction else "neutral"
        
        # Extract FinGPT confidence
        fingpt_confidence = fingpt_prediction.confidence if fingpt_prediction else 1.0
        fingpt_direction = fingpt_prediction.direction if fingpt_prediction else "neutral"
        
        # Get dominant regime
        regime = regime_probs.dominant_regime
        
        # Compute regime alignment
        regime_alignment = self.check_alignment(
            signal_direction=signal_direction,
            ml_direction=ml_direction,
            fingpt_direction=fingpt_direction,
            regime=regime,
        )
        
        # Compute conviction
        return self.compute_conviction(
            composite_signal=composite_signal,
            ml_confidence=ml_confidence,
            fingpt_confidence=fingpt_confidence,
            regime_alignment=regime_alignment,
        )
