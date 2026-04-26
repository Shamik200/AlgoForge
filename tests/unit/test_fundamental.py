"""Unit tests for the Fundamental Analysis Module."""

from datetime import datetime, timedelta

from algoforge.fundamental.models import (
    FinancialMetrics,
    MacroEnvironment,
    NewsItem,
    SentimentLevel,
)
from algoforge.fundamental.agents import (
    NewsSentimentAgent,
    FinancialScreenerAgent,
    MacroAnalystAgent,
    StockSelectorAgent,
)
from algoforge.fundamental.pipeline import FundamentalPipeline


def test_news_sentiment_bullish():
    """Test news sentiment aggregation with bullish headlines."""
    agent = NewsSentimentAgent()
    now = datetime.now()
    items = [
        NewsItem("Stock surges on strong earnings", "Reuters", now, 0.8),
        NewsItem("Record revenue growth", "Bloomberg", now - timedelta(hours=2), 0.7),
        NewsItem("Analyst upgrades to Buy", "CNBC", now - timedelta(hours=6), 0.6),
    ]
    result = agent.run("AAPL", items)

    assert result.overall_sentiment > 0.5
    assert result.sentiment_level in (SentimentLevel.BULLISH, SentimentLevel.VERY_BULLISH)
    assert result.news_count == 3


def test_news_sentiment_bearish():
    """Test news sentiment with bearish headlines."""
    agent = NewsSentimentAgent()
    now = datetime.now()
    items = [
        NewsItem("SEC investigation launched", "WSJ", now, -0.9),
        NewsItem("Revenue misses estimates badly", "Reuters", now - timedelta(hours=1), -0.7),
    ]
    result = agent.run("AAPL", items)

    assert result.overall_sentiment < -0.5
    assert result.sentiment_level in (SentimentLevel.BEARISH, SentimentLevel.VERY_BEARISH)


def test_news_sentiment_empty():
    """Test sentiment returns neutral with no news."""
    agent = NewsSentimentAgent()
    result = agent.run("AAPL", [])

    assert result.overall_sentiment == 0.0
    assert result.sentiment_level == SentimentLevel.NEUTRAL


def test_financial_screener_strong():
    """Test screener scores a fundamentally strong company highly."""
    agent = FinancialScreenerAgent()
    metrics = FinancialMetrics(
        symbol="AAPL",
        pe_ratio=12.0, pb_ratio=1.2,
        roe=0.25, net_margin=0.20,
        revenue_growth_yoy=0.25, earnings_growth_yoy=0.30,
        debt_to_equity=0.3, current_ratio=2.5,
        free_cash_flow=5_000_000_000, dividend_yield=0.03,
    )
    result = agent.run(metrics)

    assert result.composite_score > 70
    assert result.valuation_score > 60
    assert result.profitability_score > 60


def test_financial_screener_weak():
    """Test screener scores a fundamentally weak company low."""
    agent = FinancialScreenerAgent()
    metrics = FinancialMetrics(
        symbol="JUNK",
        pe_ratio=-5.0, pb_ratio=8.0,
        roe=-0.10, net_margin=-0.15,
        revenue_growth_yoy=-0.20, earnings_growth_yoy=-0.30,
        debt_to_equity=3.0, current_ratio=0.5,
        free_cash_flow=-1_000_000, dividend_yield=0.0,
    )
    result = agent.run(metrics)

    assert result.composite_score < 30


def test_macro_risk_on():
    """Test macro agent classifies a favorable environment."""
    agent = MacroAnalystAgent()
    macro = MacroEnvironment(
        gdp_growth=0.04, inflation_rate=0.02,
        interest_rate=0.015, vix=12.0,
    )
    result = agent.run(macro)

    assert result.risk_regime == "risk_on"
    assert result.environment_score > 65


def test_macro_risk_off():
    """Test macro agent classifies a hostile environment."""
    agent = MacroAnalystAgent()
    macro = MacroEnvironment(
        gdp_growth=-0.01, inflation_rate=0.08,
        interest_rate=0.06, vix=35.0,
    )
    result = agent.run(macro)

    assert result.risk_regime == "risk_off"
    assert result.environment_score < 35


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

    assert pipeline.should_allow_trading(result) is True
    assert result.gate_score >= 40
    assert result.sentiment is not None
    assert result.screener is not None
    assert result.macro is not None
    assert len(result.selections) == 1


def test_pipeline_blocked():
    """Test the pipeline blocks a fundamentally terrible stock."""
    pipeline = FundamentalPipeline(gate_threshold=40)
    now = datetime.now()

    result = pipeline.analyze(
        symbol="JUNK",
        news_items=[NewsItem("Fraud investigation", "SEC", now, -0.9)],
        metrics=FinancialMetrics(
            symbol="JUNK", pe_ratio=-5, pb_ratio=8.0,
            roe=-0.15, net_margin=-0.20,
            revenue_growth_yoy=-0.25,
            debt_to_equity=4.0, current_ratio=0.4,
            free_cash_flow=-500_000,
        ),
        macro=MacroEnvironment(gdp_growth=-0.02, vix=40.0, interest_rate=0.07),
    )

    assert pipeline.should_allow_trading(result) is False
    assert result.gate_score < 40
