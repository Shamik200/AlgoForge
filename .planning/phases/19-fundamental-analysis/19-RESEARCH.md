# Phase 19: Fundamental Analysis Module - Research

## Context
AI-powered fundamental analysis pipeline with modular agents. In production, each agent would use LLM calls (FinBERT for sentiment, GPT for macro analysis). For the initial implementation, we build the scoring logic and pipeline orchestration with mock-friendly interfaces.

## Technical Findings

1. **News Sentiment Agent:**
   - Accepts pre-scored NewsItems (in production, FinBERT or LLM would score them).
   - Recency weighting: `weight = 1 / (1 + age_hours/24)`. Recent news matters more.
   - Classification: [-1.0, -0.6] = very_bearish, [-0.6, -0.2] = bearish, [-0.2, 0.2] = neutral, etc.

2. **Financial Screener Agent:**
   - 5 scoring dimensions, each 0-100:
     - Valuation (PE, PB) — lower = better
     - Profitability (ROE, Net Margin) — higher = better
     - Growth (Revenue YoY, Earnings YoY) — higher = better
     - Leverage (D/E, Current Ratio) — lower debt = better
     - Quality (FCF, Dividends)
   - Weighted composite: Profitability 25%, Quality 20%, Valuation 20%, Growth 20%, Leverage 15%.

3. **Macro Analyst Agent:**
   - Evaluates VIX, GDP growth, interest rates, inflation.
   - Classifies regime: risk_on (>65), neutral (35-65), risk_off (<35).

4. **Stock Selector Agent:**
   - Combines: Screener 50% + Sentiment 25% + Macro 25%.
   - Confidence 0-100. Allocation weight: <30 = 0%, 30-70 = linear, >70 = max.

5. **Gate Mechanism:**
   - gate_score = selector confidence. If < threshold (default 40), technical signals blocked.

## Implementation Path
- Create `src/algoforge/fundamental/models.py`.
- Create `src/algoforge/fundamental/agents.py`.
- Create `src/algoforge/fundamental/pipeline.py`.
- Create `tests/unit/test_fundamental.py`.
