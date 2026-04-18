---
phase: 1
plan: 1
title: "Project Scaffolding & Configuration System"
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - src/algoforge/__init__.py
  - src/algoforge/__main__.py
  - src/algoforge/core/__init__.py
  - src/algoforge/core/config.py
  - src/algoforge/core/constants.py
  - config/settings.yaml
  - .env.example
  - .gitignore
  - README.md
  - tests/__init__.py
  - tests/unit/__init__.py
  - tests/unit/test_config.py
requirements: [CONF-01, CONF-02, CONF-03, CONF-04, CONF-05]
autonomous: true
---

# Plan 01: Project Scaffolding & Configuration System

<objective>
Set up the complete Python project structure with pyproject.toml, src layout, and the YAML-based configuration system using pydantic-settings. This plan establishes the foundation directory structure and the config loading mechanism that ALL subsequent code depends on.
</objective>

<task id="01-01">
## Task 1: Create project structure and pyproject.toml

<read_first>
- GEMINI.md (architecture conventions, code style requirements)
- .planning/phases/01-foundation-data/01-CONTEXT.md (implementation decisions)
- .planning/research/STACK.md (technology versions)
</read_first>

<action>
Create the full directory structure:

```
trading-system/
├── config/
│   └── settings.yaml
├── src/
│   └── algoforge/
│       ├── __init__.py          # version = "0.1.0"
│       ├── __main__.py          # entry point: python -m algoforge
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   └── constants.py
│       ├── data/
│       │   ├── __init__.py
│       │   ├── feeds/
│       │   │   ├── __init__.py
│       │   │   └── base.py
│       │   ├── storage/
│       │   │   └── __init__.py
│       │   └── processors/
│       │       └── __init__.py
│       ├── technical/
│       │   └── __init__.py
│       ├── fundamental/
│       │   └── __init__.py
│       ├── risk/
│       │   └── __init__.py
│       ├── execution/
│       │   └── __init__.py
│       └── ml/
│           └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   └── __init__.py
│   └── integration/
│       └── __init__.py
├── .env.example
├── .gitignore
└── pyproject.toml
```

pyproject.toml must include:
- build-system: hatchling
- project name: algoforge
- python-requires: >=3.11
- Core dependencies: pydantic>=2.6, pydantic-settings>=2.2, structlog>=24.1, redis>=5.0, httpx>=0.27, yfinance>=0.2.36, pandas>=2.2, polars>=1.0, numpy>=1.26, python-dotenv>=1.0, pyyaml>=6.0
- Optional dependency groups: [ml] for torch, xgboost, etc.; [dev] for ruff, mypy, pre-commit; [test] for pytest, hypothesis, pytest-asyncio, pytest-cov

