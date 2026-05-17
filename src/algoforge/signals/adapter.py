"""Strategy Adapter for Legacy Strategy Integration.

This module provides the StrategyAdapter class that converts legacy Strategy
outputs (Signal objects) into standardized SignalResult objects for use in
the signal combination framework.

The adapter:
- Normalizes signal scores to [-1, 1] range
- Maps Direction enum to SignalDirection enum
- Preserves strategy metadata (name, timeframe, confidence)
- Validates output bounds
"""

from __future__ import annotations

from algoforge.core.constants import Direction, Timeframe
from algoforge.core.models import Signal
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.strategies.base import Strategy
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot


class StrategyAdapter:
    """Adapts legacy strategies to the SignalResult interface.
    
    This adapter allows legacy Strategy implementations to participate in
    the signal combination framework by converting their Signal outputs
    into standardized SignalResult objects.
    
    The adapter performs:
    - Score normalization to [-1, 1] range
    - Direction mapping (Direction -> SignalDirection)
    - Metadata preservation (strategy name, timeframe, confidence)
    - Output validation
    
    Example:
        >>> strategy = TrendlinePullbackStrategy()
        >>> adapter = StrategyAdapter(strategy, "structural")
        >>> signal_result = await adapter.generate_signal(
        ...     symbol="AAPL",
        ...     timeframe=Timeframe.M5,
        ...     indicators=indicators,
        ...     structure=structure,
        ...     closes=closes,
        ...     highs=highs,
        ...     lows=lows,
        ...     volumes=volumes,
        ...     opens=opens
        ... )
    """
    
    def __init__(self, strategy: Strategy, family_name: str) -> None:
        """Initialize adapter with a strategy instance and its signal family.
        
        Args:
            strategy: The legacy Strategy instance to adapt
            family_name: The signal family this strategy belongs to
                        (e.g., "momentum", "mean_reversion", "breakout", "structural")
        """
        self.strategy = strategy
        self.family_name = family_name
    
    async def generate_signal(
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
    ) -> SignalResult:
        """Convert strategy output to SignalResult.
        
        Calls the legacy strategy's evaluate() method and converts the
        resulting Signal(s) into a standardized SignalResult.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe being analyzed
            indicators: All indicator results for this symbol/timeframe
            structure: S/R levels, trendlines, trend direction
            closes: Historical close prices
            highs: Historical high prices
            lows: Historical low prices
            volumes: Historical volumes
            opens: Historical open prices
        
        Returns:
            SignalResult with score normalized to [-1, 1], direction mapped
            to SignalDirection, and metadata preserved.
            
            If the strategy returns no signals or multiple signals, the adapter
            will aggregate them appropriately:
            - No signals: returns neutral signal with score 0.0
            - Multiple signals: returns the signal with highest confidence
        """
        # Call the legacy strategy's evaluate method
        signals: list[Signal] = self.strategy.evaluate(
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
            structure=structure,
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            opens=opens,
        )
        
        # Handle no signals case
        if not signals:
            return SignalResult(
                family_name=self.family_name,
                score=0.0,
                direction=SignalDirection.NEUTRAL,
                is_valid=False,
                metadata={
                    "strategy_name": self.strategy.name,
                    "timeframe": timeframe.value,
                    "confidence": 0.0,
                    "reason": "no_signal_generated",
                },
            )
        
        # Handle multiple signals - take the one with highest confidence
        signal = max(signals, key=lambda s: s.confidence)
        
        # Normalize score to [-1, 1] range
        # Legacy signals use confidence [0, 1] and direction
        # We map: LONG confidence -> positive score, SHORT confidence -> negative score
        normalized_score = self._normalize_score(signal)
        
        # Map Direction to SignalDirection
        signal_direction = self._map_direction(signal.direction)
        
        # Build metadata dictionary
        metadata = {
            "strategy_name": self.strategy.name,
            "timeframe": timeframe.value,
            "confidence": signal.confidence,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "risk_reward_ratio": signal.risk_reward_ratio,
        }
        
        # Add any strategy-specific metadata
        if signal.metadata:
            metadata.update({f"strategy_{k}": v for k, v in signal.metadata.items()})
        
        return SignalResult(
            family_name=self.family_name,
            score=normalized_score,
            direction=signal_direction,
            is_valid=True,
            metadata=metadata,
        )
    
    def _normalize_score(self, signal: Signal) -> float:
        """Normalize signal confidence to [-1, 1] range.
        
        Converts the legacy Signal's confidence [0, 1] and direction into
        a normalized score:
        - LONG: confidence maps to [0, 1]
        - SHORT: confidence maps to [-1, 0]
        - NEUTRAL: always 0.0
        
        Args:
            signal: The legacy Signal object
        
        Returns:
            Normalized score in [-1, 1] range
        """
        if signal.direction == Direction.LONG:
            score = signal.confidence
        elif signal.direction == Direction.SHORT:
            score = -signal.confidence
        else:  # NEUTRAL
            score = 0.0
        
        # Validate bounds (should always be true, but defensive check)
        score = max(-1.0, min(1.0, score))
        
        return score
    
    def _map_direction(self, direction: Direction) -> SignalDirection:
        """Map legacy Direction enum to SignalDirection enum.
        
        Args:
            direction: Legacy Direction enum value
        
        Returns:
            Corresponding SignalDirection enum value
        """
        mapping = {
            Direction.LONG: SignalDirection.LONG,
            Direction.SHORT: SignalDirection.SHORT,
            Direction.NEUTRAL: SignalDirection.NEUTRAL,
        }
        return mapping[direction]
    
    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"<StrategyAdapter: {self.strategy.name} -> {self.family_name}>"
