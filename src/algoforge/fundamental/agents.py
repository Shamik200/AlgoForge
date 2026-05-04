"""Multi-Agent Fundamental Analyst Personas (Phase 12).

SwarmTrader-inspired LLM analyst personas using structured Pydantic outputs
for explicit reasoning and consensus scoring weighted by historical accuracy.
"""

import json
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

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


# --- Pydantic Schemas for Structured LLM Output ---

class AnalystOpinion(BaseModel):
    """Structured output from a single specialist analyst."""
    persona: str = Field(description="The persona evaluating (Value, Growth, Momentum, Sentiment)")
    score: float = Field(ge=-1.0, le=1.0, description="Directional conviction score from -1.0 (bearish) to 1.0 (bullish)")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this evaluation")
    reasoning: list[str] = Field(description="Bullet points of core reasoning")
    flags: list[str] = Field(description="Any critical warning flags to alert the consensus layer")


class ConsensusOutput(BaseModel):
    """Final output from the consensus lead analyst."""
    symbol: str
    composite_score: float = Field(ge=-1.0, le=1.0)
    decision: str = Field(description="BUY, HOLD, or SELL")
    allocation_weight: float = Field(ge=0.0, le=1.0)
    consensus_summary: str = Field(description="One paragraph summarizing the multi-agent consensus")


# --- Mock LLM Client (Replace with real OpenAI/Anthropic client in production) ---

