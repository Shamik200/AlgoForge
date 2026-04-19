"""Offline retraining pipeline for the HMM Regime Detector."""

from __future__ import annotations

import os
from pathlib import Path

import joblib
import numpy as np

try:
    from hmmlearn.hmm import GaussianHMM
    from sklearn.preprocessing import StandardScaler
except ImportError:
    GaussianHMM = None
    StandardScaler = None


class HMMTrainer:
    """Trainer for the 4-state Hidden Markov Model.
    
    This class is intended to be run in an offline, scheduled background job
    (e.g., weekly) to update the market regime model without introducing
    latency to the live trading execution engine.
    """

    def __init__(
        self,
        n_components: int = 4,
        covariance_type: str = "diag",
        n_iter: int = 100,
        random_state: int = 42,
    ) -> None:
        """Initialize the trainer.
        
        Args:
            n_components: Number of hidden states (default: 4).
            covariance_type: Type of covariance parameters ('diag' or 'full').
            n_iter: Maximum number of iterations to perform.
            random_state: Random seed for reproducibility.
        """
        if GaussianHMM is None:
            msg = "hmmlearn and scikit-learn are required for the regime module. Install with: pip install hmmlearn scikit-learn"
            raise ImportError(msg)

        self.n_components = n_components
        self.model = GaussianHMM(
            n_components=n_components,
            covariance_type=covariance_type,
            n_iter=n_iter,
            random_state=random_state,
        )
        self.scaler = StandardScaler()
        self.is_trained = False

    def train(self, features: np.ndarray) -> None:
        """Train the HMM on a feature matrix.
        
        Args:
            features: 2D numpy array of shape (n_samples, n_features).
        """
        if features.shape[0] < self.n_components * 10:
            msg = f"Insufficient data for training. Need at least {self.n_components * 10} samples."
            raise ValueError(msg)

        # Scale features
        scaled_features = self.scaler.fit_transform(features)
        
        # Fit HMM
        self.model.fit(scaled_features)
        self.is_trained = True

    def save(self, directory: str | Path, model_name: str = "regime_hmm") -> None:
        """Serialize the trained model and scaler to disk.
        
        Args:
            directory: The directory to save the files in.
            model_name: Base name for the saved files.
        """
        if not self.is_trained:
            msg = "Cannot save an untrained model."
            raise RuntimeError(msg)

        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)

        model_path = dir_path / f"{model_name}_model.pkl"
        scaler_path = dir_path / f"{model_name}_scaler.pkl"

        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)

    @classmethod
    def load(cls, directory: str | Path, model_name: str = "regime_hmm") -> "HMMTrainer":
        """Load a trained model and scaler from disk.
        
        Args:
            directory: The directory containing the saved files.
            model_name: Base name of the saved files.
            
        Returns:
            An instantiated HMMTrainer with the loaded model and scaler.
        """
        if GaussianHMM is None:
            msg = "hmmlearn and scikit-learn are required for the regime module."
            raise ImportError(msg)

        dir_path = Path(directory)
        model_path = dir_path / f"{model_name}_model.pkl"
        scaler_path = dir_path / f"{model_name}_scaler.pkl"

        if not model_path.exists() or not scaler_path.exists():
            msg = f"Model files not found in {directory}"
            raise FileNotFoundError(msg)

        instance = cls()
        instance.model = joblib.load(model_path)
        instance.scaler = joblib.load(scaler_path)
        instance.is_trained = True
        return instance
