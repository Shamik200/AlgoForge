---
gap_closure: false
---

# Plan 21-01: Dashboard & Monitoring

## Objective
Build a production-grade monitoring dashboard with FastAPI WebSocket backend and Next.js frontend. 6-panel dark-themed trading terminal with real-time updates and kill switch.

## Tasks

- [ ] **1. Dashboard Data Models**
  - Create `src/algoforge/dashboard/models.py`.
  - Define DashboardState, PositionView, SignalHealthView, SystemStatus.

- [ ] **2. FastAPI WebSocket Server**
  - Create `src/algoforge/dashboard/server.py`.
  - WebSocket endpoint broadcasting state snapshots.
  - REST endpoints for historical data.
  - Kill switch command handler.

- [ ] **3. Next.js Dashboard Frontend**
  - Initialize Next.js app in `dashboard/`.
  - Dark theme with CSS variables.
  - 6-panel CSS Grid layout.
  - WebSocket client hook for real-time updates.

- [ ] **4. Dashboard Panels**
  - P&L ticker + equity curve panel.
  - Open positions table panel.
  - HMM regime probability panel.
  - Signal family health panel.
  - Signal combination breakdown panel.
  - Kill switch control panel.

- [ ] **5. Integration & Testing**
  - Create `src/algoforge/dashboard/__init__.py`.
  - Create `tests/unit/test_dashboard.py`.
  - Test data model serialization and state snapshot generation.
