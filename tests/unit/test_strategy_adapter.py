"""Unit tests for the StrategyAdapter class.

Tests cover:
- Score normalization to [-1, 1] range
- Direction mapping from Direction to SignalDirection
- Metadata preservation (strategy name, timeframe, confidence)
- Handling of no signals, single signal, and multiple signals
- Edge cases and validation
"""

from datetime import datetime, timezone

import pytest

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.signals.adapter import StrategyAdapter
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.strategies.base import Strategy
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot


class MockStrategy(Strategy):
    """Mock strategy for testing the adapter."""
    
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
        symbol="AAPL",
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


class TestStrategyAdapterInitialization:
    """Test StrategyAdapter initialization."""
    
    def test_init_with_strategy_and_family(self):
        """Test adapter initialization with strategy and family name."""
        strategy = MockStrategy(name="test_strategy")
        adapter = StrategyAdapter(strategy, "momentum")
        
        assert adapter.strategy == strategy
        assert adapter.family_name == "momentum"
    
    def test_repr(self):
        """Test string representation of adapter."""
        strategy = MockStrategy(name="test_strategy")
        adapter = StrategyAdapter(strategy, "momentum")
        
        repr_str = repr(adapter)
        assert "StrategyAdapter" in repr_str
        assert "test_strategy" in repr_str
        assert "momentum" in repr_str


class TestScoreNormalization:
    """Test score normalization to [-1, 1] range."""
    
    @pytest.mark.asyncio
    async def test_long_signal_positive_score(self, mock_indicators, mock_structure, mock_price_data):
        """Test that LONG signals produce positive scores."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.8,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.score == 0.8
        assert result.score > 0
        assert -1.0 <= result.score <= 1.0
    
    @pytest.mark.asyncio
    async def test_short_signal_negative_score(self, mock_indicators, mock_structure, mock_price_data):
        """Test that SHORT signals produce negative scores."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.SHORT,
            strategy="test_strategy",
            confidence=0.6,
            entry_price=100.0,
            stop_loss=105.0,
            take_profit=90.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.score == -0.6
        assert result.score < 0
        assert -1.0 <= result.score <= 1.0
    
    @pytest.mark.asyncio
    async def test_neutral_signal_zero_score(self, mock_indicators, mock_structure, mock_price_data):
        """Test that NEUTRAL signals produce zero score."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.NEUTRAL,
            strategy="test_strategy",
            confidence=0.5,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=105.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.score == 0.0
        assert -1.0 <= result.score <= 1.0
    
    @pytest.mark.asyncio
    async def test_max_confidence_long(self, mock_indicators, mock_structure, mock_price_data):
        """Test maximum confidence LONG signal produces score of 1.0."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=1.0,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.score == 1.0
    
    @pytest.mark.asyncio
    async def test_max_confidence_short(self, mock_indicators, mock_structure, mock_price_data):
        """Test maximum confidence SHORT signal produces score of -1.0."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.SHORT,
            strategy="test_strategy",
            confidence=1.0,
            entry_price=100.0,
            stop_loss=105.0,
            take_profit=90.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.score == -1.0
    
    @pytest.mark.asyncio
    async def test_min_confidence(self, mock_indicators, mock_structure, mock_price_data):
        """Test minimum confidence signal produces score near 0."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.0,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.score == 0.0


