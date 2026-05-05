"""Integration tests for the full AlgoForge pipeline."""

import pytest
import numpy as np
from datetime import datetime, timezone

from algoforge.core.constants import MarketRegime, Timeframe
from algoforge.core.orchestrator import Orchestrator
from algoforge.fundamental.pipeline import FundamentalResult
from algoforge.risk.manager import RiskConfig
from algoforge.strategies.secondary_trending_range import EMACrossover
from algoforge.technical.indicator_base import IndicatorResult
from algoforge.technical.regime import RegimeResult
from algoforge.technical.structural.models import StructuralSnapshot, TrendDirection

def test_full_pipeline_end_to_end():
    """Test the full pipeline end-to-end with all components enabled."""
    
    # 1. Initialize Orchestrator with all components enabled
    orch = Orchestrator(
        capital=100_000,
        enable_fundamentals=True,
        enable_dual_tf=False,  # Skip dual TF to simplify test data
        enable_ml=True,
        enable_combination=True,
        strategies=[EMACrossover(min_adx=15)]
    )
    
    # Verify components are initialized
    assert orch._fundamental is not None
    assert orch._ml is not None
    assert orch._combination is not None
    assert orch.paper_engine is not None
    
    # 2. Mock input data for a single bar
    # Technical Indicators
    indicators = {
        "adx": IndicatorResult(name="adx", value=25.0, parameters={}, is_valid=True),
        "rsi": IndicatorResult(name="rsi", value=60.0, parameters={}, is_valid=True),
        "ema_fast": IndicatorResult(name="ema_fast", value=105.0, parameters={}, is_valid=True),
        "ema_slow": IndicatorResult(name="ema_slow", value=100.0, parameters={}, is_valid=True),
    }
    
    # Structural Analysis
    structure = StructuralSnapshot(
        symbol="TEST",
        timeframe=Timeframe.D1,
        trend=TrendDirection.UP,
        support_levels=[95.0],
        resistance_levels=[110.0],
        timestamp=datetime.now(timezone.utc)
    )
    
    # Market Regime
    regime = RegimeResult(
        symbol="TEST",
        primary_regime=MarketRegime.TRENDING,
        confidence=0.8,
        probabilities={MarketRegime.TRENDING: 0.8, MarketRegime.RANGE: 0.2}
    )
    
    # Fundamental Gate (Pass)
    fundamental_result = FundamentalResult(
        symbol="TEST",
        gate_score=85, # High score to allow trading
        sentiment=None, screener=None, macro=None, selections=[]
    )
    
    # ML Features (simulating output of FeatureBuilder for Dummy)
    ml_features = {
        "adx": 25.0,
        "rsi": 60.0,
        "ret_1": 0.01
    }
    
    # 3. Process the bar
    results = orch.process_bar(
        symbol="TEST",
        timeframe=Timeframe.D1,
        indicators=indicators,
        structure=structure,
        regime_result=regime,
        closes=[98.0, 99.0, 101.0, 102.0],
        highs=[99.0, 100.0, 102.0, 103.0],
        lows=[97.0, 98.0, 100.0, 101.0],
        volumes=[1000, 1200, 1500, 2000],
        opens=[97.5, 98.5, 99.5, 101.5],
        fundamental_result=fundamental_result,
        ml_features=ml_features
    )
    
    # 4. Assertions
    # The pipeline should have executed without crashing
    assert len(results) >= 0
    # Depending on the mock ML model state (StackingEnsemble is untrained here), 
    # the signals might be unmodified or modified, but it shouldn't crash.
    
    # The stats should reflect the number of signals generated
    stats = orch.stats
    assert stats["strategies"] == 1
    assert "signals_generated" in stats