.gitignore must include: __pycache__, .env, *.pyc, .mypy_cache, .ruff_cache, data/, models/, logs/, .planning/phases/*/scratch/

__main__.py: `from algoforge.core.config import get_settings; print(f"AlgoForge v{settings.version} loaded")`
</action>

<acceptance_criteria>
- pyproject.toml contains `name = "algoforge"` and `requires-python = ">=3.11"`
- pyproject.toml contains `pydantic-settings` in dependencies
- src/algoforge/__init__.py contains `__version__ = "0.1.0"`
- Directory structure has: src/algoforge/core/, src/algoforge/data/feeds/, src/algoforge/data/storage/, src/algoforge/data/processors/
- .gitignore contains `.env` and `__pycache__`
- .env.example contains `ALGOFORGE_REDIS_HOST=localhost`
</acceptance_criteria>
</task>

<task id="01-02">
## Task 2: Create constants and enums

<read_first>
- .planning/REQUIREMENTS.md §CONF-01 to CONF-05
- .planning/phases/01-foundation-data/01-CONTEXT.md §D-13 (market-specific settings)
</read_first>

<action>
Create `src/algoforge/core/constants.py` with:

```python
from enum import Enum

class Market(str, Enum):
    STOCKS_INDIA = "stocks_india"
    STOCKS_US = "stocks_us"
    CRYPTO = "crypto"
    FOREX = "forex"

class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1wk"
    MO1 = "1mo"

class TimeframeMode(str, Enum):
    INTRADAY = "intraday"      # 1min exec, 15min-1h hold
    SWING = "swing"            # 1H/4H exec, 1week-1month hold

class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"

class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGE = "range"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    LIQUIDITY_TRAP = "liquidity_trap"

# Market hours (UTC offsets and trading windows)
MARKET_HOURS = {
    Market.STOCKS_INDIA: {"open": "03:45", "close": "10:00", "tz": "Asia/Kolkata"},
    Market.STOCKS_US: {"open": "14:30", "close": "21:00", "tz": "America/New_York"},
    Market.CRYPTO: {"open": "00:00", "close": "23:59", "tz": "UTC"},
    Market.FOREX: {"open": "00:00", "close": "23:59", "tz": "UTC"},
}

# Default timeframe mappings per mode
TIMEFRAME_CONFIG = {
    TimeframeMode.INTRADAY: {
        "sr_timeframes": [Timeframe.D1, Timeframe.H1],
        "trendline_timeframes": [Timeframe.M15, Timeframe.M5],
        "execution_timeframe": Timeframe.M1,
    },
    TimeframeMode.SWING: {
        "sr_timeframes": [Timeframe.MO1, Timeframe.W1],
        "trendline_timeframes": [Timeframe.W1, Timeframe.D1],
        "execution_timeframe": Timeframe.H1,
    },
}
```
</action>

<acceptance_criteria>
- constants.py contains `class Market(str, Enum)` with 4 markets
- constants.py contains `class Timeframe(str, Enum)` with all timeframe values
- constants.py contains `class TimeframeMode(str, Enum)` with INTRADAY and SWING
- constants.py contains `class MarketRegime(str, Enum)` with 5 regimes
- constants.py contains `MARKET_HOURS` dict with keys for all 4 markets
- constants.py contains `TIMEFRAME_CONFIG` dict with keys for both modes
</acceptance_criteria>
</task>

<task id="01-03">
## Task 3: Create configuration system with Pydantic Settings

<read_first>
- src/algoforge/core/constants.py (enums defined in Task 2)
- .planning/phases/01-foundation-data/01-CONTEXT.md §D-10 to D-13
- .planning/phases/01-foundation-data/01-RESEARCH.md §3 (Pydantic Settings patterns)
</read_first>

<action>
Create `src/algoforge/core/config.py`:

Use `pydantic_settings.BaseSettings` with `YamlConfigSettingsSource`:
- Priority: env vars (ALGOFORGE_ prefix) > .env > YAML > defaults
- Nested models: RedisConfig, DataFeedConfig, MarketConfig, LoggingConfig, RiskConfig (stub), StrategyConfig (stub)
- Singleton pattern via `functools.lru_cache` for `get_settings()`
- All fields have sensible defaults so system starts with minimal config

Key config sections:
```python
class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None

class DataFeedConfig(BaseModel):
    provider: str = "yfinance"
    symbols: list[str] = ["AAPL", "MSFT", "GOOGL"]
    base_timeframe: Timeframe = Timeframe.M1
    history_period: str = "1mo"

class MarketConfig(BaseModel):
    selected_market: Market = Market.STOCKS_US
    timeframe_mode: TimeframeMode = TimeframeMode.INTRADAY
    paper_trading_capital: float = 100000.0
    currency: str = "USD"

class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"
    log_file: str | None = "logs/algoforge.log"

class Settings(BaseSettings):
    version: str = "0.1.0"
    market: MarketConfig = MarketConfig()
    redis: RedisConfig = RedisConfig()
    data_feed: DataFeedConfig = DataFeedConfig()
    logging: LoggingConfig = LoggingConfig()
    
    model_config = SettingsConfigDict(
        yaml_file="config/settings.yaml",
        env_prefix="ALGOFORGE_",
        env_nested_delimiter="__",
        extra="ignore",
    )
```

Create `config/settings.yaml` with documented defaults for all sections including:
- market selection (stocks_india, stocks_us, crypto, forex)
- redis connection
- data feed symbols and timeframes
- logging level
- paper trading capital with currency
</action>

<acceptance_criteria>
- config.py contains `class Settings(BaseSettings)` with `YamlConfigSettingsSource`
- config.py contains `get_settings()` function returning Settings instance
- config.py imports from `pydantic_settings`
- config/settings.yaml contains `market:` section with `selected_market:` key
- config/settings.yaml contains `redis:` section with `host:` and `port:` keys
- config/settings.yaml contains `data_feed:` section with `symbols:` list
- Running `python -c "from algoforge.core.config import get_settings; s = get_settings(); print(s.market.selected_market)"` prints a Market enum value
</acceptance_criteria>
</task>

<task id="01-04">
## Task 4: Create unit tests for configuration system

<read_first>
- src/algoforge/core/config.py (config system from Task 3)
- src/algoforge/core/constants.py (enums from Task 2)
</read_first>

<action>
Create `tests/unit/test_config.py`:

Test cases:
1. `test_default_settings_load` — Settings() creates with defaults, all fields valid
2. `test_yaml_loading` — Load from config/settings.yaml, verify market selection
3. `test_env_override` — Set ALGOFORGE_MARKET__SELECTED_MARKET=crypto, verify override
4. `test_invalid_market_rejected` — Invalid market value raises ValidationError
5. `test_invalid_timeframe_rejected` — Invalid timeframe value raises ValidationError
6. `test_redis_config_defaults` — Redis host=localhost, port=6379
7. `test_data_feed_symbols_list` — Symbols is a list with at least one element
8. `test_paper_trading_capital_positive` — Capital must be > 0

Use pytest fixtures for env var cleanup.
</action>

<acceptance_criteria>
- tests/unit/test_config.py contains at least 6 test functions starting with `test_`
- tests/unit/test_config.py imports `Settings` from `algoforge.core.config`
- tests/unit/test_config.py tests env var override with `ALGOFORGE_` prefix
- Running `pytest tests/unit/test_config.py` exits 0 (all tests pass)
</acceptance_criteria>
</task>

<verification>
## Verification Criteria

### must_haves
- [ ] pyproject.toml exists with correct Python version and dependencies
- [ ] Directory structure matches architecture from ARCHITECTURE.md
- [ ] Settings load from YAML with Pydantic validation
- [ ] Market selection works via YAML config (4 markets)
- [ ] Timeframe mode selection works (intraday/swing)
- [ ] Environment variable overrides work
- [ ] All unit tests pass
</verification>
