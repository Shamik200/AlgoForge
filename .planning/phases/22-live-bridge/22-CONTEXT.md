# Phase 22: Live Trading Bridge & Production - Context

**Gathered:** 2026-04-26
**Status:** Completed (Production-grade architecture selected)

<domain>
## Phase Boundary

Build the bridge between the AlgoForge engine and live broker APIs. Includes broker adapter interfaces, gradual deployment pipeline, Prometheus observability, and Docker Compose deployment. This phase makes the system production-ready.
</domain>

<decisions>
## Implementation Decisions

### Broker Adapter Interface
- **D-01:** Abstract BrokerAdapter Base Class. A `BrokerAdapter` ABC with methods: `connect()`, `submit_order()`, `cancel_order()`, `get_positions()`, `get_account()`, `subscribe_market_data()`. Concrete implementations for Alpaca (US equities) and Binance (crypto) as placeholders — real API keys not required for the adapter layer.

### Gradual Deployment
- **D-02:** Capital Scaling Configuration. A `DeploymentConfig` dataclass with `capital_pct` (start at 10%), `scaling_schedule` (list of thresholds for scaling up), and `parallel_mode` (paper + live running simultaneously). The engine reads this config and scales position sizes accordingly.

### Observability
- **D-03:** Prometheus Metrics. Expose key metrics via a `/metrics` endpoint: `signal_latency_ms`, `order_fill_latency_ms`, `event_queue_depth`, `active_positions`, `total_pnl`. Compatible with Grafana dashboards.

### Docker Deployment
- **D-04:** Docker Compose Stack. A `docker-compose.yml` that spins up: AlgoForge engine, dashboard (Next.js), TimescaleDB, Redis (for event bus in production), Prometheus, and Grafana. One command: `docker compose up`.
</decisions>
