"""Signal score normalization logic."""

from collections import deque

import numpy as np


class RollingNormalizer:
    """Normalizes raw signal scores into z-scores over a rolling window."""
    
    def __init__(self, window_size: int = 100) -> None:
        """Initialize the normalizer.
        
        Args:
            window_size: Number of periods to keep in the rolling window.
        """
        self.window_size = window_size
        self._history: dict[str, deque[float]] = {}
        
    def add_score(self, family_name: str, score: float) -> None:
        """Add a raw score to the family's rolling history."""
        if family_name not in self._history:
            self._history[family_name] = deque(maxlen=self.window_size)
            
        self._history[family_name].append(score)
        
    def get_normalized_score(self, family_name: str, current_score: float) -> float:
        """Calculate the normalized [-1.0, 1.0] z-score for the current score.
        
        Formula: z_score = (current - mean) / std.
        The z_score is then divided by 3.0 and clipped to [-1.0, 1.0].
        
        If the family has no history, or standard deviation is 0, the 
        current score is clipped directly.
        """
        history = self._history.get(family_name)
        
        if not history or len(history) < 2:
            return np.clip(current_score, -1.0, 1.0)
            
        arr = np.array(history)
        mean = np.mean(arr)
        std = np.std(arr)
        
        if std == 0:
            # If all historical scores are identical, we can't calculate a standard z-score
            # We just bound the raw score directly.
            return np.clip(current_score, -1.0, 1.0)
            
        z_score = (current_score - mean) / std
        
        # 99.7% of z-scores fall between -3 and 3. 
        # Divide by 3 to squish mostly into [-1, 1], then hard clip the tails.
        normalized = z_score / 3.0
        return float(np.clip(normalized, -1.0, 1.0))
