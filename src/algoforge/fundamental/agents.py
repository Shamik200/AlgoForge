"""Individual fundamental analysis agents."""

import logging
from datetime import datetime

from algoforge.fundamental.models import (
    FinancialMetrics,
    MacroEnvironment,
    MacroResult,
    NewsItem,
    NewsSentimentResult,
    ScreenerResult,
    SentimentLevel,
    StockSelection,
)

logger = logging.getLogger(__name__)


class NewsSentimentAgent:
    """Agent 1: News Sentiment Analysis.

    In production, this would call FinBERT or an LLM API to score headlines.
    For now, it accepts pre-scored NewsItems and computes the aggregate.
    """

    def run(self, symbol: str, news_items: list[NewsItem]) -> NewsSentimentResult:
        """Aggregate sentiment from multiple news sources with recency weighting.

        Args:
            symbol: The instrument symbol.
            news_items: Pre-scored news items.

        Returns:
            NewsSentimentResult with weighted aggregate sentiment.
        """
        if not news_items:
            return NewsSentimentResult(
                symbol=symbol, overall_sentiment=0.0,
                sentiment_level=SentimentLevel.NEUTRAL, news_count=0
            )

        # Recency weighting: more recent items get higher weight
        now = datetime.now()
        weighted_sum = 0.0
        weight_total = 0.0

        for item in news_items:
            age_hours = max(1, (now - item.published_at).total_seconds() / 3600)
            recency_weight = 1.0 / (1.0 + (age_hours / 24.0))  # Decay over days
            effective_weight = recency_weight * item.relevance

            weighted_sum += item.sentiment_score * effective_weight
            weight_total += effective_weight

        overall = weighted_sum / weight_total if weight_total > 0 else 0.0
        overall = max(-1.0, min(1.0, overall))

        # Classify
        if overall <= -0.6:
            level = SentimentLevel.VERY_BEARISH
        elif overall <= -0.2:
            level = SentimentLevel.BEARISH
        elif overall >= 0.6:
            level = SentimentLevel.VERY_BULLISH
        elif overall >= 0.2:
            level = SentimentLevel.BULLISH
        else:
            level = SentimentLevel.NEUTRAL

        return NewsSentimentResult(
            symbol=symbol, overall_sentiment=overall,
            sentiment_level=level, news_count=len(news_items), items=news_items
        )


class FinancialScreenerAgent:
    """Agent 2: Financial Metrics Screener.

    Scores 5 dimensions of fundamental quality on a 0-100 scale.
    """

    def run(self, metrics: FinancialMetrics) -> ScreenerResult:
        """Score fundamental metrics across 5 dimensions.

        Args:
            metrics: The financial metrics for the instrument.

        Returns:
            ScreenerResult with dimension scores and composite.
        """
        valuation = self._score_valuation(metrics)
        profitability = self._score_profitability(metrics)
        growth = self._score_growth(metrics)
        leverage = self._score_leverage(metrics)
        quality = self._score_quality(metrics)

        # Weighted composite: profitability and quality matter most
        composite = (
            valuation * 0.20 +
            profitability * 0.25 +
            growth * 0.20 +
            leverage * 0.15 +
            quality * 0.20
        )

        return ScreenerResult(
            symbol=metrics.symbol,
            valuation_score=valuation,
            profitability_score=profitability,
            growth_score=growth,
            leverage_score=leverage,
            quality_score=quality,
            composite_score=composite,
            metrics=metrics,
        )

    def _score_valuation(self, m: FinancialMetrics) -> float:
        """Score valuation metrics (lower PE/PB = better, 0-100)."""
        score = 50.0  # Default neutral
        if m.pe_ratio is not None:
            if m.pe_ratio < 0:
                score -= 20  # Negative earnings
            elif m.pe_ratio < 15:
                score += 30
            elif m.pe_ratio < 25:
                score += 10
            else:
                score -= 15
        if m.pb_ratio is not None:
            if m.pb_ratio < 1.5:
                score += 15
            elif m.pb_ratio > 5:
                score -= 15
        return max(0, min(100, score))

    def _score_profitability(self, m: FinancialMetrics) -> float:
        """Score profitability metrics (higher ROE/margins = better)."""
        score = 50.0
        if m.roe is not None:
            if m.roe > 0.20:
                score += 25
            elif m.roe > 0.10:
                score += 10
            elif m.roe < 0:
                score -= 25
        if m.net_margin is not None:
            if m.net_margin > 0.15:
                score += 15
            elif m.net_margin < 0:
                score -= 20
        return max(0, min(100, score))

    def _score_growth(self, m: FinancialMetrics) -> float:
        """Score growth metrics (higher growth = better)."""
        score = 50.0
        if m.revenue_growth_yoy is not None:
            if m.revenue_growth_yoy > 0.20:
                score += 25
            elif m.revenue_growth_yoy > 0.05:
                score += 10
            elif m.revenue_growth_yoy < 0:
                score -= 20
        if m.earnings_growth_yoy is not None:
            if m.earnings_growth_yoy > 0.25:
                score += 15
            elif m.earnings_growth_yoy < -0.10:
                score -= 15
        return max(0, min(100, score))

    def _score_leverage(self, m: FinancialMetrics) -> float:
        """Score leverage metrics (lower debt = better)."""
        score = 50.0
        if m.debt_to_equity is not None:
            if m.debt_to_equity < 0.5:
                score += 25
            elif m.debt_to_equity < 1.0:
                score += 10
            elif m.debt_to_equity > 2.0:
                score -= 25
        if m.current_ratio is not None:
            if m.current_ratio > 2.0:
                score += 15
            elif m.current_ratio < 1.0:
                score -= 20
        return max(0, min(100, score))

    def _score_quality(self, m: FinancialMetrics) -> float:
        """Score quality metrics (FCF, dividends)."""
        score = 50.0
        if m.free_cash_flow is not None:
            if m.free_cash_flow > 0:
                score += 20
            else:
                score -= 15
        if m.dividend_yield is not None:
            if m.dividend_yield > 0.02:
                score += 10
        return max(0, min(100, score))


