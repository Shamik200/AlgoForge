"""Data Persistence — SQLite-backed trade history, kline cache, and state checkpoint.

Phase 4: Ensures no data loss across restarts:
- Trade history persisted to SQLite
- Kline buffers cached to avoid re-fetching
- System state checkpoint (equity, positions) saved periodically

Inspired by:
- Freqtrade SQLite trade persistence
- Qlib data handler caching
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_DB_PATH = "data/algoforge.db"


class PersistenceStore:
    """SQLite-backed persistence for trade history, klines, and state."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read perf
        self._create_tables()
        logger.info("persistence_store_initialized", db_path=db_path)

    def _create_tables(self) -> None:
        """Create all persistence tables."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                strategy TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity REAL NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                pnl REAL NOT NULL,
                commission REAL NOT NULL,
                slippage REAL NOT NULL,
                bars_held INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS kline_cache (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                PRIMARY KEY (symbol, timeframe, timestamp)
            );

            CREATE TABLE IF NOT EXISTS state_checkpoint (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_trades_symbol
                ON trade_history(symbol);
            CREATE INDEX IF NOT EXISTS idx_trades_strategy
                ON trade_history(strategy);
            CREATE INDEX IF NOT EXISTS idx_klines_symbol_tf
                ON kline_cache(symbol, timeframe);
        """)
        self._conn.commit()

    # ─── TRADE HISTORY ──────────────────────────────────────────────

    def save_trade(self, trade: dict) -> None:
        """Persist a completed trade record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO trade_history
               (id, symbol, direction, strategy, entry_price, exit_price,
                quantity, entry_time, exit_time, pnl, commission, slippage, bars_held)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade["id"], trade["symbol"], trade["direction"],
                trade["strategy"], trade["entry_price"], trade["exit_price"],
                trade["quantity"], trade["entry_time"], trade["exit_time"],
                trade["pnl"], trade["commission"], trade["slippage"],
                trade.get("bars_held", 0),
            ),
        )
        self._conn.commit()

    def get_trade_history(self, limit: int = 500) -> list[dict]:
        """Load recent trade history."""
        cursor = self._conn.execute(
            "SELECT * FROM trade_history ORDER BY exit_time DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_trade_count(self) -> int:
        """Get total number of persisted trades."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM trade_history")
        return cursor.fetchone()[0]

    def get_strategy_stats(self) -> dict[str, dict]:
        """Aggregate win rate and PnL per strategy."""
        cursor = self._conn.execute("""
            SELECT strategy,
                   COUNT(*) as total,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(pnl) as total_pnl,
                   AVG(pnl) as avg_pnl
            FROM trade_history
            GROUP BY strategy
        """)
        stats = {}
        for row in cursor.fetchall():
            stats[row["strategy"]] = {
                "total": row["total"],
                "wins": row["wins"],
                "win_rate": round(row["wins"] / row["total"] * 100, 1) if row["total"] > 0 else 0,
                "total_pnl": round(row["total_pnl"], 2),
                "avg_pnl": round(row["avg_pnl"], 2),
            }
        return stats

    # ─── KLINE CACHE ────────────────────────────────────────────────

    def save_klines(self, symbol: str, timeframe: str, candles: list[dict]) -> None:
        """Persist kline buffer for a symbol."""
        if not candles:
            return
        self._conn.executemany(
            """INSERT OR REPLACE INTO kline_cache
               (symbol, timeframe, timestamp, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (symbol, timeframe, c["timestamp"], c["open"],
                 c["high"], c["low"], c["close"], c["volume"])
                for c in candles
            ],
        )
        self._conn.commit()

    def load_klines(self, symbol: str, timeframe: str, limit: int = 300) -> list[dict]:
        """Load cached klines for a symbol."""
        cursor = self._conn.execute(
            """SELECT * FROM kline_cache
               WHERE symbol = ? AND timeframe = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (symbol, timeframe, limit),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        rows.reverse()  # Oldest first
        return rows

    def has_klines(self, symbol: str, timeframe: str, min_count: int = 50) -> bool:
        """Check if we have enough cached klines."""
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM kline_cache WHERE symbol = ? AND timeframe = ?",
            (symbol, timeframe),
        )
        return cursor.fetchone()[0] >= min_count

    def clear_klines(self, symbol: str | None = None) -> None:
        """Clear kline cache for a symbol or all symbols."""
        if symbol:
            self._conn.execute("DELETE FROM kline_cache WHERE symbol = ?", (symbol,))
        else:
            self._conn.execute("DELETE FROM kline_cache")
        self._conn.commit()

    # ─── STATE CHECKPOINT ───────────────────────────────────────────

    def save_checkpoint(self, key: str, value: Any) -> None:
        """Save a state checkpoint value (JSON-serialized)."""
        self._conn.execute(
            """INSERT OR REPLACE INTO state_checkpoint (key, value, updated_at)
               VALUES (?, ?, ?)""",
            (key, json.dumps(value), datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def load_checkpoint(self, key: str) -> Any | None:
        """Load a state checkpoint value."""
        cursor = self._conn.execute(
            "SELECT value FROM state_checkpoint WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["value"])
        return None

    def save_full_state(
        self,
        equity: float,
        cash: float,
        positions: list[dict],
        selected_assets: list[str],
        ml_trained: bool,
    ) -> None:
        """Save full system state as a checkpoint."""
        state = {
            "equity": equity,
            "cash": cash,
            "positions": positions,
            "selected_assets": selected_assets,
            "ml_trained": ml_trained,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.save_checkpoint("system_state", state)
        logger.debug("state_checkpoint_saved", equity=equity, positions=len(positions))

    def load_full_state(self) -> dict | None:
        """Load the last saved system state."""
        return self.load_checkpoint("system_state")

    # ─── LIFECYCLE ──────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
