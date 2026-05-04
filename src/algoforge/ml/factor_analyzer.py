"""Factor analysis and quality measurement (Phase 11).

Implements Qlib-inspired Information Coefficient (IC) and 
IC Information Ratio (ICIR) tracking for factor selection and decay detection.
"""

from typing import Dict, List, Optional
import numpy as np
import scipy.stats
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


@dataclass
class FactorMetrics:
    """Quality metrics for a single alpha factor."""
    name: str
    ic_mean: float
    ic_std: float
    icir: float
    rank_ic: float
    recent_ic: float
    is_decaying: bool


class FactorAnalyzer:
    """Analyzes factor quality using IC and ICIR."""

    def __init__(self, ic_decay_threshold: float = 0.02, min_samples: int = 100):
        """
        Args:
            ic_decay_threshold: Minimum acceptable recent IC before flagging decay.
            min_samples: Minimum samples required to compute reliable IC.
        """
        self.ic_decay_threshold = ic_decay_threshold
        self.min_samples = min_samples
        
        # History of ICs per factor: {factor_name: [ic_1, ic_2, ...]}
        self.ic_history: Dict[str, List[float]] = {}
        
    def evaluate_factors(self, feature_matrix: np.ndarray, feature_names: List[str], forward_returns: np.ndarray) -> Dict[str, FactorMetrics]:
        """Compute IC and ICIR for all factors in the feature matrix against forward returns.
        
        Args:
            feature_matrix: Array of shape (n_samples, n_features).
            feature_names: List of names corresponding to columns.
            forward_returns: Array of shape (n_samples,) containing future returns.
            
        Returns:
            Dict mapping factor name to FactorMetrics.
        """
        n_samples, n_features = feature_matrix.shape
        if n_samples < self.min_samples:
            logger.warning(f"Insufficient samples for factor analysis: {n_samples} < {self.min_samples}")
            return {}
            
        if len(feature_names) != n_features:
            raise ValueError(f"Feature names length ({len(feature_names)}) must match columns ({n_features})")
            
        metrics = {}
        
        for i, name in enumerate(feature_names):
            factor_values = feature_matrix[:, i]
            
            # Filter out NaNs
            valid_mask = ~(np.isnan(factor_values) | np.isnan(forward_returns))
            if np.sum(valid_mask) < self.min_samples:
                continue
                
            clean_factor = factor_values[valid_mask]
            clean_returns = forward_returns[valid_mask]
            
            # Avoid constant factors
            if np.std(clean_factor) == 0:
                continue
                
            # Spearman Rank IC (robust to outliers)
            rank_ic, _ = scipy.stats.spearmanr(clean_factor, clean_returns)
            # Pearson IC
            ic, _ = scipy.stats.pearsonr(clean_factor, clean_returns)
            
            if name not in self.ic_history:
                self.ic_history[name] = []
            
            # Store daily/batch IC
            self.ic_history[name].append(ic)
            
            # Limit history to recent 100 periods
            if len(self.ic_history[name]) > 100:
                self.ic_history[name].pop(0)
                
            history_array = np.array(self.ic_history[name])
            ic_mean = float(np.mean(history_array))
            ic_std = float(np.std(history_array))
            
            # ICIR = Mean(IC) / Std(IC)
            icir = ic_mean / ic_std if ic_std > 0 else 0.0
            
            recent_ic = float(np.mean(history_array[-5:])) if len(history_array) >= 5 else ic
            
            # Decay detection: If recent IC drops below threshold or flips sign negatively against historical
            is_decaying = False
            if abs(recent_ic) < self.ic_decay_threshold and abs(ic_mean) > self.ic_decay_threshold * 1.5:
                is_decaying = True
                
            metrics[name] = FactorMetrics(
                name=name,
                ic_mean=ic_mean,
                ic_std=ic_std,
                icir=icir,
                rank_ic=rank_ic,
                recent_ic=recent_ic,
                is_decaying=is_decaying
            )
            
        return metrics

    def filter_redundant_features(self, feature_matrix: np.ndarray, feature_names: List[str], max_correlation: float = 0.8) -> List[str]:
        """Compute correlation matrix and remove highly correlated redundant features.
        
        Args:
            feature_matrix: Array of shape (n_samples, n_features).
            feature_names: List of names corresponding to columns.
            max_correlation: Threshold for absolute correlation.
            
        Returns:
            List of feature names to keep.
        """
        import pandas as pd
        
        df = pd.DataFrame(feature_matrix, columns=feature_names)
        corr_matrix = df.corr().abs()
        
        # Upper triangle
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        
        # Find features with correlation greater than threshold
        to_drop = [column for column in upper.columns if any(upper[column] > max_correlation)]
        
        return [name for name in feature_names if name not in to_drop]
