# Phase 21: Dashboard & Monitoring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-26
**Phase:** 21-dashboard
**Areas discussed:** Frontend Architecture, Backend API, Kill Switch, Design System, Data Visualization

---

## Frontend Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Next.js App Router | Server + Client components, lightweight-charts, Recharts | **YES** |
| React SPA (Vite) | Simpler but no SSR, no server components | |
| Streamlit | Python-native, fast but toy-like for production | |

## Backend API Layer

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI WebSocket Server | Streams live data via WebSocket, REST for historical | **YES** |
| Django Channels | Heavier, more boilerplate | |
| Socket.io (Node) | Separate runtime from Python engine | |

## Kill Switch

| Option | Description | Selected |
|--------|-------------|----------|
| WebSocket Command Channel | 2-click safety, <2s execution, visual confirmation | **YES** |
| REST API endpoint | Simpler but no real-time feedback | |

## Design System

| Option | Description | Selected |
|--------|-------------|----------|
| Dark Trading Terminal | HSL colors, glassmorphism, professional aesthetic | **YES** |
| Light Material Design | Standard but not what traders expect | |

## Data Visualization

| Option | Description | Selected |
|--------|-------------|----------|
| 6-Panel Dashboard | P&L, positions, regime, health, signals, kill switch | **YES** |
| Tabbed Interface | One panel at a time | |
