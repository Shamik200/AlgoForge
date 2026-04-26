# Phase 19: Fundamental Analysis Module - Context

**Gathered:** 2026-04-26
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Build an AI-powered fundamental analysis pipeline with modular agents: news sentiment scoring, financial metric screening, macro/sector analysis, and a stock selector that produces ranked watchlists with confidence scores. The output gates the technical analysis pipeline.
</domain>

<decisions>
## Implementation Decisions

### Agent Architecture
- **D-01:** Modular Agent Classes. Each agent (News, Screener, Macro, Selector) is a standalone Python class with a `run()` method. They share a common `AgentResult` output contract. In production, these would be orchestrated by LangGraph. For now, we implement the data models, scoring logic, and orchestrator shell with mock LLM calls for testability.

### Sentiment Scoring
- **D-02:** Numeric Sentiment Scale. News sentiment is scored on a [-1.0, +1.0] scale: -1.0 = extremely bearish, 0.0 = neutral, +1.0 = extremely bullish. Multiple sources are averaged with recency weighting.

### Fundamental Gating
- **D-03:** Sequential Pipeline Gate. The fundamental module produces a `gate_score` (0-100). If below a configurable threshold (e.g., 40), the technical pipeline is blocked from generating new entry signals for that instrument. This prevents taking technically valid but fundamentally broken trades.
</decisions>
