"""Multi-Target Exits module."""

from algoforge.exits.manager import ExitManager
from algoforge.exits.stops import calculate_initial_stop
from algoforge.exits.tranches import split_into_tranches

__all__ = [
    "ExitManager",
    "calculate_initial_stop",
    "split_into_tranches",
]
