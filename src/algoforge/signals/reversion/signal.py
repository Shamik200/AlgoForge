"""Core Mean Reversion Signal class."""

import numpy as np

from algoforge.core.models import OHLCVSeries
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.signals.reversion.divergence import (
    detect_rsi_divergence,
    evaluate_bollinger_divergence,
)
from algoforge.signals.reversion.pairs import evaluate_pairs_stub
from algoforge.signals.reversion.vwap_zscore import (
    calculate_rolling_vwap,
    vwap_zscore,
)


class MeanReversionSignal:
    """Generates the Mean Reversion signal family output.
    
    Combines:
    - Rolling VWAP Z-Score (40%)
    - Bollinger %B + RSI Divergence (30%)
    - Pairs Trading Stub (30%)
    
    Guarded by Regime Probabilities and extreme Momentum scores.
    """

    def __init__(self, vwap_period: int = 20, regime_boost: float = 1.3) -> None:
        """Initialize the Mean Reversion Signal.
        
        Args:
            vwap_period: Lookback for the rolling VWAP.
            regime_boost: Multiplier when regime is MEAN_REVERT.
        """
        self.vwap_period = vwap_period
        self.regime_boost = regime_boost

    def evaluate(
        self,
        series: OHLCVSeries,
        rsi_series: np.ndarray,
        bb_upper: float,
        bb_lower: float,
        regime_probs: RegimeProbabilities | None = None,
        momentum_score: float | None = None,
    ) -> SignalResult:
        """Evaluate the mean reversion signal.
        
        Args:
            series: OHLCV data series.
            rsi_series: Array of RSI values for divergence detection.
            bb_upper: Current Bollinger Upper Band value.
            bb_lower: Current Bollinger Lower Band value.
            regime_probs: HMM Regime predictions.
            momentum_score: Raw momentum score ([-1.0, 1.0]) for anti-trend guard.
            
        Returns:
            A standardized SignalResult.
        """
        metadata: dict[str, str | float | bool] = {}
        
        # 1. Anti-Trend Steamroller Guard
        # If momentum is strongly trending, do not try to mean-revert.
        if momentum_score is not None and abs(momentum_score) > 0.80:
            return SignalResult(
                family_name="mean_reversion",
                score=0.0,
                direction=SignalDirection.NEUTRAL,
                is_valid=False,
                metadata={"filter_failed": "anti_trend_guard", "momentum_score": momentum_score}
            )
            
        # 2. Regime Guard
        # Only active if Mean Reverting probability is >= 40%
        if regime_probs is not None:
            if regime_probs.mean_revert < 0.40:
                return SignalResult(
                    family_name="mean_reversion",
                    score=0.0,
                    direction=SignalDirection.NEUTRAL,
                    is_valid=False,
                    metadata={"filter_failed": "regime_guard_too_low", "prob": regime_probs.mean_revert}
                )
                
        if series.is_empty or len(series.closes) < self.vwap_period:
            return SignalResult(
                family_name="mean_reversion",
                score=0.0,
                direction=SignalDirection.NEUTRAL,
                is_valid=False,
                metadata={"filter_failed": "insufficient_data"}
            )
            
        closes = np.array(series.closes, dtype=np.float64)
        latest_close = closes[-1]
        
        # 3. Compute VWAP Score (40%)
        vwaps = calculate_rolling_vwap(series, self.vwap_period)
        score_vwap = vwap_zscore(closes, vwaps, self.vwap_period)
        
        # 4. Compute Bollinger + Divergence Score (30%)
        div_score = detect_rsi_divergence(closes, rsi_series, lookback=100)
        score_bb_div = evaluate_bollinger_divergence(latest_close, bb_upper, bb_lower, div_score)
        
        # 5. Compute Pairs Score (30%)
        score_pairs = evaluate_pairs_stub(series)
        
        # 6. Composite Score
        raw_composite = (score_vwap * 0.40) + (score_bb_div * 0.30) + (score_pairs * 0.30)
        
        if raw_composite > 0.05:
            direction = SignalDirection.LONG
        elif raw_composite < -0.05:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL
            
        # 7. Regime Boost
        final_score = raw_composite
        if regime_probs is not None and not regime_probs.uncertainty_flag:
            if regime_probs.dominant_regime == RegimeState.MEAN_REVERT:
                final_score *= self.regime_boost
                metadata["regime_boost"] = True
                
        # 8. Format Output
        final_score = float(np.clip(final_score, -1.0, 1.0))
        
        return SignalResult(
            family_name="mean_reversion",
            score=final_score,
            direction=direction,
            is_valid=True,
            sub_scores={"vwap_z": score_vwap, "bb_div": score_bb_div, "pairs": score_pairs},
            metadata=metadata
        )
