"""AlgoForge Structural Confluence Module.

Detects objective zones of support and resistance by aggregating
volume profiles, swing points, and dynamic moving averages into
scored confluence zones.
"""

from algoforge.structural.engine import StructuralConfluenceEngine
from algoforge.structural.models import ConfluenceZone, LevelType, PriceLevel
from algoforge.structural.swings import cluster_swings, detect_swings

__all__ = [
    "ConfluenceZone",
    "LevelType",
    "PriceLevel",
    "StructuralConfluenceEngine",
    "cluster_swings",
    "detect_swings",
]
