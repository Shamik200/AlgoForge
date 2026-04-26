---
gap_closure: false
---

# Plan 19-01: Fundamental Analysis Module

## Objective
Build the 4-agent fundamental analysis pipeline with news sentiment, financial screening, macro analysis, and stock selection with a gate score mechanism.

## Tasks

- [x] **1. Data Models**
  - Create `src/algoforge/fundamental/models.py`.
  - Define NewsItem, FinancialMetrics, MacroEnvironment, and result dataclasses.

- [x] **2. Agents**
  - Create `src/algoforge/fundamental/agents.py`.
  - Implement NewsSentimentAgent, FinancialScreenerAgent, MacroAnalystAgent, StockSelectorAgent.

- [x] **3. Pipeline Orchestrator**
  - Create `src/algoforge/fundamental/pipeline.py`.
  - Implement FundamentalPipeline.analyze() and .should_allow_trading().

- [x] **4. Integration & Testing**
  - Create `src/algoforge/fundamental/__init__.py`.
  - Create `tests/unit/test_fundamental.py`.
  - Test all agents individually and the full pipeline pass/block scenarios.
