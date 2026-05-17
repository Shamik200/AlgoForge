"""AlgoForge Structural Confluence Module.

Detects objective zones of support and resistance by aggregating
volume profiles, swing points, and dynamic moving averages into
scored confluence zones.
"""

from algoforge.structural.engine import StructuralConfluenceEngine
from algoforge.structural.models import ConfluenceZone, LevelType, PriceLevel
from algoforge.structural.pattern_recognizer import (
    CandlestickPattern,
    PatternDirection,
    PatternRecognizer,
    PatternStrength,
)
from algoforge.structural.swings import cluster_swings, detect_swings

__all__ = [
    "CandlestickPattern",
    "ConfluenceZone",
    "LevelType",
    "PatternDirection",
    "PatternRecognizer",
    "PatternStrength",
    "PriceLevel",
    "StructuralConfluenceEngine",
    "cluster_swings",
    "detect_swings",
]
