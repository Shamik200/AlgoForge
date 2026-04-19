"""Core Momentum Signal class combining sub-signals and regime adaptation."""

import numpy as np

from algoforge.core.models import OHLCVSeries
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.signals.momentum.evaluator import (
    check_atr_percentile,
    check_volume_confirmation,
    time_series_momentum,
)
from algoforge.signals.momentum.vwap import calculate_vwap, vwap_momentum_score


class MomentumSignal:
    """Generates the Momentum signal family output.
    
    Combines:
    - Time-Series Momentum (Trailing return)
    - Intraday VWAP Momentum (Deviation from session VWAP)
    - Regime Boost (1.3x multiplier if regime aligns)
    - Filters: Volume ROC, ATR Percentiles, KAMA Trend Direction.
    """

    def __init__(
        self,
        tsmom_lookback: int = 252,
        tsmom_skip: int = 21,
        regime_boost: float = 1.3,
    ) -> None:
        """Initialize the Momentum Signal.
        
        Args:
            tsmom_lookback: Lookback for time-series momentum.
            tsmom_skip: Recent period to skip for time-series momentum.
            regime_boost: Multiplier applied when regime supports the signal.
        """
        self.tsmom_lookback = tsmom_lookback
        self.tsmom_skip = tsmom_skip
        self.regime_boost = regime_boost

    def evaluate(
        self,
        series: OHLCVSeries,
        kama: float,
        atr_series: np.ndarray,
        regime_probs: RegimeProbabilities | None = None,
    ) -> SignalResult:
        """Evaluate the momentum signal for the given series.
        
        Args:
            series: OHLCV series.
            kama: Latest KAMA value for trend confirmation.
            atr_series: Historical ATR array for percentile filtering.
            regime_probs: Optional Regime Probabilities for the regime boost.
            
        Returns:
            A standardized SignalResult.
        """
        if series.is_empty or len(series.closes) < 2:
            return SignalResult(
                family_name="momentum",
                score=0.0,
                direction=SignalDirection.NEUTRAL,
                is_valid=False,
                metadata={"reason": "insufficient_data"}
            )
            
        closes = np.array(series.closes, dtype=np.float64)
        volumes = np.array(series.volumes, dtype=np.float64)
        latest_close = closes[-1]
        
        # 1. Compute Sub-Signals
        ts_score = time_series_momentum(closes, self.tsmom_lookback, self.tsmom_skip)
        
        vwap_series = calculate_vwap(series)
        latest_vwap = vwap_series[-1] if len(vwap_series) > 0 else latest_close
        vwap_score = vwap_momentum_score(latest_close, latest_vwap)
        
        # 2. Combine Scores (Equal-weighting D-03)
        raw_composite = (ts_score + vwap_score) / 2.0
        
        # Determine raw direction
        if raw_composite > 0.05:
            direction = SignalDirection.LONG
        elif raw_composite < -0.05:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL
            
        # 3. Confirmation Filters
        is_valid = True
        metadata: dict[str, str | float | bool] = {}
        
        # Filter A: ATR Percentile Check
        if not check_atr_percentile(atr_series):
            is_valid = False
            metadata["filter_failed"] = "atr_percentile"
            
        # Filter B: Volume Confirmation
        if not check_volume_confirmation(volumes):
            is_valid = False
            metadata["filter_failed"] = "volume_roc"
            
        # Filter C: KAMA Agreement
        if not np.isnan(kama) and kama > 0:
            if direction == SignalDirection.LONG and latest_close < kama:
                is_valid = False
                metadata["filter_failed"] = "kama_conflict_long"
            elif direction == SignalDirection.SHORT and latest_close > kama:
                is_valid = False
                metadata["filter_failed"] = "kama_conflict_short"
                
        # 4. Regime Adaptation (D-03)
        final_score = raw_composite
        
        if regime_probs is not None and not regime_probs.uncertainty_flag:
            dom_regime = regime_probs.dominant_regime
            
            # Boost score if regime aligns with signal direction
            if direction == SignalDirection.LONG and dom_regime == RegimeState.TREND_UP:
                final_score *= self.regime_boost
                metadata["regime_boost"] = True
            elif direction == SignalDirection.SHORT and dom_regime == RegimeState.TREND_DOWN:
                final_score *= self.regime_boost
                metadata["regime_boost"] = True
                
        # Hard-clip to [-1.0, 1.0]
        final_score = float(np.clip(final_score, -1.0, 1.0))
        
        return SignalResult(
            family_name="momentum",
            score=final_score,
            direction=direction,
            is_valid=is_valid,
            sub_scores={"time_series": ts_score, "vwap": vwap_score},
            metadata=metadata
        )
