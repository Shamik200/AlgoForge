# AlgoForge

Institutional-grade algorithmic trading system with 31 strategies across 5 market regimes.

## Quick Start

```bash
# Install core dependencies
pip install -e ".[test]"

# Configure (edit config/settings.yaml)
cp .env.example .env

# Run
python -m algoforge
```

## Architecture

```
Fundamental Analysis → Technical Analysis → Execution
     (AI Agents)        (31 Strategies)     (Paper/Live)
                              ↑
                    Risk Management (VETO)
```

## Project Structure

```
src/algoforge/
├── core/          # Config, models, events, logging
├── data/          # Feeds, storage, processors
├── technical/     # Indicators, patterns, regime detection
├── fundamental/   # AI agents for stock selection
├── risk/          # Position sizing, portfolio limits
├── execution/     # Paper trading, backtesting, live bridge
└── ml/            # XGBoost, LSTM, RL models
```