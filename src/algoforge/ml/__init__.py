"""ML Pipeline module."""

from algoforge.ml.features import FeatureBuilder
from algoforge.ml.labels import generate_labels, calculate_atr
from algoforge.ml.validation import purged_walk_forward_split
from algoforge.ml.models import GBMClassifier, GBMRegressor
from algoforge.ml.ensemble import StackingEnsemble
from algoforge.ml.pipeline import MLPipeline, MLPipelineResult
from algoforge.ml.fingpt_client import FinGPTClient, FinGPTPrediction, PricePoint
from algoforge.ml.confidence_aggregator import ConfidenceAggregator, ConvictionScore
from algoforge.ml.rl_adjuster import (
    RLThresholdAdjuster,
    RLConfig,
    TradeOutcome,
    ThresholdAdjustments,
    RLAgentState,
)

__all__ = [
    "FeatureBuilder",
    "generate_labels",
    "calculate_atr",
    "purged_walk_forward_split",
    "GBMClassifier",
    "GBMRegressor",
    "StackingEnsemble",
    "MLPipeline",
    "MLPipelineResult",
    "FinGPTClient",
    "FinGPTPrediction",
    "PricePoint",
    "ConfidenceAggregator",
    "ConvictionScore",
    "RLThresholdAdjuster",
    "RLConfig",
    "TradeOutcome",
    "ThresholdAdjustments",
    "RLAgentState",
]
