"""ML/DL/RL Model Integration — Enhancement layer.

ML models are OPTIONAL enhancement layers, NOT replacements for
rule-based strategies. They adjust confidence scores but never
override risk management veto.

Requirements: ML-01 to ML-05
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import structlog
from pydantic import BaseModel, Field

from algoforge.core.models import Signal

logger = structlog.get_logger(__name__)


class MLPrediction(BaseModel):
    """ML model prediction output."""

    model_name: str
    confidence_adjustment: float = Field(default=0.0, ge=-0.3, le=0.3)
    predicted_direction: str = ""  # "long", "short", "neutral"
    features_used: list[str] = Field(default_factory=list)
    model_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class MLModel(ABC):
    """Abstract base for ML enhancement models.

    ML-01: Models enhance, never replace rule-based signals
    ML-02: Confidence adjustments capped at ±30%
    ML-03: Must have fallback when model unavailable
    ML-04: Feature extraction from indicators
    ML-05: Online learning support
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def predict(self, features: dict[str, float]) -> MLPrediction:
        """Generate prediction from features."""
        ...

    def is_available(self) -> bool:
        """Check if model is loaded and ready."""
        return True


class EnsembleML:
    """Ensemble of ML models for signal enhancement.

    Aggregates predictions from multiple models and applies
    a weighted average confidence adjustment.

    Usage:
        ensemble = EnsembleML()
        ensemble.add_model(model, weight=1.0)
        enhanced = ensemble.enhance_signals(signals, features)
    """

    def __init__(self, max_adjustment: float = 0.2) -> None:
        self._models: list[tuple[MLModel, float]] = []
        self._max_adj = max_adjustment

    def add_model(self, model: MLModel, weight: float = 1.0) -> None:
        """Add a model to the ensemble."""
        self._models.append((model, weight))

    def enhance_signals(
        self, signals: list[Signal], features: dict[str, float],
    ) -> list[Signal]:
        """Enhance signals with ML predictions.

        ML-01: Enhancement only — never creates new signals.
        ML-02: Adjustments capped.
        ML-03: Graceful degradation when models unavailable.
        """
        if not self._models:
            return signals

        enhanced = []
        for sig in signals:
            total_adj = 0.0
            total_weight = 0.0

            for model, weight in self._models:
                if not model.is_available():
                    continue

                try:
                    pred = model.predict(features)
                    total_adj += pred.confidence_adjustment * weight
                    total_weight += weight
                except Exception as e:
                    logger.warning("ml_model_error", model=model.name, error=str(e))

            if total_weight > 0:
                avg_adj = total_adj / total_weight
                # ML-02: Cap the adjustment
                capped = max(-self._max_adj, min(self._max_adj, avg_adj))
                new_conf = max(0.1, min(0.95, sig.confidence + capped))
                enhanced.append(sig.model_copy(update={"confidence": new_conf}))
            else:
                # ML-03: Fallback when no models available
                enhanced.append(sig)

        logger.info(
            "ml_enhance",
            input_count=len(signals),
            models_active=sum(1 for m, _ in self._models if m.is_available()),
        )
        return enhanced

    @property
    def model_count(self) -> int:
        return len(self._models)


class DummyTrendModel(MLModel):
    """Simple trend-following model for testing."""

    @property
    def name(self) -> str:
        return "dummy_trend"

    def predict(self, features: dict[str, float]) -> MLPrediction:
        adx = features.get("adx", 20)
        rsi = features.get("rsi", 50)

        # Higher ADX → higher confidence boost
        adj = (adx - 25) / 100  # 25 ADX → 0 adj, 35 → +0.1
        adj = max(-0.1, min(0.1, adj))

        direction = "long" if rsi < 50 else "short"

        return MLPrediction(
            model_name=self.name,
            confidence_adjustment=adj,
            predicted_direction=direction,
            features_used=["adx", "rsi"],
            model_confidence=0.6,
        )
