from pydantic import BaseModel, Field

class FundamentalSummary(BaseModel):
    """Output for Fundamental Gate / Macro Analysis."""
    quality_score: float = Field(ge=0.0, le=100.0, description="Overall fundamental quality score 0-100")
    valuation_rating: str = Field(description="OVERVALUED, UNDERVALUED, or FAIR")
    catalysts: list[str] = Field(description="Upcoming catalysts or risks")
    fundamental_summary: str = Field(description="Short fundamental summary")
    recommendation: str = Field(description="PASS or BLOCK for downstream modules")


class TechnicalContextSummary(BaseModel):
    """Output for Technical/Regime Interpretation."""
    dominant_trend: str = Field(description="UP, DOWN, or CHOP")
    volatility_state: str = Field(description="EXPANDING, CONTRACTING, or STABLE")
    key_levels: list[float] = Field(description="Key support/resistance levels identified by LLM")
    regime_confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the current regime classification")
    technical_summary: str = Field(description="Summary of the technical landscape")


class SignalConfirmation(BaseModel):
    """Output for Signal Confirmation (from signal families)."""
    is_confirmed: bool = Field(description="True if the LLM confirms the algorithmic signal")
    conviction_score: float = Field(ge=0.0, le=1.0, description="Conviction score 0-1")
    supporting_factors: list[str] = Field(description="Reasons to take the trade")
    detracting_factors: list[str] = Field(description="Reasons to avoid the trade")


class RiskCommentary(BaseModel):
    """Output for Risk Review."""
    risk_level: str = Field(description="LOW, MEDIUM, HIGH, EXTREME")
    sizing_multiplier: float = Field(ge=0.0, le=1.0, description="Suggested position sizing multiplier (0.0 means veto)")
    risk_notes: str = Field(description="Notes on portfolio heat, correlations, or macro risks")


class TradeThesis(BaseModel):
    """Output for Trade Rationale Generation."""
    thesis_summary: str = Field(description="One paragraph explaining WHY the trade is being taken")
    expected_duration: str = Field(description="SCALP, INTRADAY, SWING, or POSITION")
    invalidation_level: float = Field(description="Price at which the thesis is completely wrong")


class PostTradeAnalysis(BaseModel):
    """Output for Post-Trade Review."""
    performance_rating: str = Field(description="EXCELLENT, GOOD, POOR, or TERRIBLE")
    lessons_learned: list[str] = Field(description="Key takeaways from this trade")
    rule_adherence: bool = Field(description="Did the system adhere strictly to its rules?")
    analysis_summary: str = Field(description="Review of the trade execution and exit")


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
