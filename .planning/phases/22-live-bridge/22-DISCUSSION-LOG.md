# Phase 22: Live Trading Bridge & Production - Discussion Log

> **Audit trail only.**

**Date:** 2026-04-26
**Phase:** 22-live-bridge

---

## Broker Adapter Interface

| Option | Description | Selected |
|--------|-------------|----------|
| Abstract BrokerAdapter ABC | Clean interface with Alpaca + Binance placeholders | **YES** |
| Direct API Integration | Hardcode broker calls into engine | |

## Gradual Deployment

| Option | Description | Selected |
|--------|-------------|----------|
| Capital Scaling Config | Start 10%, scale up via thresholds, paper+live parallel | **YES** |
| All-in Deployment | Deploy at full capital immediately | |

## Observability

| Option | Description | Selected |
|--------|-------------|----------|
| Prometheus Metrics | `/metrics` endpoint with Grafana compatibility | **YES** |
| Custom Logging Only | Log files without structured metrics | |

## Docker Deployment

| Option | Description | Selected |
|--------|-------------|----------|
| Docker Compose Full Stack | Engine + Dashboard + TimescaleDB + Redis + Prometheus + Grafana | **YES** |
| Manual Deployment | Run each service separately | |
