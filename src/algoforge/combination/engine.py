"""Signal Combination Engine Orchestrator."""

from algoforge.combination.correlation import SignalCorrelationMatrix, cull_redundant_signals
from algoforge.combination.normalization import RollingNormalizer
from algoforge.combination.weighting import calculate_softmax_weights
from algoforge.signals.models import SignalDirection, SignalResult


class CombinationEngine:
    """The master Signal Combination & Conviction Framework.
    
    Ingests independent signal family outputs, normalizes them, 
    removes highly correlated redundancies, weights them by Sharpe ratio,
    and produces a composite conviction score bounded to [-1.0, 1.0].
    """
    
    def __init__(self, norm_window: int = 100, corr_window: int = 30, max_corr: float = 0.70) -> None:
        """Initialize the Combination Engine.
        
        Args:
            norm_window: Lookback window for z-score normalization.
            corr_window: Lookback window for pairwise correlation tracking.
            max_corr: Threshold above which the weaker signal is dropped.
        """
        self.normalizer = RollingNormalizer(window_size=norm_window)
        self.correlation_matrix = SignalCorrelationMatrix(window_size=corr_window)
        self.max_corr = max_corr
        
    def combine(
        self, 
        signals: list[SignalResult], 
        sharpe_ratios: dict[str, float],
        health_multipliers: dict[str, float] | None = None
    ) -> SignalResult:
        """Combine multiple independent signal results into a master composite.
        
        Args:
            signals: List of SignalResult objects from the individual signal families.
            sharpe_ratios: Dictionary mapping family names to their rolling Sharpe ratios.
            health_multipliers: Dictionary mapping family names to Alpha Decay multipliers (0.0 to 1.0).
            
        Returns:
            A SignalResult object representing the combined conviction.
        """
        if not signals:
            return SignalResult(
                family_name="composite", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"error": "no_signals_provided"}
            )
            
        valid_signals = [s for s in signals if s.is_valid]
        if not valid_signals:
            return SignalResult(
                family_name="composite", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"error": "no_valid_signals"}
            )
            
        # 1. Normalize Scores & Track for Correlation
        normalized_scores: dict[str, float] = {}
        
        for sig in valid_signals:
            # Add raw score to history
            self.normalizer.add_score(sig.family_name, sig.score)
            
            # Get normalized z-score
            norm_score = self.normalizer.get_normalized_score(sig.family_name, sig.score)
            normalized_scores[sig.family_name] = norm_score
            
        # Add the normalized cross-section to the correlation tracker
        self.correlation_matrix.add_signals(normalized_scores)
        
        # Filter Sharpe ratios to only those with valid signals present
        active_sharpes = {
            sig.family_name: sharpe_ratios.get(sig.family_name, 0.0) 
            for sig in valid_signals
        }
        
        # 2. Correlation Tie-Breaker Cull
        culled_sharpes = cull_redundant_signals(
            active_sharpes, self.correlation_matrix, self.max_corr
        )
        
        if not culled_sharpes:
            return SignalResult(
                family_name="composite", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"error": "all_signals_culled"}
            )
            
        # 3. Adaptive Softmax Weighting
        weights = calculate_softmax_weights(culled_sharpes)
        
        # 3.5 Apply Alpha Decay Health Multipliers & Re-normalize
        if health_multipliers:
            throttled_weights = {}
            for family, weight in weights.items():
                mult = health_multipliers.get(family, 1.0)
                throttled_weights[family] = weight * mult
                
            total_weight = sum(throttled_weights.values())
            if total_weight > 0:
                weights = {f: w / total_weight for f, w in throttled_weights.items()}
            else:
                return SignalResult(
                    family_name="composite", score=0.0, direction=SignalDirection.NEUTRAL,
                    is_valid=False, metadata={"error": "all_signals_paused_by_decay_monitor"}
                )
        
        # 4. Composite Calculation
        composite_score = 0.0
        applied_weights = {}
        
        for family, weight in weights.items():
            composite_score += normalized_scores[family] * weight
            applied_weights[family] = weight
            
        # Determine master direction
        direction = SignalDirection.NEUTRAL
        if composite_score > 0:
            direction = SignalDirection.LONG
        elif composite_score < 0:
            direction = SignalDirection.SHORT
            
        # The composite_score is guaranteed to be in [-1.0, 1.0] because
        # the normalized scores are bounded, and weights sum to 1.0.
        
        import json
        return SignalResult(
            family_name="composite",
            score=composite_score,
            direction=direction,
            is_valid=True,
            metadata={
                "weights": json.dumps(applied_weights),
                "raw_scores": json.dumps({s.family_name: s.score for s in valid_signals}),
                "normalized_scores": json.dumps(normalized_scores),
                "culled_families": json.dumps(list(set(active_sharpes.keys()) - set(culled_sharpes.keys())))
            }
        )
