"""Pairs & Cointegration Trading signal family module."""

from algoforge.signals.pairs.cointegration import engle_granger_test
from algoforge.signals.pairs.family import PairsTradingFamily

__all__ = [
    "engle_granger_test",
    "PairsTradingFamily",
]
