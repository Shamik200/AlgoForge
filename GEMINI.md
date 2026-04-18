# AlgoForge — GSD Workflow Guide

## Project Overview

AlgoForge is an institutional-grade algorithmic trading system with 3 modules (Fundamental → Technical → Execution), 31 strategies across 5 market regimes, and a risk management engine with absolute veto power.

## Planning Directory

All project planning artifacts are in `.planning/`:
- `PROJECT.md` — Project context and vision
- `REQUIREMENTS.md` — 118 v1 requirements with REQ-IDs
- `ROADMAP.md` — 15-phase roadmap
- `STATE.md` — Current progress tracker
- `config.json` — Workflow preferences
- `research/` — Stack, features, architecture, pitfalls research

## Architecture Conventions

- Event-driven architecture using internal event bus
- All strategies inherit from base `Strategy` class
- All configuration is YAML-driven, not hardcoded
- Pydantic models for all data structures
- Structured JSON logging (structlog)
- Type hints on all functions; docstrings on all public methods
- Python 3.11+ with async/await for I/O-bound operations

## Key Design Decisions

- Fundamental analysis MUST complete before technical analysis begins
- Market regime detection MUST run before any strategy is activated
- Every trade MUST have a stop loss — no exceptions
- Risk manager can veto any signal from any strategy
- Paper trading engine must model slippage, commissions, and latency
- ML models are optional enhancement layers, not replacements for rule-based strategies
- Primary strategy (trendline-pullback) generates >50% of all trades

## Code Style

- Python 3.11+ with async/await
- PEP 8 compliance; use `ruff` for linting + formatting
- `mypy` for static type checking
- `pytest` + `hypothesis` for testing
- No global mutable state; dependency injection via constructors
- Structured JSON logging via `structlog`
