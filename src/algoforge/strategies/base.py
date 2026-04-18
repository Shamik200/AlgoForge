"""Strategy base class.

All strategies inherit from this ABC. Enforces the contract:
- Must declare required_regime (which regime activates this strategy)
- Must implement evaluate() → list of Signal candidates
- Must declare name and minimum required data
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from algoforge.core.constants import MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot


class Strategy(ABC):
    """Abstract base class for all trading strategies.

    Subclasses implement `evaluate()` which receives indicator and structural
    data and returns zero or more Signal candidates. The strategy orchestrator
    will only call evaluate() when the market regime matches required_regime.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier (e.g., 'trendline_pullback')."""
        ...

    @property
    @abstractmethod
    def required_regime(self) -> list[MarketRegime]:
        """Market regimes that activate this strategy."""
        ...

    @property
    def min_bars(self) -> int:
        """Minimum bars needed for evaluation."""
        return 50

    @abstractmethod
    def evaluate(
        self,
        symbol: str,
        timeframe: Timeframe,
        indicators: IndicatorSnapshot,
        structure: StructuralSnapshot,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[float],
        opens: list[float],
    ) -> list[Signal]:
        """Evaluate market conditions and generate signals.

        Args:
            symbol: Instrument symbol
            timeframe: Timeframe being analyzed
            indicators: All indicator results for this symbol/timeframe
            structure: S/R levels, trendlines, trend direction
            closes/highs/lows/volumes/opens: Raw price data

        Returns:
            List of Signal candidates (may be empty). These will be
            passed through the risk management engine for validation.
        """
        ...

    def __repr__(self) -> str:
        return f"<Strategy: {self.name}>"