class MockLLMClient:
    """Mock LLM that returns deterministic Pydantic objects based on inputs."""
    
    def analyze(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        # Dummy implementations that respond to metrics
        if "Value Analyst" in prompt:
            score = 0.5 if "pe_ratio" in prompt and "10" in prompt else 0.0
            return AnalystOpinion(
                persona="Value", score=score, confidence=0.8,
                reasoning=["PE is attractive", "FCF yield is strong"], flags=[]
            )
        elif "Growth Analyst" in prompt:
            score = 0.6 if "revenue_growth" in prompt else 0.1
            return AnalystOpinion(
                persona="Growth", score=score, confidence=0.7,
                reasoning=["Revenue growth > 20%", "Margin expansion visible"], flags=[]
            )
        elif "Momentum Analyst" in prompt:
            return AnalystOpinion(
                persona="Momentum", score=0.4, confidence=0.9,
                reasoning=["Strong relative strength", "Breakout confirmed"], flags=["Overbought RSI"]
            )
        elif "Sentiment Analyst" in prompt:
            return AnalystOpinion(
                persona="Sentiment", score=0.2, confidence=0.6,
                reasoning=["News flow is slightly positive", "No major scandals"], flags=[]
            )
        elif "Consensus" in prompt:
            return ConsensusOutput(
                symbol="UNKNOWN", composite_score=0.45, decision="BUY",
                allocation_weight=0.5, consensus_summary="All analysts lean positive."
            )
        return schema.model_construct()


# --- Analyst Personas ---

class BaseAnalystAgent:
    """Base class for LLM-powered fundamental analysts."""
    def __init__(self, llm_client=None, historical_accuracy: float = 1.0):
        self.llm = llm_client or MockLLMClient()
        self.historical_accuracy = historical_accuracy
        
    def evaluate(self, symbol: str, data: dict[str, Any]) -> AnalystOpinion:
        prompt = self._build_prompt(symbol, data)
        opinion = self.llm.analyze(prompt, AnalystOpinion)
        # Weight confidence by historical track record (Phase 12 requirement)
        opinion.confidence *= self.historical_accuracy
        return opinion
        
    def _build_prompt(self, symbol: str, data: dict[str, Any]) -> str:
        raise NotImplementedError


class ValueAnalystAgent(BaseAnalystAgent):
    def _build_prompt(self, symbol: str, data: dict[str, Any]) -> str:
        return f"You are a Value Analyst. Evaluate {symbol} given metrics: {json.dumps(data)}"


class GrowthAnalystAgent(BaseAnalystAgent):
    def _build_prompt(self, symbol: str, data: dict[str, Any]) -> str:
        return f"You are a Growth Analyst. Evaluate {symbol} given metrics: {json.dumps(data)}"


class MomentumAnalystAgent(BaseAnalystAgent):
    def _build_prompt(self, symbol: str, data: dict[str, Any]) -> str:
        return f"You are a Momentum/Technicals Analyst. Evaluate {symbol} given metrics: {json.dumps(data)}"


class SentimentAnalystAgent(BaseAnalystAgent):
    def _build_prompt(self, symbol: str, data: dict[str, Any]) -> str:
        return f"You are a Sentiment Analyst. Evaluate {symbol} news: {json.dumps(data)}"


class AnalystConsensusAgent:
    """Lead Analyst that aggregates persona opinions into a final portfolio decision."""
    
    def __init__(self, llm_client=None):
        self.llm = llm_client or MockLLMClient()
        
    def run(self, symbol: str, opinions: list[AnalystOpinion]) -> StockSelection:
        """Score consensus from multiple agents weighted by their historical accuracy."""
        if not opinions:
            return StockSelection(symbol=symbol, confidence=0, allocation_weight=0.0)
            
        # Mathematical consensus fallback
        weighted_score = sum(o.score * o.confidence for o in opinions)
        total_confidence = sum(o.confidence for o in opinions)
        
        composite = weighted_score / total_confidence if total_confidence > 0 else 0.0
        
        # In a full system, we pass opinions to LLM to debate and output ConsensusOutput.
        # For now, we use the math consensus.
        
        # Map composite [-1, 1] to confidence [0, 100]
        confidence = int((composite + 1.0) / 2.0 * 100)
        
        weight = 0.0
        if confidence > 65:
            weight = (confidence - 65) / 35.0  # Linear scaling
            
        reasoning = f"Consensus of {len(opinions)} analysts. "
        for o in opinions:
            reasoning += f"[{o.persona}: {o.score:.2f}] "
            
        return StockSelection(
            symbol=symbol,
            confidence=confidence,
            allocation_weight=round(weight, 3),
            reasoning=reasoning
        )


# --- Legacy Adapters to keep existing code functional ---

class NewsSentimentAgent:
    """Legacy adapter for the old NewsSentimentAgent interface."""
    def run(self, symbol: str, news_items: list[NewsItem]) -> NewsSentimentResult:
        # Use new SentimentAnalystAgent internally
        agent = SentimentAnalystAgent()
        opinion = agent.evaluate(symbol, {"items": [n.headline for n in news_items]})
        
        overall = opinion.score
        if overall <= -0.6:
            level = SentimentLevel.VERY_BEARISH
        elif overall >= 0.6:
            level = SentimentLevel.VERY_BULLISH
        else:
            level = SentimentLevel.NEUTRAL
            
        return NewsSentimentResult(
            symbol=symbol, overall_sentiment=overall,
            sentiment_level=level, news_count=len(news_items), items=news_items
        )


class FinancialScreenerAgent:
    """Legacy adapter for the old FinancialScreenerAgent."""
    def run(self, metrics: FinancialMetrics) -> ScreenerResult:
        # Basic mapping to satisfy the pipeline
        score = 50.0
        return ScreenerResult(
            symbol=metrics.symbol, valuation_score=score, profitability_score=score,
            growth_score=score, leverage_score=score, quality_score=score,
            composite_score=score, metrics=metrics
        )


class MacroAnalystAgent:
    """Legacy adapter for Macro analysis."""
    def run(self, macro: MacroEnvironment) -> MacroResult:
        return MacroResult(environment_score=50.0, risk_regime="neutral", macro=macro)


class StockSelectorAgent:
    """Legacy adapter that uses the new Multi-Agent Consensus."""
    def run(self, symbol: str, sentiment: NewsSentimentResult, screener: ScreenerResult, macro: MacroResult) -> StockSelection:
        # Instantiate the personas
        val_agent = ValueAnalystAgent(historical_accuracy=1.2) # High accuracy
        gro_agent = GrowthAnalystAgent(historical_accuracy=0.9)
        mom_agent = MomentumAnalystAgent(historical_accuracy=1.0)
        sent_agent = SentimentAnalystAgent(historical_accuracy=0.8)
        
        # Gather opinions
        opinions = [
            val_agent.evaluate(symbol, {"pe": screener.metrics.pe_ratio if screener.metrics else None}),
            gro_agent.evaluate(symbol, {"growth": screener.metrics.revenue_growth_yoy if screener.metrics else None}),
            mom_agent.evaluate(symbol, {"regime": macro.risk_regime}),
            sent_agent.evaluate(symbol, {"score": sentiment.overall_sentiment})
        ]
        
        # Lead analyst debates and decides
        lead = AnalystConsensusAgent()
        return lead.run(symbol, opinions)
