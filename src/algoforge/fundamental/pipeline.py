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

        # Optional external Fundamental-System adapter
        try:
            from algoforge.fundamental.external_adapter import available as _ext_available
            from algoforge.fundamental import external_adapter as _ext_adapter
        except Exception:
            _ext_adapter = None
            _ext_available = lambda: False

        self._external_adapter = _ext_adapter if _ext_available() else None

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
        # If an external system is available, prefer its live news ingestion
        if self._external_adapter and (news_items is None or not news_items):
            external_news = self._external_adapter.fetch_live_news()
            if external_news:
                # Map external news dicts to NewsItem dataclass shape
                mapped = []
                for n in external_news:
                    mapped.append(NewsItem(
                        headline=n.get("headline") or n.get("title") or str(n),
                        source=n.get("source") or n.get("domain", "external"),
                        published_at=getattr(n.get("published_at"), "isoformat", lambda: None)(),
                        sentiment_score=0.0,
                        relevance=1.0,
                    ))
                sentiment_result = self.news_agent.run(symbol, mapped)
            else:
                sentiment_result = self.news_agent.run(symbol, news_items or [])
        else:
            sentiment_result = self.news_agent.run(symbol, news_items or [])

        # Agent 2: Financial Screener
        if metrics is None:
            metrics = FinancialMetrics(symbol=symbol)
        screener_result = self.screener_agent.run(metrics)

        # Agent 3: Macro Environment
        # Prefer external macro data if available
        if self._external_adapter and macro is None:
            external_macro = self._external_adapter.fetch_macro_data()
            if external_macro:
                try:
                    macro = MacroEnvironment(
                        gdp_growth=float(external_macro.get("GDP_GROWTH", 0.0)) if external_macro.get("GDP_GROWTH") else None,
                        inflation_rate=float(external_macro.get("US_CPI", "0").strip("%")) if external_macro.get("US_CPI") else None,
                        vix=float(external_macro.get("VIX", 0.0)) if external_macro.get("VIX") else None,
                        dxy=None,
                    )
                except Exception:
                    macro = MacroEnvironment()
            else:
                macro = MacroEnvironment()
        elif macro is None:
            macro = MacroEnvironment()
        macro_result = self.macro_agent.run(macro)

        # Agent 4: Stock Selector
        selection = self.selector_agent.run(
            symbol, sentiment_result, screener_result, macro_result
        )

        # The gate_score IS the selector's confidence
        gate_score = selection.confidence

        # NEW LLM LAYER: Fundamental Context Summarization
        try:
            from algoforge.llm.client import FinLLMClient
            from algoforge.llm.prompts import PromptBuilder
            from algoforge.llm.schemas import FundamentalSummary
            llm = FinLLMClient()
            data_dict = {
                "sentiment": sentiment_result.overall_sentiment,
                "macro": macro_result.environment_score,
                "confidence": selection.confidence
            }
            prompt = PromptBuilder.build_fundamental_prompt(symbol, data_dict)
            llm_summary = llm.analyze(prompt, FundamentalSummary)
            # If LLM strongly blocks, we can override gate_score
            if llm_summary.recommendation == "BLOCK":
                gate_score = min(gate_score, self.gate_threshold - 1)
        except Exception as e:
            logger.warning("[FundamentalPipeline] LLM Assistant failed: %s", e)
            llm_summary = None

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
            llm_summary=llm_summary,
        )

    def should_allow_trading(self, result: FundamentalResult) -> bool:
        """Check if the fundamental gate allows technical trading.

        Args:
            result: The FundamentalResult from `analyze()`.

        Returns:
            True if the gate_score meets the threshold.
        """
        return result.gate_score >= self.gate_threshold
