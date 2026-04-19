"""HMM Probabilistic Regime Detector.

Provides a 4-state Hidden Markov Model that classifies market regimes into 
continuous probability vectors. Includes offline retraining and runtime inference.
"""

from algoforge.regime.engine import RegimeEngine
from algoforge.regime.features import build_features, forward_fill_cross_asset, smooth_features
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.regime.trainer import HMMTrainer

__all__ = [
    "HMMTrainer",
    "RegimeEngine",
    "RegimeProbabilities",
    "RegimeState",
    "build_features",
    "forward_fill_cross_asset",
    "smooth_features",
]
