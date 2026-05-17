"""Property-based tests for StrategyAdapter module.

**Validates: Requirements 1.1, 1.2, 1.7**

Property 1: Signal Score Normalization
For any legacy strategy output with any score value, when adapted through the
StrategyAdapter, the resulting SignalResult score SHALL be within the bounds
[-1.0, 1.0] inclusive.

Property 2: Signal Metadata Completeness
For any legacy strategy that generates a signal, the adapted SignalResult SHALL
contain non-empty values for strategy name, timeframe, and confidence in the
metadata dictionary.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.signals.adapter import StrategyAdapter
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.strategies.base import Strategy
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot


# ============================================================================
# Mock Strategy for Testing
# ============================================================================

class MockStrategy(Strategy):
    """Mock strategy for property-based testing."""
    
    def __init__(self, name: str = "mock_strategy", signals: list[Signal] | None = None):
        self._name = name
        self._signals = signals if signals is not None else []
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.TRENDING]
    
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
        return self._signals


# ============================================================================
# Hypothesis Strategies for Generating Test Data
# ============================================================================

@st.composite
def valid_confidence(draw):
    """Generate valid confidence values (0.0 to 1.0)."""
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


@st.composite
def direction_enum(draw):
    """Generate Direction enum values."""
    return draw(st.sampled_from([Direction.LONG, Direction.SHORT, Direction.NEUTRAL]))


@st.composite
def timeframe_enum(draw):
    """Generate Timeframe enum values."""
    return draw(st.sampled_from([
        Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.M30,
        Timeframe.H1, Timeframe.H4, Timeframe.D1
    ]))


@st.composite
def valid_price(draw):
    """Generate valid price values."""
    return draw(st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False))


@st.composite
def strategy_name(draw):
    """Generate strategy names."""
    return draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='_-'
    )))


@st.composite
def signal_with_metadata(draw):
    """Generate a Signal with all required fields and optional metadata."""
    direction = draw(direction_enum())
    confidence = draw(valid_confidence())
    entry_price = draw(valid_price())
    
    # Generate stop loss and take profit based on direction
    if direction == Direction.LONG:
        stop_loss = draw(st.floats(
            min_value=entry_price * 0.5,
            max_value=entry_price * 0.99,
            allow_nan=False,
            allow_infinity=False
        ))
        take_profit = draw(st.floats(
            min_value=entry_price * 1.01,
            max_value=entry_price * 2.0,
            allow_nan=False,
            allow_infinity=False
        ))
    elif direction == Direction.SHORT:
        stop_loss = draw(st.floats(
            min_value=entry_price * 1.01,
            max_value=entry_price * 1.5,
            allow_nan=False,
            allow_infinity=False
        ))
        take_profit = draw(st.floats(
            min_value=entry_price * 0.5,
            max_value=entry_price * 0.99,
            allow_nan=False,
            allow_infinity=False
        ))
    else:  # NEUTRAL
        stop_loss = entry_price * 0.95
        take_profit = entry_price * 1.05
    
    timeframe = draw(timeframe_enum())
    strat_name = draw(strategy_name())
    
    # Optional metadata (must be dict, not None)
    metadata = draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll'),
            whitelist_characters='_'
        )),
        values=st.one_of(
            st.integers(min_value=-1000, max_value=1000),
            st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.text(min_size=0, max_size=50)
        ),
        min_size=0,
        max_size=5
    ))
    
    return Signal(
        symbol="TEST",
        direction=direction,
        strategy=strat_name,
        confidence=confidence,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        timeframe=timeframe,
        metadata=metadata
    )


@st.composite
def multiple_signals(draw):
    """Generate a list of 1-5 signals."""
    num_signals = draw(st.integers(min_value=1, max_value=5))
    return [draw(signal_with_metadata()) for _ in range(num_signals)]


@st.composite
def family_name(draw):
    """Generate signal family names."""
    return draw(st.sampled_from([
        "momentum", "mean_reversion", "breakout", "structural", "microstructure"
    ]))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_indicators():
    """Create mock indicator snapshot."""
    snapshot = IndicatorSnapshot()
    snapshot.computed_at = datetime.now(timezone.utc).timestamp()
    return snapshot


@pytest.fixture
def mock_structure():
    """Create mock structural snapshot."""
    return StructuralSnapshot(
        symbol="TEST",
        sr_levels=[],
        trendlines=[],
        channels=[],
        trend_direction="unclear",
        swing_highs=[],
        swing_lows=[],
        computed_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_price_data():
    """Create mock price data."""
    return {
        "closes": [100.0] * 50,
        "highs": [101.0] * 50,
        "lows": [99.0] * 50,
        "volumes": [1000.0] * 50,
        "opens": [100.0] * 50,
    }


# ============================================================================
# Property 1: Signal Score Normalization
# **Validates: Requirements 1.1, 1.7**
# ============================================================================

class TestSignalScoreNormalizationProperty:
    """Property-based tests for signal score normalization.
    
    **Validates: Requirements 1.1, 1.7**
    
    Property 1: Signal Score Normalization
    For any legacy strategy output with any score value, when adapted through
    the StrategyAdapter, the resulting SignalResult score SHALL be within the
    bounds [-1.0, 1.0] inclusive.
    """
    
    @given(signal_with_metadata(), family_name())
    @settings(
        max_examples=100,
        deadline=None
    )
    @pytest.mark.asyncio
    async def test_property_single_signal_score_in_bounds(
        self,
        signal,
        family
    ):
        """Property: All adapted single signals have scores in [-1, 1].
        
        **Validates: Requirements 1.1, 1.7**
        """
        # Create mock fixtures
        mock_indicators = IndicatorSnapshot()
        mock_indicators.computed_at = datetime.now(timezone.utc).timestamp()
        
        mock_structure = StructuralSnapshot(
            symbol="TEST",
            sr_levels=[],
            trendlines=[],
            channels=[],
            trend_direction="unclear",
            swing_highs=[],
            swing_lows=[],
            computed_at=datetime.now(timezone.utc),
        )
        
        mock_price_data = {
            "closes": [100.0] * 50,
            "highs": [101.0] * 50,
            "lows": [99.0] * 50,
            "volumes": [1000.0] * 50,
            "opens": [100.0] * 50,
        }
        
        # Create strategy with the generated signal
        strategy = MockStrategy(name=signal.strategy, signals=[signal])
        adapter = StrategyAdapter(strategy, family)
        
        # Generate signal result
        result = await adapter.generate_signal(
            symbol="TEST",
            timeframe=signal.timeframe,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        # Property: Score must be in [-1, 1]
        assert -1.0 <= result.score <= 1.0, (
            f"Signal score {result.score} is outside bounds [-1, 1] "
            f"for direction={signal.direction}, confidence={signal.confidence}"
        )
    
    @given(multiple_signals(), family_name())
    @settings(
        max_examples=100,
        deadline=None
    )
    @pytest.mark.asyncio
    async def test_property_multiple_signals_score_in_bounds(
        self,
        signals,
        family
    ):
        """Property: When multiple signals are generated, the adapted result score is in [-1, 1].
        
        **Validates: Requirements 1.1, 1.7**
        """
        # Create mock fixtures
        mock_indicators = IndicatorSnapshot()
        mock_indicators.computed_at = datetime.now(timezone.utc).timestamp()
        
        mock_structure = StructuralSnapshot(
            symbol="TEST",
            sr_levels=[],
            trendlines=[],
            channels=[],
            trend_direction="unclear",
            swing_highs=[],
            swing_lows=[],
            computed_at=datetime.now(timezone.utc),
        )
        
        mock_price_data = {
            "closes": [100.0] * 50,
            "highs": [101.0] * 50,
            "lows": [99.0] * 50,
            "volumes": [1000.0] * 50,
            "opens": [100.0] * 50,
        }
        
        # Use the first signal's strategy name and timeframe
        strategy_name = signals[0].strategy
        timeframe = signals[0].timeframe
        
        # Create strategy with multiple signals
        strategy = MockStrategy(name=strategy_name, signals=signals)
        adapter = StrategyAdapter(strategy, family)
        
        # Generate signal result
        result = await adapter.generate_signal(
            symbol="TEST",
            timeframe=timeframe,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        # Property: Score must be in [-1, 1]
        assert -1.0 <= result.score <= 1.0, (
            f"Signal score {result.score} is outside bounds [-1, 1] "
            f"for {len(signals)} signals"
        )
    
    @given(direction_enum(), valid_confidence(), family_name())
    @settings(
        max_examples=100,
        deadline=None
    )
    @pytest.mark.asyncio
    async def test_property_score_respects_direction(
        self,
        direction,
        confidence,
        family
    ):
        """Property: LONG signals produce non-negative scores, SHORT signals produce non-positive scores.
        
        **Validates: Requirements 1.1, 1.7**
        """
        # Create mock fixtures inline
        mock_indicators = IndicatorSnapshot()
        mock_indicators.computed_at = datetime.now(timezone.utc).timestamp()
        
        mock_structure = StructuralSnapshot(
            symbol="TEST",
            sr_levels=[],
            trendlines=[],
            channels=[],
            trend_direction="unclear",
            swing_highs=[],
            swing_lows=[],
            computed_at=datetime.now(timezone.utc),
        )
        
        mock_price_data = {
            "closes": [100.0] * 50,
            "highs": [101.0] * 50,
            "lows": [99.0] * 50,
            "volumes": [1000.0] * 50,
            "opens": [100.0] * 50,
        }
        
        signal = Signal(
            symbol="TEST",
            direction=direction,
            strategy="test_strategy",
            confidence=confidence,
            entry_price=100.0,
            stop_loss=95.0 if direction == Direction.LONG else 105.0,
            take_profit=110.0 if direction == Direction.LONG else 90.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, family)
        
        result = await adapter.generate_signal(
            symbol="TEST",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        # Property: Direction determines score sign
        if direction == Direction.LONG:
            assert result.score >= 0.0, f"LONG signal produced negative score: {result.score}"
        elif direction == Direction.SHORT:
            assert result.score <= 0.0, f"SHORT signal produced positive score: {result.score}"
        else:  # NEUTRAL
            assert result.score == 0.0, f"NEUTRAL signal produced non-zero score: {result.score}"
        
        # Property: Score is in bounds
        assert -1.0 <= result.score <= 1.0


# ============================================================================
# Property 2: Signal Metadata Completeness
# **Validates: Requirements 1.2**
# ============================================================================

class TestSignalMetadataCompletenessProperty:
    """Property-based tests for signal metadata completeness.
    
    **Validates: Requirements 1.2**
    
    Property 2: Signal Metadata Completeness
    For any legacy strategy that generates a signal, the adapted SignalResult
    SHALL contain non-empty values for strategy name, timeframe, and confidence
    in the metadata dictionary.
    """
    
    @given(signal_with_metadata(), family_name())
    @settings(
        max_examples=100,
        deadline=None
    )
    @pytest.mark.asyncio
    async def test_property_metadata_contains_required_fields(
        self,
        signal,
        family
    ):
        """Property: All adapted signals contain required metadata fields.
        
        **Validates: Requirements 1.2**
        """
        # Create mock fixtures inline
        mock_indicators = IndicatorSnapshot()
        mock_indicators.computed_at = datetime.now(timezone.utc).timestamp()
        
        mock_structure = StructuralSnapshot(
            symbol="TEST",
            sr_levels=[],
            trendlines=[],
            channels=[],
            trend_direction="unclear",
            swing_highs=[],
            swing_lows=[],
            computed_at=datetime.now(timezone.utc),
        )
        
        mock_price_data = {
            "closes": [100.0] * 50,
            "highs": [101.0] * 50,
            "lows": [99.0] * 50,
            "volumes": [1000.0] * 50,
            "opens": [100.0] * 50,
        }
        
        strategy = MockStrategy(name=signal.strategy, signals=[signal])
        adapter = StrategyAdapter(strategy, family)
        
        result = await adapter.generate_signal(
            symbol="TEST",
            timeframe=signal.timeframe,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        # Property: Required metadata fields must be present
        assert "strategy_name" in result.metadata, "Missing 'strategy_name' in metadata"
        assert "timeframe" in result.metadata, "Missing 'timeframe' in metadata"
        assert "confidence" in result.metadata, "Missing 'confidence' in metadata"
        
        # Property: Required fields must be non-empty/non-null
        assert result.metadata["strategy_name"], "strategy_name is empty"
        assert result.metadata["timeframe"], "timeframe is empty"
        assert result.metadata["confidence"] is not None, "confidence is None"
    
    @given(signal_with_metadata(), family_name())
    @settings(
        max_examples=100,
        deadline=None
    )
    @pytest.mark.asyncio
    async def test_property_metadata_values_match_signal(
        self,
        signal,
        family
    ):
        """Property: Metadata values match the original signal values.
        
        **Validates: Requirements 1.2**
        """
        # Create mock fixtures inline
        mock_indicators = IndicatorSnapshot()
        mock_indicators.computed_at = datetime.now(timezone.utc).timestamp()
        
        mock_structure = StructuralSnapshot(
            symbol="TEST",
            sr_levels=[],
            trendlines=[],
            channels=[],
            trend_direction="unclear",
            swing_highs=[],
            swing_lows=[],
            computed_at=datetime.now(timezone.utc),
        )
        
        mock_price_data = {
            "closes": [100.0] * 50,
            "highs": [101.0] * 50,
            "lows": [99.0] * 50,
            "volumes": [1000.0] * 50,
            "opens": [100.0] * 50,
        }
        
        strategy = MockStrategy(name=signal.strategy, signals=[signal])
        adapter = StrategyAdapter(strategy, family)
        
        result = await adapter.generate_signal(
            symbol="TEST",
            timeframe=signal.timeframe,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        # Property: Metadata values must match original signal
        assert result.metadata["strategy_name"] == signal.strategy, (
            f"strategy_name mismatch: {result.metadata['strategy_name']} != {signal.strategy}"
        )
        assert result.metadata["timeframe"] == signal.timeframe.value, (
            f"timeframe mismatch: {result.metadata['timeframe']} != {signal.timeframe.value}"
        )
        assert result.metadata["confidence"] == signal.confidence, (
            f"confidence mismatch: {result.metadata['confidence']} != {signal.confidence}"
        )
    
    @given(signal_with_metadata(), family_name())
    @settings(
        max_examples=100,
        deadline=None
    )
    @pytest.mark.asyncio
    async def test_property_metadata_contains_price_levels(
        self,
        signal,
        family
    ):
        """Property: Metadata contains entry price, stop loss, and take profit.
        
        **Validates: Requirements 1.2**
        """
        # Create mock fixtures inline
        mock_indicators = IndicatorSnapshot()
        mock_indicators.computed_at = datetime.now(timezone.utc).timestamp()
        
        mock_structure = StructuralSnapshot(
            symbol="TEST",
            sr_levels=[],
            trendlines=[],
            channels=[],
            trend_direction="unclear",
            swing_highs=[],
            swing_lows=[],
            computed_at=datetime.now(timezone.utc),
        )
        
        mock_price_data = {
            "closes": [100.0] * 50,
            "highs": [101.0] * 50,
            "lows": [99.0] * 50,
            "volumes": [1000.0] * 50,
            "opens": [100.0] * 50,
        }
        
        strategy = MockStrategy(name=signal.strategy, signals=[signal])
        adapter = StrategyAdapter(strategy, family)
        
        result = await adapter.generate_signal(
            symbol="TEST",
            timeframe=signal.timeframe,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        # Property: Price level metadata must be present
        assert "entry_price" in result.metadata, "Missing 'entry_price' in metadata"
        assert "stop_loss" in result.metadata, "Missing 'stop_loss' in metadata"
        assert "take_profit" in result.metadata, "Missing 'take_profit' in metadata"
        
        # Property: Price levels must match original signal
        assert result.metadata["entry_price"] == signal.entry_price
        assert result.metadata["stop_loss"] == signal.stop_loss
        assert result.metadata["take_profit"] == signal.take_profit
    
    @given(multiple_signals(), family_name())
    @settings(
        max_examples=100,
        deadline=None
    )
    @pytest.mark.asyncio
    async def test_property_metadata_complete_for_multiple_signals(
        self,
        signals,
        family
    ):
        """Property: When multiple signals are generated, metadata is still complete.
        
        **Validates: Requirements 1.2**
        """
        # Create mock fixtures inline
        mock_indicators = IndicatorSnapshot()
        mock_indicators.computed_at = datetime.now(timezone.utc).timestamp()
        
        mock_structure = StructuralSnapshot(
            symbol="TEST",
            sr_levels=[],
            trendlines=[],
            channels=[],
            trend_direction="unclear",
            swing_highs=[],
            swing_lows=[],
            computed_at=datetime.now(timezone.utc),
        )
        
        mock_price_data = {
            "closes": [100.0] * 50,
            "highs": [101.0] * 50,
            "lows": [99.0] * 50,
            "volumes": [1000.0] * 50,
            "opens": [100.0] * 50,
        }
        
        strategy_name = signals[0].strategy
        timeframe = signals[0].timeframe
        
        strategy = MockStrategy(name=strategy_name, signals=signals)
        adapter = StrategyAdapter(strategy, family)
        
        result = await adapter.generate_signal(
            symbol="TEST",
            timeframe=timeframe,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        # Property: Required metadata fields must be present
        assert "strategy_name" in result.metadata
        assert "timeframe" in result.metadata
        assert "confidence" in result.metadata
        
        # Property: Required fields must be non-empty/non-null
        assert result.metadata["strategy_name"]
        assert result.metadata["timeframe"]
        assert result.metadata["confidence"] is not None
        
        # Property: Metadata should correspond to the highest confidence signal
        highest_confidence_signal = max(signals, key=lambda s: s.confidence)
        assert result.metadata["confidence"] == highest_confidence_signal.confidence
