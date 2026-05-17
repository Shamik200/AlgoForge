"""Signal generation and integration module.

This module provides:
- StrategyAdapter: Converts legacy strategies to SignalResult format
- IntegrationRegistry: Maps strategies to signal families
- SignalResult and SignalDirection: Standardized signal models
"""

from algoforge.signals.adapter import StrategyAdapter
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.signals.registry import IntegrationRegistry, create_default_registry

__all__ = [
    "StrategyAdapter",
    "IntegrationRegistry",
    "create_default_registry",
    "SignalResult",
    "SignalDirection",
]
