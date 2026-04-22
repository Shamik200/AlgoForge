"""Softmax adaptive weighting logic for signal combination."""

import numpy as np


def calculate_softmax_weights(sharpe_ratios: dict[str, float]) -> dict[str, float]:
    """Calculate softmax weights from a dictionary of Sharpe ratios.
    
    Formula: weight_i = exp(sharpe_i) / sum(exp(sharpe_j))
    
    This ensures that:
    1. All weights are positive.
    2. All weights sum to exactly 1.0.
    3. Negative Sharpe ratios are exponentially penalized but still
       receive a non-zero mathematical weight.
       
    Args:
        sharpe_ratios: Dictionary mapping family_name to its rolling Sharpe ratio.
        
    Returns:
        Dictionary mapping family_name to its calculated weight [0.0, 1.0].
    """
    if not sharpe_ratios:
        return {}
        
    families = list(sharpe_ratios.keys())
    sharpes = np.array([sharpe_ratios[f] for f in families], dtype=np.float64)
    
    # Subtract max for numerical stability (prevents overflow in exp)
    max_sharpe = np.max(sharpes)
    exp_scores = np.exp(sharpes - max_sharpe)
    
    sum_exp = np.sum(exp_scores)
    weights = exp_scores / sum_exp
    
    return {f: float(w) for f, w in zip(families, weights)}
