"""ML Pipeline Orchestrator for coordinating ML model predictions.

This module orchestrates the ML enhancement layer, coordinating predictions from:
- XGBoost classifier (GBMClassifier)
- LSTM forecaster (placeholder for future implementation)
- Ensemble meta-model (StackingEnsemble)
- FinGPT integration (optional)

The orchestrator computes features, generates predictions, and provides
comprehensive ML prediction output for signal enhancement.
"""

import logging
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from algoforge.ml.ensemble import StackingEnsemble
from algoforge.ml.features import FeatureBuilder
from algoforge.ml.models import GBMClassifier

logger = logging.getLogger(__name__)


class MLConfig(BaseModel):
    """Configuration for ML Pipeline Orchestrator."""
    
    enable_xgboost: bool = True
    enable_lstm: bool = False  # Not yet implemented
    enable_ensemble: bool = True
    enable_fingpt: bool = False  # Requires FinGPT client
    
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_confidence_adjustment: float = Field(default=0.15, ge=0.0, le=0.5)
    
    # Model hyperparameters
    xgboost_params: dict = Field(default_factory=dict)
    lstm_params: dict = Field(default_factory=dict)


class MLPrediction(BaseModel):
    """ML pipeline prediction output."""
    
    direction: Literal["long", "short", "neutral"]
    probability: float = Field(ge=0.0, le=1.0)  # Probability of predicted direction
    confidence: float = Field(ge=0.0, le=1.0)  # Overall confidence in prediction
    xgboost_score: float = Field(ge=-1.0, le=1.0)  # XGBoost signal score
    lstm_forecast: list[float] = Field(default_factory=list)  # LSTM multi-step forecast
    ensemble_score: float = Field(ge=-1.0, le=1.0)  # Final ensemble score
    feature_importance: dict[str, float] = Field(default_factory=dict)  # Top features
    
    class Config:
        """Pydantic config."""
        frozen = False


