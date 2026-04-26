# Phase 22: Live Trading Bridge & Production - Research

## Context
Bridge between the AlgoForge engine and real broker APIs. Must support gradual capital deployment and full observability.

## Technical Findings

1. **BrokerAdapter ABC:**
   - `connect() -> bool` — Establish connection to broker API.
   - `submit_order(symbol, side, quantity, order_type, price) -> OrderResult`
   - `cancel_order(order_id) -> bool`
   - `get_positions() -> list[Position]`
   - `get_account() -> AccountInfo`

2. **Alpaca Adapter (Placeholder):**
   - REST API at `https://paper-api.alpaca.markets` for paper, `https://api.alpaca.markets` for live.
   - WebSocket for streaming market data.
   - The placeholder implements the interface but returns mock responses.

3. **Deployment Config:**
   - `capital_pct`: Starting allocation (e.g., 0.10 = 10%).
   - `scaling_thresholds`: List of (pnl_pct, new_capital_pct) tuples. E.g., after +5% P&L, scale to 25%.
   - `parallel_mode`: If True, paper and live engines run simultaneously for comparison.

4. **Prometheus Metrics:**
   - Use `prometheus_client` library.
   - Histogram for latencies, Gauge for positions/P&L, Counter for trades.
   - Endpoint at `:9090/metrics`.

5. **Docker Compose:**
   - Services: engine, dashboard, timescaledb, redis, prometheus, grafana.
   - Volumes for persistent data.
   - Health checks for all services.

## Implementation Path
- Create `src/algoforge/bridge/adapter.py` — BrokerAdapter ABC
- Create `src/algoforge/bridge/alpaca.py` — Alpaca placeholder
- Create `src/algoforge/bridge/deployment.py` — DeploymentConfig
- Create `src/algoforge/bridge/metrics.py` — Prometheus metrics
- Create `docker-compose.yml`
- Create `Dockerfile`
- Create `tests/unit/test_bridge.py`