class TestDirectionMapping:
    """Test direction mapping from Direction to SignalDirection."""
    
    @pytest.mark.asyncio
    async def test_long_direction_mapping(self, mock_indicators, mock_structure, mock_price_data):
        """Test LONG direction is correctly mapped."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.direction == SignalDirection.LONG
    
    @pytest.mark.asyncio
    async def test_short_direction_mapping(self, mock_indicators, mock_structure, mock_price_data):
        """Test SHORT direction is correctly mapped."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.SHORT,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=105.0,
            take_profit=90.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.direction == SignalDirection.SHORT
    
    @pytest.mark.asyncio
    async def test_neutral_direction_mapping(self, mock_indicators, mock_structure, mock_price_data):
        """Test NEUTRAL direction is correctly mapped."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.NEUTRAL,
            strategy="test_strategy",
            confidence=0.5,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=105.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.direction == SignalDirection.NEUTRAL


class TestMetadataPreservation:
    """Test metadata preservation from legacy signals."""
    
    @pytest.mark.asyncio
    async def test_strategy_name_in_metadata(self, mock_indicators, mock_structure, mock_price_data):
        """Test strategy name is preserved in metadata."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="trendline_pullback",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(name="trendline_pullback", signals=[signal])
        adapter = StrategyAdapter(strategy, "structural")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert "strategy_name" in result.metadata
        assert result.metadata["strategy_name"] == "trendline_pullback"
    
    @pytest.mark.asyncio
    async def test_timeframe_in_metadata(self, mock_indicators, mock_structure, mock_price_data):
        """Test timeframe is preserved in metadata."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M15,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M15,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert "timeframe" in result.metadata
        assert result.metadata["timeframe"] == Timeframe.M15.value
    
    @pytest.mark.asyncio
    async def test_confidence_in_metadata(self, mock_indicators, mock_structure, mock_price_data):
        """Test confidence is preserved in metadata."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.85,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert "confidence" in result.metadata
        assert result.metadata["confidence"] == 0.85
    
    @pytest.mark.asyncio
    async def test_price_levels_in_metadata(self, mock_indicators, mock_structure, mock_price_data):
        """Test entry, stop loss, and take profit are preserved in metadata."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.metadata["entry_price"] == 100.0
        assert result.metadata["stop_loss"] == 95.0
        assert result.metadata["take_profit"] == 110.0
    
    @pytest.mark.asyncio
    async def test_risk_reward_ratio_in_metadata(self, mock_indicators, mock_structure, mock_price_data):
        """Test risk/reward ratio is preserved in metadata."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert "risk_reward_ratio" in result.metadata
        # Risk = 5, Reward = 10, R/R = 2.0
        assert result.metadata["risk_reward_ratio"] == 2.0
    
    @pytest.mark.asyncio
    async def test_strategy_specific_metadata(self, mock_indicators, mock_structure, mock_price_data):
        """Test strategy-specific metadata is preserved with prefix."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
            metadata={
                "trendline_touches": 3,
                "ema_alignment": True,
                "rsi_value": 55.0,
            },
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "structural")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert "strategy_trendline_touches" in result.metadata
        assert result.metadata["strategy_trendline_touches"] == 3
        assert "strategy_ema_alignment" in result.metadata
        assert result.metadata["strategy_ema_alignment"] is True
        assert "strategy_rsi_value" in result.metadata
        assert result.metadata["strategy_rsi_value"] == 55.0


class TestSignalHandling:
    """Test handling of different signal scenarios."""
    
    @pytest.mark.asyncio
    async def test_no_signals_returns_neutral(self, mock_indicators, mock_structure, mock_price_data):
        """Test that no signals returns a neutral SignalResult."""
        strategy = MockStrategy(signals=[])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.score == 0.0
        assert result.direction == SignalDirection.NEUTRAL
        assert result.is_valid is False
        assert result.metadata["reason"] == "no_signal_generated"
    
    @pytest.mark.asyncio
    async def test_single_signal(self, mock_indicators, mock_structure, mock_price_data):
        """Test handling of a single signal."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.score == 0.7
        assert result.direction == SignalDirection.LONG
        assert result.is_valid is True
    
    @pytest.mark.asyncio
    async def test_multiple_signals_takes_highest_confidence(self, mock_indicators, mock_structure, mock_price_data):
        """Test that multiple signals returns the one with highest confidence."""
        signal1 = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.5,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        signal2 = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.9,
            entry_price=101.0,
            stop_loss=96.0,
            take_profit=111.0,
            timeframe=Timeframe.M5,
        )
        
        signal3 = Signal(
            symbol="AAPL",
            direction=Direction.SHORT,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=105.0,
            take_profit=90.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal1, signal2, signal3])
        adapter = StrategyAdapter(strategy, "momentum")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        # Should select signal2 with confidence 0.9
        assert result.score == 0.9
        assert result.direction == SignalDirection.LONG
        assert result.metadata["confidence"] == 0.9
        assert result.metadata["entry_price"] == 101.0


class TestFamilyName:
    """Test family name assignment."""
    
    @pytest.mark.asyncio
    async def test_family_name_preserved(self, mock_indicators, mock_structure, mock_price_data):
        """Test that family name is correctly set in SignalResult."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        adapter = StrategyAdapter(strategy, "structural")
        
        result = await adapter.generate_signal(
            symbol="AAPL",
            timeframe=Timeframe.M5,
            indicators=mock_indicators,
            structure=mock_structure,
            **mock_price_data,
        )
        
        assert result.family_name == "structural"
    
    @pytest.mark.asyncio
    async def test_different_family_names(self, mock_indicators, mock_structure, mock_price_data):
        """Test adapters with different family names."""
        signal = Signal(
            symbol="AAPL",
            direction=Direction.LONG,
            strategy="test_strategy",
            confidence=0.7,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe=Timeframe.M5,
        )
        
        strategy = MockStrategy(signals=[signal])
        
        families = ["momentum", "mean_reversion", "breakout", "structural", "microstructure"]
        
        for family in families:
            adapter = StrategyAdapter(strategy, family)
            result = await adapter.generate_signal(
                symbol="AAPL",
                timeframe=Timeframe.M5,
                indicators=mock_indicators,
                structure=mock_structure,
                **mock_price_data,
            )
            assert result.family_name == family
