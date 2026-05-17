"""Unit tests for the Fundamental Analysis Module."""

from datetime import datetime

from algoforge.fundamental import external_adapter
from algoforge.fundamental.models import (
    FinancialMetrics,
    MacroEnvironment,
    NewsItem,
)
from algoforge.fundamental.agents import (
    ValueAnalystAgent,
    GrowthAnalystAgent,
    MomentumAnalystAgent,
    SentimentAnalystAgent,
    AnalystConsensusAgent
)
from algoforge.fundamental.pipeline import FundamentalPipeline


def test_value_analyst():
    """Test Value Analyst parsing."""
    agent = ValueAnalystAgent()
    metrics = {"pe_ratio": 10.0}
    opinion = agent.evaluate("AAPL", metrics)
    assert opinion.persona == "Value"
    assert opinion.score == 0.5


def test_growth_analyst():
    """Test Growth Analyst parsing."""
    agent = GrowthAnalystAgent()
    metrics = {"revenue_growth": 0.25}
    opinion = agent.evaluate("AAPL", metrics)
    assert opinion.persona == "Growth"
    assert opinion.score == 0.6


def test_momentum_analyst():
    """Test Momentum Analyst parsing."""
    agent = MomentumAnalystAgent()
    metrics = {"regime": "risk_on"}
    opinion = agent.evaluate("AAPL", metrics)
    assert opinion.persona == "Momentum"
    assert opinion.score == 0.4


def test_sentiment_analyst():
    """Test Sentiment Analyst parsing."""
    agent = SentimentAnalystAgent()
    metrics = {"items": ["Good news"]}
    opinion = agent.evaluate("AAPL", metrics)
    assert opinion.persona == "Sentiment"
    assert opinion.score == 0.2


def test_consensus_agent():
    """Test consensus agent mathematical aggregation."""
    agent = AnalystConsensusAgent()
    
    # Mathematical consensus of two agents with high score
    from algoforge.fundamental.agents import AnalystOpinion
    opinions = [
        AnalystOpinion(persona="A", score=0.8, confidence=1.0, reasoning=[], flags=[]),
        AnalystOpinion(persona="B", score=0.6, confidence=1.0, reasoning=[], flags=[])
    ]
    
    selection = agent.run("AAPL", opinions)
    
    # Composite = (0.8 + 0.6) / 2 = 0.7.
    # Confidence = int((0.7 + 1.0)/2 * 100) = 85
    assert selection.confidence == 85
    assert selection.allocation_weight > 0.0


def test_pipeline_full_pass():
    """Test the full pipeline produces a passing gate score."""
    pipeline = FundamentalPipeline(gate_threshold=40)
    now = datetime.now()

    result = pipeline.analyze(
        symbol="AAPL",
        news_items=[NewsItem("Strong earnings beat", "Reuters", now, 0.8)],
        metrics=FinancialMetrics(
            symbol="AAPL", pe_ratio=15, pb_ratio=2.0,
            roe=0.20, net_margin=0.18,
            revenue_growth_yoy=0.15, earnings_growth_yoy=0.20,
            debt_to_equity=0.5, current_ratio=2.0,
            free_cash_flow=1_000_000,
        ),
        macro=MacroEnvironment(gdp_growth=0.03, vix=14.0, interest_rate=0.02),
    )

    # With the MockLLMClient, the consensus logic results in a gate score > 40
    assert pipeline.should_allow_trading(result) is True
    assert result.gate_score >= 40
    assert result.sentiment is not None
    assert result.screener is not None
    assert result.macro is not None
    assert len(result.selections) == 1


def test_external_fundamental_adapter_is_available():
    """Test the trading repo can load the sibling Fundamental-System adapter."""
    assert external_adapter.available() is True

    macro_data = external_adapter.fetch_macro_data()
    assert macro_data is not None
    assert "US_CPI" in macro_data
