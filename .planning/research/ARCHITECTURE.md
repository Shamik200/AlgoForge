# Architecture Research

**Domain:** Algorithmic Trading System (HFT-level, multi-market)
**Researched:** 2026-04-18
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER (LangGraph)                   │
│         Coordinates sequential Module 1 → 2 → 3 pipeline           │
├──────────────┬──────────────────────┬───────────────────────────────┤
│  MODULE 1    │     MODULE 2         │       MODULE 3                │
│  FUNDAMENTAL │     TECHNICAL        │       EXECUTION               │
│  ANALYSIS    │     ANALYSIS         │                               │
│              │                      │                               │
│ ┌──────────┐ │ ┌────────────────┐   │ ┌───────────────────┐        │
│ │News Agent│ │ │Regime Detector │   │ │Paper Trading Sim  │        │
│ ├──────────┤ │ ├────────────────┤   │ ├───────────────────┤        │
│ │Financials│ │ │Structure Layer │   │ │Backtesting Engine │        │
│ │Screener  │ │ │(S/R+Trendlines)│  │ ├───────────────────┤        │
│ ├──────────┤ │ ├────────────────┤   │ │Order Manager      │        │
│ │Sector/   │ │ │Strategy Engine │   │ ├───────────────────┤        │
│ │Macro     │ │ │(31 strategies) │   │ │Broker Adapters    │        │
│ ├──────────┤ │ ├────────────────┤   │ │(Zerodha/Alpaca/   │        │
│ │Stock     │ │ │ML/DL/RL Models │   │ │ Binance/IBKR)     │        │
│ │Selector  │ │ ├────────────────┤   │ └───────────────────┘        │
│ └──────────┘ │ │Signal Generator│   │                               │
│              │ └────────────────┘   │                               │
├──────────────┴──────────────────────┴───────────────────────────────┤
│              RISK MANAGEMENT ENGINE (absolute veto power)            │
│  Per-Trade Controls │ Portfolio Controls │ Circuit Breaker │ Kill SW │
├─────────────────────────────────────────────────────────────────────┤
│              EVENT BUS (Redis Streams / internal async queues)        │
├─────────────────────────────────────────────────────────────────────┤
│              DATA INFRASTRUCTURE                                     │
│  Market Feeds │ TimescaleDB │ Redis Cache │ Feature Store            │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Orchestration Engine | Coordinates Module 1→2→3 sequential pipeline; manages lifecycle | Async Python with state machine; LangGraph for fundamental agents |
| Data Feed Manager | Connects to market data sources; normalizes OHLCV; handles reconnection | WebSocket clients with async reconnect logic; adapter per market |
| Indicator Engine | Computes all 14 technical indicators on configurable timeframes | TA-Lib + pandas-ta; cached computation to avoid recalculation |
| Structure Detector | Finds S/R levels (higher TF) and constructs trendlines (mid TF) | Custom algorithms using swing detection + linear regression |
| Regime Detector | Classifies market condition per instrument | ADX/Bollinger/Volume rules → 5-class probabilities |
| Strategy Engine | Applies strategy logic based on regime; generates raw signals | Base Strategy class; each strategy inherits and implements signal() |
| Signal Aggregator | Filters, ranks, and deduplicates signals from multiple strategies | Priority queue; conflict resolution; primary strategy weighting |
| Risk Manager | Validates every signal against per-trade and portfolio rules | Stateless check functions; has absolute veto power |
| Position Sizer | Calculates lot size based on risk parameters and confidence | Fixed-fraction, Kelly Criterion, RL-based sizing |
| Order Manager | Converts signals to orders; tracks order lifecycle | State machine: PENDING→SUBMITTED→FILLED/CANCELLED |
| Paper Trader | Simulates realistic execution with slippage/commission/latency | Synthetic order book; configurable slippage model |
| Backtester | Replays historical data through strategy engine | Event-driven; same code path as live trading |
| ML Pipeline | Trains, evaluates, and serves prediction models | Walk-forward training; feature store; MLflow tracking |
| Fundamental Agents | AI-powered analysis of news, financials, sectors, scoring | LangChain agents orchestrated by LangGraph DAG |
| Dashboard | Real-time monitoring and control interface | Next.js with WebSocket; read-only view of system state |

## Recommended Project Structure

