# Stack Research

**Domain:** Algorithmic Trading System (HFT-level, multi-market)
**Researched:** 2026-04-18
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Core language (strategy, ML, research) | Industry standard for quant research; rich ecosystem (pandas, numpy, ML libs); async/await for concurrent I/O |
| asyncio + aiohttp | stdlib + 3.9+ | Async framework | Non-blocking I/O for concurrent data feeds, WebSocket connections, API calls across 1000+ instruments |
| Polars | 1.x | High-performance DataFrames | Written in Rust, 10-50x faster than pandas for large-scale data manipulation; critical for backtesting speed |
| pandas | 2.2+ | Data manipulation (compatibility) | Required for TA-Lib/pandas-ta compatibility; use Polars for heavy lifting, pandas for indicator computation |
| NumPy | 1.26+ | Numerical computation | Foundation for all numerical operations; vectorized math for indicator calculations |
| Next.js | 14+ | Dashboard / monitoring UI | Server-side rendering, React ecosystem, WebSocket support, production-grade; fastest premium-looking UI |
| TypeScript | 5.x | Dashboard language | Type safety for complex trading dashboard; prevents runtime errors in critical monitoring UI |
| Docker | 24+ | Containerization & deployment | Reproducible environments; isolated services; easy deployment across dev/prod |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| TA-Lib | 0.4.28+ | Technical indicators (C-based) | All 14 indicator calculations — fastest available; C bindings for speed |
| pandas-ta | 0.3.14b+ | Additional indicators | Indicators not in TA-Lib (Supertrend, custom); pure Python fallback |
| scikit-learn | 1.4+ | ML preprocessing & models | Feature scaling, train/test split, baseline models, pipeline infrastructure |
| XGBoost | 2.0+ | Gradient boosting classification | Primary ML model for trade direction prediction; best tabular data classifier |
| LightGBM | 4.3+ | Fast gradient boosting | Alternative to XGBoost for speed; feature importance ranking |
| PyTorch | 2.2+ | Deep learning (LSTM, Transformer) | Price forecasting, temporal pattern recognition; GPU-accelerated training |
| Stable-Baselines3 | 2.3+ | Reinforcement learning | PPO/SAC for position sizing and execution timing optimization |
| LangChain | 0.2+ | LLM orchestration | Fundamental analysis agents — news processing, financial analysis, chain-of-thought |
| LangGraph | 0.1+ | Multi-agent workflows | Orchestrating 4 fundamental analysis agents in DAG workflow |
| Pydantic | 2.6+ | Data validation & models | All data structures — signals, orders, positions, configs; runtime type safety |
| structlog | 24.1+ | Structured JSON logging | All application logging; machine-parseable for monitoring and debugging |
| httpx | 0.27+ | Async HTTP client | API calls to broker/data providers; better async support than requests |
| websockets | 12+ | WebSocket client | Real-time market data feed connections |
| SQLAlchemy | 2.0+ | ORM & database toolkit | PostgreSQL/TimescaleDB interaction; async support |
| Redis (redis-py) | 5.0+ | Cache & pub/sub | Real-time signal distribution, session cache, rate limiting |
| Optuna | 3.6+ | Hyperparameter tuning | ML model optimization; Bayesian search for strategy parameters |
| SHAP | 0.45+ | Model explainability | Feature importance analysis for ML models; debugging predictions |
| MLflow | 2.11+ | ML experiment tracking | Model versioning, performance comparison, artifact storage |
| pytest | 8.0+ | Testing framework | Unit, integration, and backtest validation tests |
| hypothesis | 6.98+ | Property-based testing | Fuzzing strategy logic with random inputs; edge case discovery |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Linting + formatting | Replaces flake8 + black + isort; extremely fast (Rust-based) |
| mypy | Static type checking | Enforce type hints across codebase; catch type errors before runtime |
| pre-commit | Git hooks | Run ruff + mypy before every commit |
| Docker Compose | Multi-service orchestration | Database, Redis, dashboard, trading engine as separate containers |

### Database Layer

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PostgreSQL | 16+ | Primary relational database | Trade logs, positions, portfolio state, fundamental data |
| TimescaleDB | 2.14+ | Time-series extension | OHLCV candle storage, tick data; hypertable compression for 1-min data |
| Redis | 7+ | Cache & message broker | Real-time signal pub/sub, session state, rate limiting |

