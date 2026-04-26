# Phase 21: Dashboard & Monitoring - Context

**Gathered:** 2026-04-26
**Status:** Completed (HFT-grade architecture selected)

<domain>
## Phase Boundary

Build a production-grade monitoring dashboard for the AlgoForge trading system. Real-time WebSocket updates for P&L, positions, signals, and regime state. Kill switch for emergency position flattening. Dark-themed, professional trading terminal aesthetic.
</domain>

<decisions>
## Implementation Decisions

### Frontend Architecture
- **D-01:** Next.js App Router. Server components for initial page load (SEO, fast TTI), client components for WebSocket real-time updates. TradingView's lightweight-charts for equity curves and price charts. Recharts for signal analytics bar/pie charts.

### Backend API Layer
- **D-02:** FastAPI WebSocket Server. A dedicated `src/algoforge/dashboard/server.py` that:
  - Streams live P&L, positions, signal scores, and regime state via WebSocket
  - REST endpoints for historical data (/api/backtest, /api/performance)
  - Serves the dashboard static files in production

### Kill Switch
- **D-03:** WebSocket Command Channel. The kill switch sends a `FLATTEN_ALL` command through a dedicated WebSocket channel. The engine processes it within 2 seconds. The UI shows real-time confirmation with a red/green state indicator and a 2-click safety (click → confirm modal → execute).

### Design System
- **D-04:** Professional Trading Terminal. Dark theme (HSL-based color system). Color coding:
  - Green (#00C853) = profit/healthy
  - Red (#FF1744) = loss/degraded/paused
  - Amber (#FFD600) = warning/degraded
  - Blue (#2979FF) = informational/neutral
  - Glassmorphism cards with `backdrop-filter: blur(12px)` and subtle borders

### Data Visualization
- **D-05:** Six Dashboard Panels:
  1. Live P&L ticker + equity curve (lightweight-charts)
  2. Open positions table with unrealized P&L
  3. HMM regime probabilities (color-coded stacked bars)
  4. Signal family health dashboard (decay monitor status)
  5. Signal combination breakdown (conviction weights per family)
  6. Kill switch control panel with system status
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 21 success criteria
- `.planning/phases/14-paper-trading/14-CONTEXT.md` — Position data model
- `.planning/phases/16-alpha-decay/16-CONTEXT.md` — Health multiplier model
</canonical_refs>
