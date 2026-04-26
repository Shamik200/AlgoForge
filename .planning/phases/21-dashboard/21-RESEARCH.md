# Phase 21: Dashboard & Monitoring - Research

## Context
Production-grade monitoring dashboard for a quantitative trading system. Must feel like a Bloomberg terminal, not a toy.

## Technical Findings

1. **FastAPI WebSocket Server:**
   - FastAPI natively supports WebSocket endpoints alongside REST.
   - The server will broadcast system state snapshots at a configurable interval (default 1s).
   - State snapshot includes: P&L, positions, signal scores, regime probs, health multipliers, system status.
   - Kill switch command is received on the same WebSocket and triggers an immediate event bus broadcast.

2. **Dashboard Data Models:**
   - `DashboardState` — The complete snapshot sent to the UI each tick.
   - `PositionView` — Simplified position for display (symbol, side, qty, entry, current, unrealized P&L).
   - `SignalHealthView` — Per-family health status (name, score, health, multiplier, status color).
   - `SystemStatus` — Overall engine state (running, paused, killed), uptime, total P&L.

3. **Next.js Frontend:**
   - App Router with `layout.tsx` for consistent dark theme.
   - Client components for WebSocket-connected panels.
   - TradingView lightweight-charts for the equity curve.
   - CSS Grid layout for the 6-panel dashboard.

4. **Kill Switch Safety:**
   - 2-click pattern: Button shows "KILL SWITCH" → Click 1 → Modal "CONFIRM: Flatten ALL positions?" → Click 2 → Execute.
   - Visual feedback: Button pulses red during execution, turns green with checkmark on confirmation.
   - The engine has 2 seconds to respond. If no response, the UI shows a warning.

## Implementation Path
- Create `src/algoforge/dashboard/models.py` — Dashboard data models
- Create `src/algoforge/dashboard/server.py` — FastAPI WebSocket server
- Create `dashboard/` — Next.js app with 6 panels
- Create `tests/unit/test_dashboard.py` — Server-side tests
