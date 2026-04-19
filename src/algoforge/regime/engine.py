"""Runtime inference engine for the HMM Regime Detector."""

from pathlib import Path

import numpy as np

from algoforge.core.models import OHLCVSeries
from algoforge.regime.features import build_features, smooth_features
from algoforge.regime.models import RegimeProbabilities
from algoforge.regime.trainer import HMMTrainer


class RegimeEngine:
    """Runtime engine for predicting market regimes via HMM.
    
    Loads a pre-trained model and evaluates new OHLCV data to produce
    a smooth probability vector across 4 hidden states.
    """

    def __init__(
        self,
        model_dir: str | Path,
        model_name: str = "regime_hmm",
        smoothing_period: int = 5,
        entropy_threshold: float = 1.2,
    ) -> None:
        """Initialize the inference engine.
        
        Args:
            model_dir: Path to the directory containing the saved model/scaler.
            model_name: Base name of the saved model files.
            smoothing_period: Period for the fast EMA applied to features before inference.
            entropy_threshold: Probability entropy threshold above which the 
                uncertainty flag is raised. Maximum entropy for 4 states is ~1.38.
        """
        self.model_dir = Path(model_dir)
        self.model_name = model_name
        self.smoothing_period = smoothing_period
        self.entropy_threshold = entropy_threshold
        
        # Load the trainer instance which holds the model and scaler
        self.trainer = HMMTrainer.load(self.model_dir, self.model_name)
        
        # We need to map the arbitrary HMM states (0, 1, 2, 3) to our semantic RegimeStates.
        # This mapping should ideally be determined during offline training by analyzing 
        # the state means (e.g., state with highest return mean = TREND_UP).
        # For this implementation, we'll assume the states are ordered or we use a basic heuristic.
        self._state_mapping = self._determine_state_mapping()

    def _determine_state_mapping(self) -> dict[int, str]:
        """Map the HMM hidden states to semantic regime names.
        
        Analyzes the learned means of the HMM to map states to:
        trend_up, trend_down, mean_revert, crisis.
        
        Feature order assumed: [returns, realized_vol, vol_ratio]
        """
        means = self.trainer.model.means_
        mapping = {}
        
        if means.shape[1] >= 2:
            # Simple heuristic based on returns and volatility
            returns_col = means[:, 0]
            vol_col = means[:, 1]
            
            # Highest vol is crisis
            crisis_state = int(np.argmax(vol_col))
            
            # Mask crisis state
            masked_returns = returns_col.copy()
            masked_returns[crisis_state] = -np.inf
            
            # Highest remaining return is trend_up
            trend_up_state = int(np.argmax(masked_returns))
            
            # Lowest return is trend_down
            masked_returns = returns_col.copy()
            masked_returns[crisis_state] = np.inf
            trend_down_state = int(np.argmin(masked_returns))
            
            # The remaining state is mean_revert
            all_states = {0, 1, 2, 3}
            assigned = {crisis_state, trend_up_state, trend_down_state}
            remaining = all_states - assigned
            mean_revert_state = int(remaining.pop()) if remaining else 0
            
            mapping[trend_up_state] = "trend_up"
            mapping[trend_down_state] = "trend_down"
            mapping[mean_revert_state] = "mean_revert"
            mapping[crisis_state] = "crisis"
        else:
            # Fallback
            mapping = {0: "trend_up", 1: "trend_down", 2: "mean_revert", 3: "crisis"}
            
        return mapping

    def _calculate_entropy(self, probs: np.ndarray) -> float:
        """Calculate Shannon entropy of the probability vector.
        
        Args:
            probs: 1D array of probabilities summing to 1.
            
        Returns:
            Entropy value.
        """
        # Avoid log(0)
        safe_probs = np.clip(probs, 1e-10, 1.0)
        return float(-np.sum(safe_probs * np.log(safe_probs)))

    def compute(
        self, 
        series: OHLCVSeries, 
        cross_asset_features: np.ndarray | None = None,
        current_vix: float | None = None
    ) -> RegimeProbabilities | None:
        """Compute the current market regime probabilities.
        
        Args:
            series: OHLCV series.
            cross_asset_features: Optional aligned cross-asset features.
            current_vix: Current VIX value for hard heuristic checks.
            
        Returns:
            RegimeProbabilities model or None if insufficient data.
        """
        if series.is_empty:
            return None
            
        # 1. Build features
        raw_features = build_features(series, cross_asset_features)
        if raw_features.shape[0] == 0:
            return None
            
        # 2. Smooth features (D-01)
        smoothed_features = smooth_features(raw_features, period=self.smoothing_period)
        
        # We only need to predict for the latest bar
        # In practice, HMM prediction (Viterbi or forward-backward) requires the sequence.
        # We will scale the sequence, predict, and take the last probabilities.
        scaled_features = self.trainer.scaler.transform(smoothed_features)
        
        try:
            # predict_proba returns (n_samples, n_components)
            all_probs = self.trainer.model.predict_proba(scaled_features)
            latest_probs = all_probs[-1]
        except Exception:
            return None
            
        # 3. Map probabilities to semantic regimes
        mapped_probs = {
            "trend_up": 0.0,
            "trend_down": 0.0,
            "mean_revert": 0.0,
            "crisis": 0.0,
        }
        
        for state_idx, prob in enumerate(latest_probs):
            semantic_name = self._state_mapping.get(state_idx, "mean_revert")
            mapped_probs[semantic_name] = float(prob)
            
        # 4. Uncertainty Flag (D-04)
        entropy = self._calculate_entropy(latest_probs)
        uncertainty = entropy > self.entropy_threshold
        
        # Hard VIX conflict check
        if current_vix is not None and current_vix > 30.0:
            # If VIX is extreme fear, but model is highly confident in an uptrend
            if mapped_probs["trend_up"] > 0.6:
                uncertainty = True
                
        return RegimeProbabilities(
            trend_up=mapped_probs["trend_up"],
            trend_down=mapped_probs["trend_down"],
            mean_revert=mapped_probs["mean_revert"],
            crisis=mapped_probs["crisis"],
            uncertainty_flag=uncertainty
        )
