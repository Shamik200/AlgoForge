"""Correlation Matrix Cache for instantaneous risk checks."""

import pandas as pd


class CorrelationMatrix:
    """A daily-updated cache of pairwise asset correlations.
    
    Prevents the Risk Engine from doing heavy DataFrame matrix
    math on every intraday trade evaluation.
    """
    
    def __init__(self) -> None:
        self._matrix: dict[tuple[str, str], float] = {}

    def update(self, returns_df: pd.DataFrame) -> None:
        """Update the correlation matrix from a dataframe of returns.
        
        Args:
            returns_df: DataFrame where columns are symbols and rows are daily returns.
        """
        if returns_df.empty:
            return
            
        corr_df = returns_df.corr(method="pearson")
        
        symbols = corr_df.columns.tolist()
        self._matrix.clear()
        
        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i:]:
                val = float(corr_df.loc[sym_a, sym_b])
                # Store in both directions for easy lookup
                self._matrix[(sym_a, sym_b)] = val
                self._matrix[(sym_b, sym_a)] = val

    def get_correlation(self, symbol_a: str, symbol_b: str) -> float:
        """Get the cached correlation between two symbols.
        
        Returns 0.0 if unknown to prevent false positives in risk limits.
        """
        if symbol_a == symbol_b:
            return 1.0
        return self._matrix.get((symbol_a, symbol_b), 0.0)
        
    def is_empty(self) -> bool:
        return len(self._matrix) == 0
