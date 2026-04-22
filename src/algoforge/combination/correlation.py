"""Signal decorrelation matrix and redundant signal culling."""

from collections import deque

import numpy as np
import pandas as pd


class SignalCorrelationMatrix:
    """Tracks historical signal outputs to calculate pairwise correlation."""
    
    def __init__(self, window_size: int = 30) -> None:
        """Initialize the correlation matrix tracker.
        
        Args:
            window_size: Number of historical periods to correlate.
        """
        self.window_size = window_size
        self._history: dict[str, deque[float]] = {}
        
    def add_signals(self, signals: dict[str, float]) -> None:
        """Add a row of cross-sectional signals to the history."""
        for family, score in signals.items():
            if family not in self._history:
                self._history[family] = deque(maxlen=self.window_size)
            self._history[family].append(score)
            
    def get_correlation(self, family_a: str, family_b: str) -> float:
        """Calculate the Pearson correlation between two signal families."""
        if family_a == family_b:
            return 1.0
            
        hist_a = self._history.get(family_a)
        hist_b = self._history.get(family_b)
        
        if not hist_a or not hist_b:
            return 0.0
            
        # Ensure arrays are the same length
        min_len = min(len(hist_a), len(hist_b))
        if min_len < 5:
            return 0.0  # Not enough data for a stable correlation
            
        arr_a = list(hist_a)[-min_len:]
        arr_b = list(hist_b)[-min_len:]
        
        # Calculate Pearson correlation
        df = pd.DataFrame({"A": arr_a, "B": arr_b})
        corr = df["A"].corr(df["B"])
        
        # Handle NaN if arrays are completely flat (std=0)
        if pd.isna(corr):
            return 0.0
            
        return float(corr)


def cull_redundant_signals(
    sharpe_ratios: dict[str, float],
    correlation_matrix: SignalCorrelationMatrix,
    max_correlation: float = 0.70
) -> dict[str, float]:
    """Remove highly correlated signals, keeping the one with the higher Sharpe.
    
    Args:
        sharpe_ratios: Dictionary of family names to their Sharpe ratios.
        correlation_matrix: The tracking matrix containing historical signal scores.
        max_correlation: The Pearson correlation threshold.
        
    Returns:
        A new dictionary of sharpe_ratios with the redundant families dropped.
    """
    families = list(sharpe_ratios.keys())
    to_drop = set()
    
    for i in range(len(families)):
        for j in range(i + 1, len(families)):
            fam_a = families[i]
            fam_b = families[j]
            
            if fam_a in to_drop or fam_b in to_drop:
                continue
                
            corr = correlation_matrix.get_correlation(fam_a, fam_b)
            
            if corr > max_correlation:
                # Highly correlated! Drop the one with the lower Sharpe ratio.
                sharpe_a = sharpe_ratios[fam_a]
                sharpe_b = sharpe_ratios[fam_b]
                
                if sharpe_a >= sharpe_b:
                    to_drop.add(fam_b)
                else:
                    to_drop.add(fam_a)
                    
    # Return filtered dict
    return {f: s for f, s in sharpe_ratios.items() if f not in to_drop}
