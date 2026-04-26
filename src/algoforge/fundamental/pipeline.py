"""Fundamental Analysis Pipeline orchestrator."""

import logging

from algoforge.fundamental.agents import (
    FinancialScreenerAgent,
    MacroAnalystAgent,
    NewsSentimentAgent,
    StockSelectorAgent,
)
from algoforge.fundamental.models import (
    FinancialMetrics,
    FundamentalResult,
    MacroEnvironment,
    NewsItem,
)

logger = logging.getLogger(__name__)


class FundamentalPipeline:
    """Orchestrates the 4 fundamental analysis agents sequentially.

    In a full LangGraph implementation, this would be a LangGraph workflow
    with error recovery and retries. For now, it's a simple sequential pipeline.
    """

    def __init__(self, gate_threshold: int = 40) -> None:
        """Initialize the pipeline.

        Args:
            gate_threshold: Minimum gate_score (0-100) to allow technical signals.
                            Below this, technical analysis is blocked for the instrument.
        """
        self.gate_threshold = gate_threshold
        self.news_agent = NewsSentimentAgent()
        self.screener_agent = FinancialScreenerAgent()
        self.macro_agent = MacroAnalystAgent()
        self.selector_agent = StockSelectorAgent()

    def analyze(
        self,
        symbol: str,
        news_items: list[NewsItem] | None = None,
        metrics: FinancialMetrics | None = None,
        macro: MacroEnvironment | None = None,
    ) -> FundamentalResult:
        """Run the full fundamental analysis pipeline.

        Args:
            symbol: Instrument to analyze.
            news_items: Pre-fetched news items (or empty for no news).
            metrics: Pre-fetched financial metrics (or None for defaults).
            macro: Current macro environment (or None for defaults).

        Returns:
            FundamentalResult with gate_score and detailed breakdowns.
        """
        logger.info("[FundamentalPipeline] Analyzing %s", symbol)

        # Agent 1: News Sentiment
        sentiment_result = self.news_agent.run(symbol, news_items or [])

        # Agent 2: Financial Screener
        if metrics is None:
            metrics = FinancialMetrics(symbol=symbol)
        screener_result = self.screener_agent.run(metrics)

        # Agent 3: Macro Environment
        if macro is None:
            macro = MacroEnvironment()
        macro_result = self.macro_agent.run(macro)

        # Agent 4: Stock Selector
        selection = self.selector_agent.run(
            symbol, sentiment_result, screener_result, macro_result
        )

        # The gate_score IS the selector's confidence
        gate_score = selection.confidence

        logger.info(
            "[FundamentalPipeline] %s gate_score=%d (threshold=%d) → %s",
            symbol, gate_score, self.gate_threshold,
            "PASS" if gate_score >= self.gate_threshold else "BLOCKED"
        )

        return FundamentalResult(
            symbol=symbol,
            gate_score=gate_score,
            sentiment=sentiment_result,
            screener=screener_result,
            macro=macro_result,
            selections=[selection],
        )

    def should_allow_trading(self, result: FundamentalResult) -> bool:
        """Check if the fundamental gate allows technical trading.

        Args:
            result: The FundamentalResult from `analyze()`.

        Returns:
            True if the gate_score meets the threshold.
        """
        return result.gate_score >= self.gate_threshold