```
trading-system/
├── config/
│   ├── settings.yaml               # Global settings (logging, database, API keys)
│   ├── strategies.yaml              # All strategy parameters (tunable per market)
│   ├── risk_management.yaml         # Risk limits, position sizing rules
│   └── markets/
│       ├── stocks_india.yaml        # NSE/BSE specific: hours, fees, instruments
│       ├── stocks_us.yaml           # NYSE/NASDAQ: PDT rules, hours, fees
│       ├── crypto.yaml              # 24/7, USDT base, exchange-specific
│       └── forex.yaml               # Session-based, pip calculations, leverage
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── engine.py                # Main orchestration engine (Module 1→2→3)
│   │   ├── event_bus.py             # Internal event system (signals, orders, fills)
│   │   ├── models.py                # Pydantic models (Signal, Order, Position, etc.)
│   │   ├── config.py                # YAML config loader with validation
│   │   └── constants.py             # Enums, market hours, timeframe mappings
│   ├── data/
│   │   ├── feeds/
│   │   │   ├── base.py              # Abstract DataFeed interface
│   │   │   ├── yahoo.py             # Yahoo Finance adapter
│   │   │   ├── binance.py           # Binance WebSocket adapter
│   │   │   └── ccxt_feed.py         # CCXT unified adapter (multi-exchange)
│   │   ├── storage/
│   │   │   ├── timescale.py         # TimescaleDB adapter for OHLCV
│   │   │   └── redis_cache.py       # Redis for real-time cache
│   │   └── processors/
│   │       ├── normalizer.py        # Raw data → standardized OHLCV
│   │       └── resampler.py         # 1min → 5min/15min/1H/1D aggregation
│   ├── technical/
│   │   ├── indicators/
│   │   │   ├── base.py              # Abstract Indicator interface
│   │   │   ├── trend.py             # EMA, SMA, Supertrend, Ichimoku
│   │   │   ├── momentum.py          # RSI, MACD, Stochastic, ADX
│   │   │   ├── volatility.py        # ATR, Bollinger, Keltner, Donchian
│   │   │   └── volume.py            # VWAP, OBV, Volume Profile
│   │   ├── structures/
│   │   │   ├── support_resistance.py # Multi-timeframe S/R detection
│   │   │   └── trendlines.py        # Algorithmic trendline construction
│   │   ├── patterns/
│   │   │   └── candlestick.py       # All candlestick pattern recognition
│   │   ├── regime/
│   │   │   └── detector.py          # 5-class market regime classifier
│   │   ├── strategies/
│   │   │   ├── base.py              # Abstract Strategy interface
│   │   │   ├── primary/
│   │   │   │   └── trendline_pullback.py  # User's primary strategy
│   │   │   ├── trending/            # 8 trending strategies
│   │   │   ├── range/               # 7 range/sideways strategies
│   │   │   ├── breakout/            # 7 breakout strategies
│   │   │   ├── reversal/            # 5 reversal strategies
│   │   │   └── liquidity/           # 4 liquidity/trap strategies
│   │   └── signals/
│   │       ├── generator.py         # Signal generation from strategies
│   │       └── aggregator.py        # Multi-signal filtering & ranking
│   ├── fundamental/
│   │   ├── agents/
│   │   │   ├── news_sentiment.py    # Agent 1: News + NLP sentiment
│   │   │   ├── financial_screener.py # Agent 2: Balance sheet analysis
│   │   │   ├── sector_macro.py      # Agent 3: Sector rotation + macro
│   │   │   └── stock_selector.py    # Agent 4: Scoring + watchlist
│   │   ├── graph.py                 # LangGraph DAG workflow
│   │   └── prompts/                 # LLM prompt templates
│   ├── ml/
│   │   ├── features/
│   │   │   └── engineering.py       # Feature computation from indicators
│   │   ├── models/
│   │   │   ├── classifier.py        # XGBoost/LightGBM direction predictor
│   │   │   ├── forecaster.py        # LSTM/Transformer price forecaster
│   │   │   └── position_sizer_rl.py # PPO/SAC RL position sizing
│   │   ├── training/
│   │   │   └── pipeline.py          # Walk-forward training orchestration
│   │   └── inference/
│   │       └── predictor.py         # Real-time model prediction
│   ├── risk/
│   │   ├── manager.py               # Per-trade risk validation
│   │   ├── portfolio.py             # Portfolio-level controls (VaR, correlation)
│   │   ├── position_sizer.py        # Fixed-fraction, Kelly, RL-based sizing
│   │   └── circuit_breaker.py       # Kill switch, drawdown halt, flash crash
│   ├── execution/
│   │   ├── paper_trader.py          # Paper trading with realistic simulation
│   │   ├── backtester.py            # Event-driven historical replay
│   │   ├── order_manager.py         # Order lifecycle management
│   │   └── brokers/
│   │       ├── base.py              # Abstract Broker interface
│   │       ├── zerodha.py           # Zerodha Kite adapter (placeholder)
│   │       ├── alpaca.py            # Alpaca adapter (placeholder)
│   │       └── binance.py           # Binance adapter (placeholder)
│   └── dashboard/
│       ├── api/                     # FastAPI backend for dashboard
│       └── frontend/               # Next.js application
├── tests/
│   ├── unit/                        # Per-module unit tests
│   ├── integration/                 # Cross-module integration tests
│   └── backtest_validation/         # Strategy validation tests
├── notebooks/                       # Research & analysis
├── data/                           # Historical data cache
├── models/                         # Trained ML artifacts
├── logs/                           # Structured JSON logs
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml                   # Project metadata + dependencies
└── README.md
```

