"""Signal Combination Framework module."""

from algoforge.combination.correlation import SignalCorrelationMatrix, cull_redundant_signals
from algoforge.combination.engine import CombinationEngine
from algoforge.combination.normalization import RollingNormalizer
from algoforge.combination.weighting import calculate_softmax_weights

__all__ = [
    "CombinationEngine",
    "RollingNormalizer",
    "SignalCorrelationMatrix",
    "calculate_softmax_weights",
    "cull_redundant_signals",
]
