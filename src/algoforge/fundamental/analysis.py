"""Fundamental Analysis Module — News and economic event filtering.

Provides sentiment scoring from configurable data sources and
economic calendar integration to filter/boost signals.

Requirements: FUND-01 to FUND-06
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class Sentiment(str, Enum):
    """Market sentiment classification."""

    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class EconomicEvent(BaseModel):
    """Economic calendar event."""

    name: str
    currency: str
    importance: str = Field(default="medium", description="low/medium/high")
    timestamp: datetime
    actual: float | None = None
    forecast: float | None = None
    previous: float | None = None


class FundamentalSnapshot(BaseModel):
    """Point-in-time fundamental data for a symbol."""

    symbol: str
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    upcoming_events: list[EconomicEvent] = Field(default_factory=list)
    sector: str = ""
    has_earnings_soon: bool = False
    news_volume: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FundamentalFilter:
    """Filter/adjust signals based on fundamental data.

    FUND-01: Sentiment must not contradict signal direction
    FUND-02: Block trading during high-impact events
    FUND-03: Boost/reduce confidence based on sentiment alignment
    FUND-04: Earnings blackout period
    FUND-05: News volume threshold for volatility warning
    FUND-06: Fundamental analysis must complete before technical

    Usage:
        ff = FundamentalFilter()
        approved = ff.filter(signals, fundamentals)
    """

    def __init__(
        self,
        block_high_impact: bool = True,
        earnings_blackout: bool = True,
        sentiment_boost: float = 0.1,
        sentiment_penalty: float = 0.15,
        news_volume_warning: int = 50,
        event_window_minutes: int = 30,
    ) -> None:
        self._block_high = block_high_impact
        self._earnings_blackout = earnings_blackout
        self._sentiment_boost = sentiment_boost
        self._sentiment_penalty = sentiment_penalty
        self._news_vol_warn = news_volume_warning
        self._event_window = event_window_minutes

    def filter(
        self,
        signals: list[Any],
        fundamentals: dict[str, FundamentalSnapshot],
    ) -> list[Any]:
        """Filter signals through fundamental checks."""
        approved = []

        for sig in signals:
            snap = fundamentals.get(sig.symbol)
            if not snap:
                # No fundamental data → pass through (conservative)
                approved.append(sig)
                continue

            reasons: list[str] = []

            # FUND-04: Earnings blackout
            if self._earnings_blackout and snap.has_earnings_soon:
                reasons.append("FUND-04: Earnings blackout period")

            # FUND-02: High-impact event blocking
            if self._block_high:
                high_events = [
                    e for e in snap.upcoming_events
                    if e.importance == "high"
                ]
                if high_events:
                    reasons.append(f"FUND-02: {len(high_events)} high-impact events pending")

            # FUND-01: Sentiment contradiction
            if sig.direction.value == "long" and snap.sentiment in (Sentiment.VERY_BEARISH, Sentiment.BEARISH):
                if snap.sentiment == Sentiment.VERY_BEARISH:
                    reasons.append("FUND-01: Very bearish sentiment contradicts LONG")
                else:
                    # Bearish → penalty but don't block
                    pass

            if sig.direction.value == "short" and snap.sentiment in (Sentiment.VERY_BULLISH, Sentiment.BULLISH):
                if snap.sentiment == Sentiment.VERY_BULLISH:
                    reasons.append("FUND-01: Very bullish sentiment contradicts SHORT")

            if reasons:
                logger.debug("fundamental_rejected", symbol=sig.symbol, reasons=reasons)
                continue

            # FUND-03: Confidence adjustment
            adjusted = self._adjust_confidence(sig, snap)
            approved.append(adjusted)

        logger.info(
            "fundamental_filter",
            input_count=len(signals),
            approved_count=len(approved),
        )
        return approved

    def _adjust_confidence(self, signal: Any, snap: FundamentalSnapshot) -> Any:
        """Boost or reduce confidence based on sentiment alignment."""
        boost = 0.0

        if signal.direction.value == "long":
            if snap.sentiment == Sentiment.VERY_BULLISH:
                boost = self._sentiment_boost
            elif snap.sentiment == Sentiment.BULLISH:
                boost = self._sentiment_boost * 0.5
            elif snap.sentiment == Sentiment.BEARISH:
                boost = -self._sentiment_penalty * 0.5
        else:
            if snap.sentiment == Sentiment.VERY_BEARISH:
                boost = self._sentiment_boost
            elif snap.sentiment == Sentiment.BEARISH:
                boost = self._sentiment_boost * 0.5
            elif snap.sentiment == Sentiment.BULLISH:
                boost = -self._sentiment_penalty * 0.5

        if boost != 0:
            new_conf = max(0.1, min(0.95, signal.confidence + boost))
            return signal.model_copy(update={"confidence": new_conf})

        return signal
