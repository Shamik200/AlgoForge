"""Market Memory Engine — Stores asset breakout fakeouts, signal decay, and transition probabilities.
"""

from __future__ import annotations

import sqlite3
import os
import structlog
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


class MarketMemoryEngine:
    """Manages structural profiling of assets (fakeouts, signal decay rates, regime transitions).

    Utilizes SQLite database (`data/algoforge.db`) to persist profile statistics.
    """

    def __init__(self, db_path: str = "data/algoforge.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create tables for market memory profiles if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # 1. Asset Profiles (fakeout and decay tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS asset_profiles (
                    symbol TEXT PRIMARY KEY,
                    total_breakouts INTEGER DEFAULT 0,
                    fakeout_breakouts INTEGER DEFAULT 0,
                    fakeout_rate REAL DEFAULT 0.0,
                    signal_half_life_bars REAL DEFAULT 5.0,
                    last_updated TIMESTAMP
                )
            """)
            
            # 2. HMM Regime Transition Matrix (Counts of transitions between regimes)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regime_transitions (
                    from_regime TEXT,
                    to_regime TEXT,
                    transition_count INTEGER DEFAULT 0,
                    PRIMARY KEY (from_regime, to_regime)
                )
            """)
            conn.commit()
            logger.info("market_memory.db_initialized", db_path=self.db_path)
        except Exception as e:
            logger.error("market_memory.db_init_failed", error=str(e))
        finally:
            conn.close()

    def record_breakout(self, symbol: str, is_fakeout: bool) -> None:
        """Record breakout outcome and update dynamic fakeout rate for the asset."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Ensure asset profile exists
            cursor.execute("INSERT OR IGNORE INTO asset_profiles (symbol) VALUES (?)", (symbol,))
            
            # Update breakout counts
            if is_fakeout:
                cursor.execute("""
                    UPDATE asset_profiles 
                    SET total_breakouts = total_breakouts + 1,
                        fakeout_breakouts = fakeout_breakouts + 1,
                        last_updated = ?
                    WHERE symbol = ?
                """, (datetime.now(timezone.utc).isoformat(), symbol))
            else:
                cursor.execute("""
                    UPDATE asset_profiles 
                    SET total_breakouts = total_breakouts + 1,
                        last_updated = ?
                    WHERE symbol = ?
                """, (datetime.now(timezone.utc).isoformat(), symbol))
                
            # Recalculate rate
            cursor.execute("""
                UPDATE asset_profiles
                SET fakeout_rate = CAST(fakeout_breakouts AS REAL) / CAST(total_breakouts AS REAL)
                WHERE symbol = ? AND total_breakouts > 0
            """, (symbol,))
            
            conn.commit()
            logger.info("market_memory.breakout_recorded", symbol=symbol, is_fakeout=is_fakeout)
        except Exception as e:
            logger.error("market_memory.record_breakout_failed", symbol=symbol, error=str(e))
        finally:
            conn.close()

    def get_fakeout_rate(self, symbol: str) -> float:
        """Get current rolling fakeout rate. Default is 0.0 (no fakeouts recorded)."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT fakeout_rate FROM asset_profiles WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            if row:
                return float(row[0])
            return 0.0
        except Exception as e:
            logger.error("market_memory.get_fakeout_rate_failed", symbol=symbol, error=str(e))
            return 0.0
        finally:
            conn.close()

    def record_regime_transition(self, from_regime: str, to_regime: str) -> None:
        """Track transition history for regime transition probability matrices."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO regime_transitions (from_regime, to_regime, transition_count)
                VALUES (?, ?, 1)
                ON CONFLICT(from_regime, to_regime) DO UPDATE SET
                transition_count = transition_count + 1
            """)
            conn.commit()
            logger.info("market_memory.regime_transition_recorded", from_regime=from_regime, to_regime=to_regime)
        except Exception as e:
            logger.error("market_memory.record_transition_failed", error=str(e))
        finally:
            conn.close()

    def get_transition_probabilities(self, from_regime: str) -> dict[str, float]:
        """Compute relative transition probability vector out of a given regime state."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT to_regime, transition_count 
                FROM regime_transitions 
                WHERE from_regime = ?
            """, (from_regime,))
            rows = cursor.fetchall()
            
            if not rows:
                return {}
                
            total = sum(row[1] for row in rows)
            if total == 0:
                return {}
                
            return {row[0]: (row[1] / total) for row in rows}
        except Exception as e:
            logger.error("market_memory.get_transition_probabilities_failed", from_regime=from_regime, error=str(e))
            return {}
        finally:
            conn.close()