class MLPipelineOrchestrator:
    """Orchestrates ML model predictions and ensemble.
    
    This class coordinates multiple ML models to generate enhanced predictions:
    1. Computes engineered features from market data
    2. Generates XGBoost classification predictions
    3. Generates LSTM forecasts (placeholder)
    4. Combines predictions using ensemble meta-model
    5. Integrates FinGPT predictions if available
    
    The orchestrator is designed to work with the existing AlgoForge signal
    framework and can be integrated into the main trading loop.
    """
    
    def __init__(self, config: MLConfig | None = None):
        """Initialize the ML Pipeline Orchestrator.
        
        Args:
            config: Configuration for ML models and behavior.
        """
        self.config = config or MLConfig()
        
        # Initialize models
        self.xgboost_model = GBMClassifier(self.config.xgboost_params) if self.config.enable_xgboost else None
        self.lstm_model = None  # Placeholder for future LSTM implementation
        self.ensemble_model = StackingEnsemble() if self.config.enable_ensemble else None
        self.feature_engineer = FeatureBuilder()
        
        self._is_trained = False
        
        logger.info(
            "MLPipelineOrchestrator initialized: xgboost=%s, lstm=%s, ensemble=%s",
            self.config.enable_xgboost,
            self.config.enable_lstm,
            self.config.enable_ensemble,
        )
    
    def is_trained(self) -> bool:
        """Check if the orchestrator has trained models."""
        return self._is_trained
    
    def train(
        self,
        features: np.ndarray,
        y_class: np.ndarray,
        y_return: np.ndarray,
    ) -> None:
        """Train all enabled ML models.
        
        Args:
            features: Feature matrix (n_samples, n_features).
            y_class: Classification labels {-1, 0, +1}.
            y_return: Continuous forward return labels.
        """
        if self.config.enable_xgboost and self.xgboost_model is not None:
            logger.info("Training XGBoost classifier...")
            self.xgboost_model.fit(features, y_class)
        
        if self.config.enable_lstm and self.lstm_model is not None:
            logger.info("Training LSTM forecaster...")
            # TODO: Implement LSTM training when model is available
            pass
        
        if self.config.enable_ensemble and self.ensemble_model is not None:
            logger.info("Training ensemble meta-model...")
            self.ensemble_model.fit(features, y_class, y_return)
        
        self._is_trained = True
        logger.info("ML Pipeline training completed")
    
    async def generate_prediction(
        self,
        symbol: str,
        bars: pd.DataFrame,
        indicators: dict[str, float],
        fingpt_pred: "FinGPTPrediction | None" = None,  # type: ignore
    ) -> MLPrediction:
        """Generate ensemble ML prediction.
        
        Args:
            symbol: Trading symbol.
            bars: Historical price bars (OHLCV data).
            indicators: Dictionary of computed technical indicators.
            fingpt_pred: Optional FinGPT prediction for integration.
        
        Returns:
            MLPrediction with comprehensive prediction output.
        
        Raises:
            RuntimeError: If models are not trained.
        """
        if not self._is_trained:
            raise RuntimeError("ML models not trained. Call train() first.")
        
        # Compute features
        features = self.compute_features(bars, indicators)
        
        # Ensure features are 2D
        if features.ndim == 1:
            features = features.reshape(1, -1)
        
        # Initialize prediction components
        xgboost_score = 0.0
        lstm_forecast = []
        ensemble_score = 0.0
        
        # XGBoost prediction
        if self.config.enable_xgboost and self.xgboost_model is not None:
            xgboost_score = float(self.xgboost_model.predict_signal(features)[0])
        
        # LSTM prediction (placeholder)
        if self.config.enable_lstm and self.lstm_model is not None:
            # TODO: Implement LSTM prediction when model is available
            lstm_forecast = [0.0] * 5  # Placeholder for 5-step forecast
        
        # Ensemble prediction
        if self.config.enable_ensemble and self.ensemble_model is not None:
            ensemble_score = float(self.ensemble_model.predict(features)[0])
        else:
            # Fallback to XGBoost if ensemble not available
            ensemble_score = xgboost_score
        
        # Integrate FinGPT prediction if available
        if fingpt_pred is not None and self.config.enable_fingpt:
            # Adjust ensemble score based on FinGPT direction alignment
            fingpt_direction_score = self._fingpt_to_score(fingpt_pred)
            # Weighted average: 70% ensemble, 30% FinGPT
            ensemble_score = 0.7 * ensemble_score + 0.3 * fingpt_direction_score
        
        # Determine direction and probability
        direction = self._score_to_direction(ensemble_score)
        probability = self._score_to_probability(ensemble_score)
        
        # Compute confidence based on score magnitude and consistency
        confidence = self._compute_confidence(
            ensemble_score,
            xgboost_score,
            fingpt_pred,
        )
        
        # Get feature importance
        feature_importance = self._get_feature_importance()
        
        return MLPrediction(
            direction=direction,
            probability=probability,
            confidence=confidence,
            xgboost_score=xgboost_score,
            lstm_forecast=lstm_forecast,
            ensemble_score=ensemble_score,
            feature_importance=feature_importance,
        )
    
    def compute_features(
        self,
        bars: pd.DataFrame,
        indicators: dict[str, float],
    ) -> np.ndarray:
        """Compute 44+ engineered features from market data.
        
        Args:
            bars: Historical price bars with OHLCV data.
            indicators: Dictionary of computed technical indicators.
        
        Returns:
            Numpy array of engineered features.
        """
        # Extract signal scores from indicators (if available)
        signal_scores = {
            "momentum": indicators.get("momentum_score", 0.0),
            "mean_reversion": indicators.get("mean_reversion_score", 0.0),
            "breakout": indicators.get("breakout_score", 0.0),
            "regime": indicators.get("regime_score", 0.0),
            "microstructure": indicators.get("microstructure_score", 0.0),
            "pairs": indicators.get("pairs_score", 0.0),
        }
        
        # Extract regime probabilities (if available)
        regime_probs = {
            "bull": indicators.get("regime_bull", 0.33),
            "bear": indicators.get("regime_bear", 0.33),
            "sideways": indicators.get("regime_sideways", 0.34),
        }
        
        # Compute returns from bars
        if len(bars) >= 20:
            closes = bars["close"].values
            returns_1 = (closes[-1] - closes[-2]) / closes[-2] if len(closes) >= 2 else 0.0
            returns_5 = (closes[-1] - closes[-6]) / closes[-6] if len(closes) >= 6 else 0.0
            returns_10 = (closes[-1] - closes[-11]) / closes[-11] if len(closes) >= 11 else 0.0
            returns_20 = (closes[-1] - closes[-21]) / closes[-21] if len(closes) >= 21 else 0.0
            
            # Compute volatility
            volatility_5 = float(np.std(closes[-5:])) if len(closes) >= 5 else 0.0
            volatility_20 = float(np.std(closes[-20:])) if len(closes) >= 20 else 0.0
        else:
            returns_1 = returns_5 = returns_10 = returns_20 = 0.0
            volatility_5 = volatility_20 = 0.0
        
        # Extract time features
        if len(bars) > 0:
            last_timestamp = bars.index[-1] if isinstance(bars.index, pd.DatetimeIndex) else pd.Timestamp.now()
            hour = last_timestamp.hour
            day_of_week = last_timestamp.dayofweek
            month = last_timestamp.month
        else:
            hour = 12
            day_of_week = 2
            month = 6
        
        # Build feature vector using FeatureBuilder
        features = FeatureBuilder.build(
            signal_scores=signal_scores,
            regime_probs=regime_probs,
            bars_since_regime_change=indicators.get("bars_since_regime_change", 0),
            vwap_deviation=indicators.get("vwap_deviation", 0.0),
            volume_imbalance=indicators.get("volume_imbalance", 0.0),
            obv_score=indicators.get("obv_score", 0.0),
            volume_ratio=indicators.get("volume_ratio", 1.0),
            returns_1=returns_1,
            returns_5=returns_5,
            returns_10=returns_10,
            returns_20=returns_20,
            volatility_5=volatility_5,
            volatility_20=volatility_20,
            atr_ratio=indicators.get("atr_ratio", 1.0),
            momentum=indicators.get("momentum", 0.0),
            benchmark_corr=indicators.get("benchmark_corr", 0.0),
            relative_strength=indicators.get("relative_strength", 0.0),
            spread_z=indicators.get("spread_z", 0.0),
            sector_momentum=indicators.get("sector_momentum", 0.0),
            hour=hour,
            day_of_week=day_of_week,
            month=month,
        )
        
        return features
    
    def _score_to_direction(self, score: float) -> Literal["long", "short", "neutral"]:
        """Convert ensemble score to direction.
        
        Args:
            score: Ensemble score in [-1.0, 1.0].
        
        Returns:
            Direction: "long", "short", or "neutral".
        """
        if score > 0.1:
            return "long"
        elif score < -0.1:
            return "short"
        else:
            return "neutral"
    
    def _score_to_probability(self, score: float) -> float:
        """Convert ensemble score to probability.
        
        Args:
            score: Ensemble score in [-1.0, 1.0].
        
        Returns:
            Probability in [0.0, 1.0].
        """
        # Map [-1, 1] to [0, 1] using sigmoid-like transformation
        # Neutral (0) -> 0.5, Strong long (1) -> ~0.88, Strong short (-1) -> ~0.12
        return float(1.0 / (1.0 + np.exp(-3.0 * score)))
    
    def _compute_confidence(
        self,
        ensemble_score: float,
        xgboost_score: float,
        fingpt_pred: "FinGPTPrediction | None",  # type: ignore
    ) -> float:
        """Compute overall confidence in the prediction.
        
        Confidence is based on:
        1. Magnitude of ensemble score (stronger signals = higher confidence)
        2. Agreement between XGBoost and ensemble
        3. FinGPT confidence if available
        
        Args:
            ensemble_score: Final ensemble score.
            xgboost_score: XGBoost model score.
            fingpt_pred: Optional FinGPT prediction.
        
        Returns:
            Confidence in [0.0, 1.0].
        """
        # Base confidence from score magnitude
        base_confidence = abs(ensemble_score)
        
        # Boost confidence if XGBoost and ensemble agree
        if abs(xgboost_score - ensemble_score) < 0.3:
            base_confidence *= 1.1
        else:
            base_confidence *= 0.9
        
        # Integrate FinGPT confidence if available
        if fingpt_pred is not None and self.config.enable_fingpt:
            fingpt_confidence = getattr(fingpt_pred, "confidence", 0.5)
            # Weighted average: 70% base, 30% FinGPT
            base_confidence = 0.7 * base_confidence + 0.3 * fingpt_confidence
        
        # Ensure confidence is in [0, 1]
        return float(np.clip(base_confidence, 0.0, 1.0))
    
    def _fingpt_to_score(self, fingpt_pred: "FinGPTPrediction") -> float:  # type: ignore
        """Convert FinGPT prediction to a score in [-1, 1].
        
        Args:
            fingpt_pred: FinGPT prediction object.
        
        Returns:
            Score in [-1.0, 1.0].
        """
        direction = getattr(fingpt_pred, "direction", "neutral")
        confidence = getattr(fingpt_pred, "confidence", 0.5)
        
        if direction == "up":
            return confidence
        elif direction == "down":
            return -confidence
        else:
            return 0.0
    
    def _get_feature_importance(self, top_n: int = 10) -> dict[str, float]:
        """Get top N most important features.
        
        Args:
            top_n: Number of top features to return.
        
        Returns:
            Dictionary mapping feature names to importance scores.
        """
        if self.xgboost_model is None:
            return {}
        
        importance = self.xgboost_model.feature_importance
        if importance is None or len(FeatureBuilder.FEATURE_NAMES) != len(importance):
            return {}
        
        # Sort by importance and take top N
        feature_imp = {
            name: float(imp)
            for name, imp in zip(FeatureBuilder.FEATURE_NAMES, importance)
        }
        
        sorted_features = sorted(
            feature_imp.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        return dict(sorted_features[:top_n])
