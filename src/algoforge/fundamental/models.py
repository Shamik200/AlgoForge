"""Data models for the Fundamental Analysis Module."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SentimentLevel(str, Enum):
    """Qualitative sentiment classification."""
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


@dataclass
class NewsItem:
    """A single news item with sentiment scoring."""
    headline: str
    source: str
    published_at: datetime
    sentiment_score: float  # [-1.0, +1.0]
    relevance: float = 1.0  # How relevant to the target instrument


@dataclass
class NewsSentimentResult:
    """Aggregated news sentiment for an instrument."""
    symbol: str
    overall_sentiment: float  # [-1.0, +1.0]
    sentiment_level: SentimentLevel
    news_count: int
    items: list[NewsItem] = field(default_factory=list)


@dataclass
class FinancialMetrics:
    """Key fundamental metrics for screening."""
    symbol: str
    # Valuation
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_ebitda: float | None = None
    # Profitability
    roe: float | None = None
    roa: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    # Growth
    revenue_growth_yoy: float | None = None
    earnings_growth_yoy: float | None = None
    # Leverage
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    # Quality
    free_cash_flow: float | None = None
    dividend_yield: float | None = None


@dataclass
class ScreenerResult:
    """Financial screener output with composite scoring."""
    symbol: str
    valuation_score: float  # 0-100
    profitability_score: float  # 0-100
    growth_score: float  # 0-100
    leverage_score: float  # 0-100
    quality_score: float  # 0-100
    composite_score: float  # 0-100 weighted average
    metrics: FinancialMetrics | None = None


@dataclass
class MacroEnvironment:
    """Macro/sector context."""
    gdp_growth: float | None = None
    inflation_rate: float | None = None
    interest_rate: float | None = None
    vix: float | None = None
    dxy: float | None = None  # Dollar index
    bond_yield_10y: float | None = None
    sector_momentum: dict[str, float] = field(default_factory=dict)


@dataclass
class MacroResult:
    """Macro analysis output."""
    environment_score: float  # 0-100 (higher = favorable)
    risk_regime: str  # "risk_on", "risk_off", "neutral"
    macro: MacroEnvironment | None = None


@dataclass
class StockSelection:
    """A single stock selection with confidence and allocation."""
    symbol: str
    confidence: int  # 0-100
    allocation_weight: float  # 0.0-1.0
    reasoning: str = ""


@dataclass
class FundamentalResult:
    """The complete output of the fundamental analysis pipeline."""
    symbol: str
    gate_score: int  # 0-100: below threshold blocks technical signals
    sentiment: NewsSentimentResult | None = None
    screener: ScreenerResult | None = None
    macro: MacroResult | None = None
    selections: list[StockSelection] = field(default_factory=list)
    llm_summary: Any | None = None
    timestamp: datetime = field(default_factory=datetime.now)