class MacroAnalystAgent:
    """Agent 3: Sector/Macro Environment Analyst."""

    def run(self, macro: MacroEnvironment) -> MacroResult:
        """Evaluate the macro environment and classify the risk regime.

        Args:
            macro: Current macro indicators.

        Returns:
            MacroResult with environment score and regime classification.
        """
        score = 50.0  # Neutral baseline

        # VIX assessment
        if macro.vix is not None:
            if macro.vix < 15:
                score += 15  # Low volatility = risk on
            elif macro.vix > 30:
                score -= 20  # High fear = risk off
            elif macro.vix > 20:
                score -= 10

        # GDP growth
        if macro.gdp_growth is not None:
            if macro.gdp_growth > 0.03:
                score += 15
            elif macro.gdp_growth < 0:
                score -= 20

        # Interest rates (higher = tighter = worse for equities)
        if macro.interest_rate is not None:
            if macro.interest_rate > 0.05:
                score -= 15
            elif macro.interest_rate < 0.02:
                score += 10

        # Inflation
        if macro.inflation_rate is not None:
            if macro.inflation_rate > 0.06:
                score -= 15  # High inflation = bad
            elif macro.inflation_rate < 0.03:
                score += 10

        score = max(0, min(100, score))

        # Classify regime
        if score >= 65:
            regime = "risk_on"
        elif score <= 35:
            regime = "risk_off"
        else:
            regime = "neutral"

        return MacroResult(environment_score=score, risk_regime=regime, macro=macro)


class StockSelectorAgent:
    """Agent 4: Stock Selector / Confidence Scorer.

    Combines sentiment, screener, and macro outputs to produce
    a ranked watchlist with confidence and allocation weights.
    """

    def run(
        self,
        symbol: str,
        sentiment: NewsSentimentResult,
        screener: ScreenerResult,
        macro: MacroResult,
    ) -> StockSelection:
        """Produce a stock selection with confidence and allocation.

        Args:
            symbol: The instrument symbol.
            sentiment: News sentiment result.
            screener: Financial screening result.
            macro: Macro environment result.

        Returns:
            StockSelection with confidence (0-100) and allocation weight.
        """
        # Combine: Screener fundamentals (50%) + Sentiment (25%) + Macro (25%)
        sentiment_score_normalized = (sentiment.overall_sentiment + 1.0) / 2.0 * 100  # [-1,1] → [0,100]

        raw_confidence = (
            screener.composite_score * 0.50 +
            sentiment_score_normalized * 0.25 +
            macro.environment_score * 0.25
        )

        confidence = int(max(0, min(100, raw_confidence)))

        # Allocation weight: scale linearly from confidence
        # Below 30 = 0 allocation, 30-70 = linear, 70+ = maximum
        if confidence < 30:
            weight = 0.0
        elif confidence > 70:
            weight = 1.0
        else:
            weight = (confidence - 30) / 40.0

        reasoning = (
            f"Fundamentals: {screener.composite_score:.0f}/100, "
            f"Sentiment: {sentiment.overall_sentiment:+.2f}, "
            f"Macro: {macro.risk_regime}"
        )

        return StockSelection(
            symbol=symbol, confidence=confidence,
            allocation_weight=round(weight, 3), reasoning=reasoning
        )