### Structure Rationale

- **config/:** Separation of all tunable parameters from code; YAML for human readability; market-specific configs prevent conditional logic in code
- **src/core/:** Shared infrastructure (event bus, models, config) used by all modules
- **src/technical/:** Largest module; deeply nested because it contains 31 strategies, 14 indicators, pattern recognition, and structure detection
- **src/fundamental/:** Isolated module; can be developed/tested independently; LangGraph workflow owns the orchestration
- **src/ml/:** Separate from strategies; ML models are enhancement layers, not core logic
- **src/risk/:** Critical path; kept separate so every other module must go through it
- **src/execution/:** Unified execution path; paper and live trading share the same interface
- **tests/:** Mirrors src/ structure; backtest_validation/ for strategy-level validation

## Architectural Patterns

### Pattern 1: Event-Driven Architecture

**What:** All inter-component communication happens via events on an internal event bus. Components publish events (MarketData, Signal, Order, Fill) and subscribe to events they care about.

**When to use:** Always — this is the core architectural pattern.

**Trade-offs:**
- (+) Loose coupling; components can be replaced/tested independently
- (+) Same code path for live and backtest (just different event sources)
- (+) Easy to add new components without modifying existing ones
- (−) Debugging event flows is harder than direct function calls
- (−) Event ordering must be carefully managed

**Example:**
```python
# Event types
@dataclass
class MarketDataEvent:
    symbol: str
    timeframe: str
    candle: OHLCV
    timestamp: datetime

@dataclass  
class SignalEvent:
    symbol: str
    direction: Direction  # LONG / SHORT
    strategy: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float

# Components subscribe to events
class StrategyEngine:
    def __init__(self, event_bus: EventBus):
        event_bus.subscribe(MarketDataEvent, self.on_market_data)
    
    async def on_market_data(self, event: MarketDataEvent):
        signal = self.evaluate(event)
        if signal:
            await self.event_bus.publish(signal)
```

### Pattern 2: Strategy Pattern (GoF)

**What:** All 31 strategies inherit from a base `Strategy` class with a standard interface. The strategy engine iterates over active strategies based on detected market regime.

**When to use:** For all strategy implementations.

**Trade-offs:**
- (+) New strategies added without modifying existing code
- (+) Strategies testable in isolation
- (+) Regime detector activates/deactivates strategies dynamically
- (−) Shared base class can become bloated

**Example:**
```python
class Strategy(ABC):
    @abstractmethod
    def should_activate(self, regime: MarketRegime) -> bool: ...
    
    @abstractmethod
    def generate_signal(self, data: MultiTimeframeData) -> Optional[Signal]: ...
    
    @property
    @abstractmethod
    def name(self) -> str: ...

class TrendlinePullback(Strategy):
    def should_activate(self, regime: MarketRegime) -> bool:
        return regime in (MarketRegime.TRENDING,)
    
    def generate_signal(self, data: MultiTimeframeData) -> Optional[Signal]:
        # User's 4-step logic: Structure → Trendlines → Indicators → Confirmation
        ...
```

### Pattern 3: Adapter Pattern for Market/Broker Abstraction

**What:** Abstract interfaces for data feeds and broker connections. Each market/broker has a concrete adapter.

**When to use:** For all external integrations (data feeds, broker APIs).

**Trade-offs:**
- (+) Switch markets/brokers via configuration, not code changes
- (+) Paper trading is just another "broker" adapter
- (−) Some broker-specific features may not fit cleanly into the abstract interface

## Data Flow

### Request Flow (Signal Pipeline)