## Installation

```bash
# Core
pip install python-dotenv pydantic pydantic-settings structlog httpx websockets

# Data & Indicators
pip install pandas polars numpy ta-lib pandas-ta

# ML/DL/RL
pip install scikit-learn xgboost lightgbm torch stable-baselines3 optuna shap mlflow

# Agentic AI
pip install langchain langchain-community langgraph langsmith

# Database
pip install sqlalchemy asyncpg redis psycopg2-binary

# Testing
pip install pytest hypothesis pytest-asyncio pytest-cov

# Dev tools
pip install ruff mypy pre-commit
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Python | C++/Rust | If sub-microsecond latency needed (true HFT with co-location); overkill for API-based retail |
| Polars | DuckDB | If SQL-like queries preferred over DataFrame API; analytical queries on parquet files |
| TimescaleDB | InfluxDB | If write-heavy workload with simple queries; TimescaleDB better for complex joins |
| TimescaleDB | kdb+/q | Hedge fund standard; extremely expensive licensing; overkill for retail |
| Next.js | Streamlit | If rapid prototyping needed and UI quality doesn't matter; Streamlit is 10x slower for real-time |
| PyTorch | TensorFlow | If deploying to edge/mobile; PyTorch has better research ecosystem for trading |
| Redis | RabbitMQ | If guaranteed message delivery critical; Redis Streams sufficient for internal pub/sub |
| XGBoost | CatBoost | If heavy categorical features; XGBoost generally better for numerical trading features |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Vectorized backtesting (vectorbt) | Causes lookahead bias; unrealistic fill simulation | Event-driven backtesting engine |
| Global mutable state / singletons | Race conditions in concurrent trading; untestable | Dependency injection via constructors |
| requests (sync HTTP) | Blocks event loop; can't handle concurrent feeds | httpx (async) or aiohttp |
| SQLite for tick data | Performance collapses at scale (millions of rows) | TimescaleDB with hypertables |
| Jupyter notebooks for production code | No version control, no testing, no type checking | .py files with proper structure |
| TA-Lib alone | Missing modern indicators (Supertrend, Squeeze) | TA-Lib + pandas-ta combination |
| Hardcoded parameters | Can't tune or adapt to different markets | YAML config files loaded at startup |

## Stack Patterns by Variant

**If targeting Indian markets (NSE/BSE):**
- Use Zerodha Kite Connect API for execution
- STT/GST tax modeling in commission calculator
- Market hours: 9:15 AM - 3:30 PM IST
- Currency: INR; paper trading capital: ₹1,00,00,000

**If targeting Crypto:**
- Use CCXT library for unified exchange API across Binance/Bybit/etc.
- 24/7 market hours — no session-based logic
- Currency: USDT; paper trading capital: $100,000
- Higher volatility — adjust ATR multipliers

**If targeting US Stocks:**
- Use Alpaca or IBKR API
- Market hours: 9:30 AM - 4:00 PM ET with pre/post market
- Currency: USD; paper trading capital: $100,000
- PDT rule awareness (min $25K for day trading)

**If targeting Forex:**
- Use OANDA or MetaTrader API
- Nearly 24/5 market; session-based logic (Asian/London/NY)
- Currency: USD; leverage considerations
- Pip-based calculations instead of percentage

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| TA-Lib 0.4.28 | Python 3.11-3.12 | Requires C library pre-installed; use conda for Windows |
| PyTorch 2.2+ | CUDA 11.8/12.1 | GPU training for LSTM/Transformer models |
| LangChain 0.2+ | LangGraph 0.1+ | Must use together; LangGraph requires LangChain core |
| TimescaleDB 2.14 | PostgreSQL 16 | Install as PostgreSQL extension |
| Polars 1.x | pandas 2.2+ | Interop via .to_pandas() / .from_pandas() |

## Sources

- Industry research on institutional trading infrastructure (2025)
- Official documentation: PyTorch, LangChain, TimescaleDB, XGBoost
- Community consensus: Reddit r/algotrading, QuantConnect forums

---
*Stack research for: Algorithmic Trading System*
*Researched: 2026-04-18*
