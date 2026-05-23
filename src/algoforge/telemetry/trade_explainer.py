"""Trade Explainer — Handles post-trade structured explainability logging and storage.
"""

from __future__ import annotations

import json
import sqlite3
import os
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger(__name__)


class TradeExplainer:
    """Generates and persists structured explanation records for executed trades.

    Stores:
    - timeframe alignments (daily bias, mid structure, lower entry triggers)
    - regime states
    - strategy family details
    - RL and FinLLM conviction scores
    - Portfolio engine veto decisions
    - Slippage, spread and execution quality metrics
    - Exit reason & post-mortem analysis
    """

    def __init__(self, db_path: str = "data/algoforge.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the trade explainability table inside the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_explanations (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    timeframe TEXT,
                    daily_bias TEXT,
                    mid_tf_structure TEXT,
                    lower_tf_candlestick TEXT,
                    regime_state TEXT,
                    strategy_family TEXT,
                    meta_router_weight REAL,
                    finllm_sentiment_score REAL,
                    rl_conviction_threshold REAL,
                    risk_decision TEXT,
                    pearson_correlation REAL,
                    slippage REAL,
                    execution_latency_ms REAL,
                    close_reason TEXT,
                    win_loss TEXT,
                    r_multiple REAL,
                    raw_explanation_json TEXT,
                    created_at TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("trade_explainer.db_initialized", db_path=self.db_path)
        except Exception as e:
            logger.error("trade_explainer.db_init_failed", error=str(e))
        finally:
            conn.close()

    def save_explanation(self, explanation_record: dict) -> None:
        """Persist a complete explainability record to the database."""
        trade_id = explanation_record.get("trade_id", "")
        if not trade_id:
            logger.error("trade_explainer.save_failed.no_trade_id")
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            context = explanation_record.get("context", {})
            tf_align = explanation_record.get("timeframe_alignment", {})
            strat_prior = explanation_record.get("strategy_prioritization", {})
            models = explanation_record.get("model_contributions", {})
            risk = explanation_record.get("risk_parameters", {})
            exec_metrics = explanation_record.get("execution_metrics", {})
            exit_pm = explanation_record.get("exit_post_mortem", {})

            cursor.execute("""
                INSERT OR REPLACE INTO trade_explanations (
                    trade_id, symbol, timeframe, daily_bias, mid_tf_structure,
                    lower_tf_candlestick, regime_state, strategy_family, meta_router_weight,
                    finllm_sentiment_score, rl_conviction_threshold, risk_decision,
                    pearson_correlation, slippage, execution_latency_ms, close_reason,
                    win_loss, r_multiple, raw_explanation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                context.get("asset", ""),
                context.get("timeframe", ""),
                tf_align.get("daily_bias", ""),
                tf_align.get("mid_tf_structure", ""),
                tf_align.get("lower_tf_candlestick", ""),
                strat_prior.get("regime_state", ""),
                strat_prior.get("strategy_family", ""),
                strat_prior.get("meta_router_weight", 1.0),
                models.get("finllm_sentiment_score", 0.0),
                models.get("rl_conviction_threshold", 0.0),
                risk.get("portfolio_veto", ""),
                risk.get("correlation_check", {}).get("max_pearson", 0.0),
                exec_metrics.get("slippage", 0.0),
                exec_metrics.get("execution_latency_ms", 0.0),
                exit_pm.get("close_reason", ""),
                exit_pm.get("win_loss", ""),
                exit_pm.get("r_multiple", 0.0),
                json.dumps(explanation_record),
                datetime.now(timezone.utc).isoformat()
            ))
            
            conn.commit()
            logger.info("trade_explainer.saved_explanation", trade_id=trade_id)
        except Exception as e:
            logger.error("trade_explainer.save_failed", trade_id=trade_id, error=str(e))
        finally:
            conn.close()

    def get_explanation(self, trade_id: str) -> dict | None:
        """Retrieve a saved explainability record by trade ID."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT raw_explanation_json FROM trade_explanations WHERE trade_id = ?", (trade_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger.error("trade_explainer.get_failed", trade_id=trade_id, error=str(e))
            return None
        finally:
            conn.close()
