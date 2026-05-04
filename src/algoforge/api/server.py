"""AlgoForge Trading API — Live Paper Trading Server.

Decomposed from 650-line monolith into focused modules:
- engine/state.py      — SystemState, models, config
- engine/universe.py   — Universe scoring & kline fetching
- engine/live_handler.py — Tick processing pipeline
- engine/trading_loop.py — Main background loop

This file now contains only:
1. FastAPI app setup & CORS
2. REST endpoints (config, start/stop/reset/flatten)
3. WebSocket telemetry
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from algoforge.engine.state import SystemState, log_msg
from algoforge.engine.trading_loop import trading_engine_loop

logger = structlog.get_logger(__name__)

app = FastAPI(title="AlgoForge Trading API - LIVE PAPER TRADING", version="5.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# GLOBAL STATE
# ---------------------------------------------------------
state = SystemState()
state.restore_checkpoint()  # Phase 9: Restore trade persistence on startup


# ---------------------------------------------------------
# API MODELS & REST ENDPOINTS
# ---------------------------------------------------------
class ConfigRequest(BaseModel):
    market: str
    broker: str
    universe_size: int
    selected_assets_count: int
    min_liquidity: float
    volatility_filter: float
    max_risk_pct: float
    max_drawdown_pct: float


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "system_running": state.is_running}


@app.get("/api/config")
async def get_config():
    return {
        "market": state.discovery_config.market,
        "broker": state.active_broker,
        "universe_size": state.discovery_config.universe_size,
        "selected_assets_count": 5,
        "min_liquidity": state.discovery_config.min_liquidity,
        "volatility_filter": 1.5,
        "max_risk_pct": state.risk_config.max_risk_per_trade_pct,
        "max_drawdown_pct": state.risk_config.max_drawdown_pct,
    }


@app.post("/api/config")
async def update_config(config: ConfigRequest):
    if state.is_running:
        log_msg(state, "Cannot update config while system is running. Pause first.")
        await broadcast_telemetry()
        return {"error": "Cannot update config while system is running."}

    state.discovery_config.market = config.market
    state.discovery_config.universe_size = config.universe_size
    state.discovery_config.min_liquidity = config.min_liquidity
    state.active_broker = config.broker

    # Clamp values to safe fractional ranges via RiskConfig validators
    state.risk_config.max_risk_per_trade_pct = min(config.max_risk_pct, 0.10)
    state.risk_config.max_drawdown_pct = min(config.max_drawdown_pct, 0.50)

    log_msg(state, f"Configuration updated: Market={config.market}, Universe Size={config.universe_size}")
    await broadcast_telemetry()
    return {"status": "success"}


# Phase 4: Data Persistence endpoints
@app.get("/api/trades")
async def get_trade_history():
    """Query persisted trade history from SQLite."""
    trades = state.persistence.get_trade_history(limit=200)
    strategy_stats = state.persistence.get_strategy_stats()
    return {
        "trades": trades,
        "total_persisted": state.persistence.get_trade_count(),
        "strategy_stats": strategy_stats,
    }


@app.get("/api/trades/stats")
async def get_strategy_stats():
    """Aggregated per-strategy performance stats."""
    return state.persistence.get_strategy_stats()


@app.post("/api/system/start")
async def start_system():
    if state.is_running:
        log_msg(state, "System is already running.")
        await broadcast_telemetry()
        return {"status": "already_running"}
    state.is_running = True
    asyncio.create_task(trading_engine_loop(state, broadcast_telemetry))
    # Reset cooldown so prior session losses don't block fresh start
    if state.connector:
        state.connector.reset_risk_limits()
    log_msg(state, "SYSTEM STARTED: Live Paper Trading on WebSocket Streams.")
    await broadcast_telemetry()
    return {"status": "started"}


@app.post("/api/system/stop")
async def stop_system():
    state.is_running = False
    # Fire-and-forget stop — don't await WS close (causes pause delay)
    if state.connector:
        asyncio.create_task(state.connector.stop())
    state.kline_buffers.clear()
    state.selected_assets = []
    state.asset_regimes.clear()
    log_msg(state, "SYSTEM PAUSED. Streams stopping in background.")
    await broadcast_telemetry()
    return {"status": "stopped"}


@app.post("/api/system/reset")
async def reset_system():
    if state.is_running:
        state.is_running = False
        if state.connector:
            await state.connector.stop()
    if state.connector:
        state.connector.reset()
    state.equity_history.clear()
    state.latest_logs.clear()
    state.kline_buffers.clear()
    state.asset_memory.clear()
    state.scored_assets = []
    state.selected_assets = []
    state.asset_regimes.clear()
    state.strategy_signals.clear()
    log_msg(state, "SYSTEM RESET: All data cleared. Starting fresh at $100,000.")
    await broadcast_telemetry()
    return {"status": "reset"}


@app.post("/api/system/flatten")
async def emergency_flatten():
    state.is_running = False
    if state.connector:
        await state.connector.stop()
        state.connector.emergency_flatten()
    log_msg(state, "EMERGENCY FLATTEN: All active positions liquidated. System offline.")
    await broadcast_telemetry()
    return {"status": "flattened"}


@app.get("/api/trades/export")
async def export_trades():
    """Export all completed trades as JSON (Phase 9)."""
    trades = state.persistence.get_trade_history(limit=5000)
    return {"status": "success", "trades": trades}


# ---------------------------------------------------------
# WEBSOCKET TELEMETRY
# ---------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


async def broadcast_telemetry():
    if not state.connector:
        return
        
    snap = state.connector.snapshot()
    live_equity = snap.equity

    if not state.equity_history:
        state.equity_history.append({"time": datetime.now(timezone.utc).isoformat(), "value": live_equity})
    else:
        if live_equity != state.equity_history[-1]["value"] or random.random() < 0.1:
            state.equity_history.append({"time": datetime.now(timezone.utc).isoformat(), "value": live_equity})
    if len(state.equity_history) > 300:
        state.equity_history.pop(0)

    # Build per-asset live data for the UI
    live_assets = []
    for a in state.scored_assets[:15]:
        sym = a["symbol"]
        book = state.live_books.get(sym, {})
        live_assets.append({
            **a,
            "regime": state.asset_regimes.get(sym, "—"),
            "regime_conf": state.asset_confidence.get(sym, 0.0),
            "bid": book.get("bid", 0.0),
            "ask": book.get("ask", 0.0),
        })

    msg = {
        "status": "RUNNING" if state.is_running else "STOPPED",
        "equity": live_equity,
        "cash": round(snap.cash, 2),
        "positions": snap.open_positions,
        "total_trades": snap.total_trades,
        "winning_trades": snap.winning_trades,
        "losing_trades": snap.losing_trades,
        "total_pnl": snap.total_pnl,
        "total_commission": snap.total_commission,
        "max_drawdown_pct": snap.max_drawdown_pct,
        "signals_generated": state.orchestrator._signals_generated,
        "signals_filled": state.orchestrator._signals_filled,
        "open_positions": [p.model_dump(mode='json') for p in state.connector.open_positions],
        "closed_positions": [t.model_dump(mode='json') for t in state.connector.trade_history[-20:]],
        "equity_curve": state.equity_history,
        "scored_assets": live_assets,
        "active_assets": state.selected_assets,
        "logs": state.latest_logs,
    }
    await manager.broadcast(msg)


@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await broadcast_telemetry()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