```
[Market Data Feed] → WebSocket/REST
    ↓
[Data Normalizer] → Standardized OHLCV candles
    ↓
[Multi-Timeframe Resampler] → 1min, 5min, 15min, 1H, 1D candles
    ↓
[Indicator Engine] → EMA, RSI, ADX, ATR, MACD, Bollinger, etc.
    ↓
[Structure Detector] → S/R levels (higher TF) + Trendlines (mid TF)
    ↓
[Market Regime Detector] → Trending / Range / Breakout / Reversal / Trap
    ↓
[Strategy Engine] → Raw signals from active strategies (based on regime)
    ↓
[Signal Aggregator] → Filtered, ranked, deduplicated signals
    ↓
[Risk Manager] → APPROVED / VETOED (per-trade + portfolio checks)
    ↓
[Position Sizer] → Lot size calculated from risk rules + confidence
    ↓
[Order Manager] → Order created → submitted to broker/paper
    ↓
[Execution Engine] → Filled / Partially Filled / Rejected
    ↓
[Post-Trade Analytics] → Update P&L, drawdown, strategy stats
```

### Fundamental Analysis Pipeline (runs first)

```
[Scheduler: Every N hours or on-demand]
    ↓
[Agent 1: News/Sentiment] ──┐
[Agent 2: Financials]       ├──→ [Agent 4: Stock Selector]
[Agent 3: Sector/Macro]  ──┘         ↓
                              [Watchlist + Confidence Scores]
                                     ↓
                              [Technical Analysis Pipeline] (above)
```

### Key Data Flows

1. **Market data → Signal:** Real-time candle data processed through indicators, structure, regime, strategy, signal pipeline (milliseconds)
2. **Fundamental → Watchlist:** Periodic fundamental screening produces rated watchlist (minutes to hours)
3. **Signal → Execution:** Approved signal converted to order and executed (< 50ms target)
4. **Fill → Analytics:** Trade results update portfolio state, strategy stats, risk metrics (immediate)

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------| 
| 1-50 instruments | Single Python process; all components in-process; no message queue needed |
| 50-500 instruments | Separate data feed process; Redis for inter-process communication; multiple strategy workers |
| 500-2000 instruments | Kubernetes deployment; separate pods per module; TimescaleDB with read replicas |
| 2000+ instruments | Horizontal strategy sharding; dedicated ML inference service; market-specific pipelines |

### Scaling Priorities

1. **First bottleneck:** Indicator computation on 1-min candles across many instruments → Solution: Polars for batch computation; cache computed indicators
2. **Second bottleneck:** Strategy evaluation across 31 strategies per instrument → Solution: Only evaluate strategies matching detected regime (5x reduction)

## Anti-Patterns

### Anti-Pattern 1: Shared Mutable State

**What people do:** Global dictionaries for positions, portfolio state, indicator caches
**Why it's wrong:** Race conditions in async code; impossible to test; hard to track state changes
**Do this instead:** Immutable data objects (Pydantic models); state changes through events; explicit state passing

### Anti-Pattern 2: Vectorized Backtesting

**What people do:** Use numpy vectorization to compute signals over entire history at once
**Why it's wrong:** Introduces lookahead bias; signals see future data; unrealistic execution
**Do this instead:** Event-driven backtesting that processes one candle at a time, same as live

### Anti-Pattern 3: Strategy-Specific Risk Management

**What people do:** Each strategy manages its own risk (SL/TP/sizing inside strategy logic)
**Why it's wrong:** Portfolio-level risk ignored; strategies can't coordinate; risk rules inconsistent
**Do this instead:** Centralized risk manager that validates ALL signals regardless of source

### Anti-Pattern 4: Hardcoded Market Logic

**What people do:** If-else branches for different markets throughout the codebase
**Why it's wrong:** Adding a new market requires touching every file; error-prone
**Do this instead:** Market-specific YAML configs loaded at startup; adapter pattern for APIs

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Market data APIs | WebSocket + REST fallback | Handle rate limits; reconnect on disconnect; heartbeat monitoring |
| Broker APIs | Adapter pattern with retry | Idempotent order submissions; handle partial fills |
| LLM APIs (Claude/GPT) | LangChain with retry + fallback | Token rate limits; fallback between providers; cache responses |
| News APIs | Polling + webhook | RSS feeds + Twitter API; deduplication required |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Fundamental → Technical | Watchlist file/cache | Fundamental runs periodically; Technical reads latest watchlist |
| Technical → Execution | Event bus (Signal events) | Real-time; every signal goes through risk manager first |
| Execution → Dashboard | WebSocket + REST API | Dashboard is read-only; FastAPI backend exposes state |
| Strategy → Risk | Synchronous function call | Risk manager MUST be on critical path; no async bypass |

## Sources

- Event-driven backtesting architecture: QuantConnect Lean Engine
- Strategy pattern for trading: Design Patterns for Trading Systems (academic)
- Institutional trading architecture: Two Sigma, Citadel public tech talks
- Python async patterns: Python 3.11+ asyncio best practices

---
*Architecture research for: Algorithmic Trading System*
*Researched: 2026-04-18*
