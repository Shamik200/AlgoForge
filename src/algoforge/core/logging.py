"""AlgoForge structured logging setup.

Configures structlog for JSON or console output. All components use
`structlog.get_logger()` — this module configures the shared pipeline.
"""

from __future__ import annotations

import gzip
import logging
import shutil
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

from algoforge.core.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the entire application.

    Call once at startup before any other modules log.
    Reads logging config from settings.yaml.
    """
    settings = get_settings()
    cfg = settings.logging

    # Determine log level
    log_level = getattr(logging, cfg.level.upper(), logging.INFO)

    # Choose renderer based on format setting
    if cfg.format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create log directory if file logging is enabled
    if cfg.log_file:
        log_path = Path(cfg.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure stdlib logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.get_logger().info(
        "logging.configured",
        level=cfg.level,
        format=cfg.format,
        log_file=cfg.log_file,
    )


def _compress_log_file(source: str, dest: str) -> None:
    """Compress a log file using gzip.
    
    Args:
        source: Path to the source log file
        dest: Path to the compressed destination file
    """
    with open(source, 'rb') as f_in:
        with gzip.open(dest, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)


class CompressingTimedRotatingFileHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler that compresses rotated log files."""
    
    def doRollover(self) -> None:
        """Perform rollover and compress the old log file."""
        try:
            super().doRollover()
        except PermissionError:
            # Silently skip log rotation when the file is locked by another process (common on Windows)
            return
        
        # Find the rotated file and compress it
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename(f"{self.baseFilename}.{i}")
                if Path(sfn).exists() and not sfn.endswith('.gz'):
                    dfn = f"{sfn}.gz"
                    _compress_log_file(sfn, dfn)
                    Path(sfn).unlink()


class StructuredLogger:
    """Structured JSON logger for all system events.
    
    Provides specialized logging methods for different event types in the trading system:
    - Signal generation
    - Trade decisions
    - Risk vetos
    - RL threshold adjustments
    - Stop-loss/take-profit changes
    
    All logs are output in JSON format with consistent field names for easy parsing
    and analysis.
    """
    
    def __init__(self, name: str = "algoforge") -> None:
        """Initialize the structured logger.
        
        Args:
            name: Logger name (default: "algoforge")
        """
        self.logger = structlog.get_logger(name)
        # Also keep a stdlib logger for compatibility with pytest caplog
        self.std_logger = logging.getLogger(name)
        self._setup_file_rotation()
    
    def _setup_file_rotation(self) -> None:
        """Set up log file rotation and compression.
        
        Configures daily log rotation with compression of old logs.
        """
        settings = get_settings()
        cfg = settings.logging
        
        if not cfg.log_file:
            return
        
        log_path = Path(cfg.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set up rotating file handler with daily rotation
        handler = CompressingTimedRotatingFileHandler(
            filename=str(log_path),
            when='midnight',
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding='utf-8',
        )
        
        # Set log level
        log_level = getattr(logging, cfg.level.upper(), logging.INFO)
        handler.setLevel(log_level)
        
        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
    
    def log_signal_generation(
        self,
        signal: Any,
        contributing_factors: dict[str, Any],
    ) -> None:
        """Log signal generation with all contributing factors.
        
        Args:
            signal: SignalResult object containing the generated signal
            contributing_factors: Dictionary of factors that contributed to the signal
                (e.g., signal family scores, conviction, regime, ML predictions)
        """
        self.logger.info(
            "signal.generated",
            event_type="signal_generation",
            family_name=signal.family_name,
            score=signal.score,
            direction=signal.direction.value if hasattr(signal.direction, 'value') else signal.direction,
            is_valid=signal.is_valid,
            sub_scores=signal.sub_scores,
            metadata=signal.metadata,
            contributing_factors=contributing_factors,
        )
        try:
            self.std_logger.info("signal.generated", extra={"event_type": "signal_generation", "family_name": signal.family_name})
        except Exception:
            pass
    
    def log_trade_decision(
        self,
        decision: Any,
        decision_tree: dict[str, Any],
    ) -> None:
        """Log trade decision with full reasoning.
        
        Args:
            decision: TradeDecision object containing the decision details
            decision_tree: Dictionary explaining the decision logic
                (why the trade was accepted or rejected)
        """
        self.logger.info(
            "trade.decision",
            event_type="trade_decision",
            decision=decision.decision if hasattr(decision, 'decision') else str(decision),
            signal_family=decision.signal.family_name if hasattr(decision, 'signal') else None,
            signal_score=decision.signal.score if hasattr(decision, 'signal') else None,
            position_size=decision.position_size if hasattr(decision, 'position_size') else None,
            entry_price=decision.entry_price if hasattr(decision, 'entry_price') else None,
            stop_loss=decision.stop_loss if hasattr(decision, 'stop_loss') else None,
            take_profit_levels=decision.take_profit_levels if hasattr(decision, 'take_profit_levels') else None,
            conviction_breakdown=decision.conviction_breakdown if hasattr(decision, 'conviction_breakdown') else None,
            veto_reason=decision.veto_reason if hasattr(decision, 'veto_reason') else None,
            decision_tree=decision_tree,
        )
        try:
            self.std_logger.info("trade.decision", extra={"event_type": "trade_decision", "decision": decision.decision if hasattr(decision, 'decision') else str(decision)})
        except Exception:
            pass
    
    def log_risk_veto(
        self,
        signal: Any,
        violated_rule: str,
        details: dict[str, Any],
    ) -> None:
        """Log risk manager veto with the specific rule violated.
        
        Args:
            signal: SignalResult that was vetoed
            violated_rule: Name of the risk rule that was violated
            details: Additional details about the violation
        """
        self.logger.warning(
            "risk.veto",
            event_type="risk_veto",
            family_name=signal.family_name,
            signal_score=signal.score,
            signal_direction=signal.direction.value if hasattr(signal.direction, 'value') else signal.direction,
            violated_rule=violated_rule,
            details=details,
        )
        try:
            self.std_logger.warning("risk.veto", extra={"event_type": "risk_veto", "violated_rule": violated_rule})
        except Exception:
            pass
    
    def log_threshold_adjustment(
        self,
        adjustment: Any,
        triggering_trades: list[str],
    ) -> None:
        """Log RL agent threshold adjustment.
        
        Args:
            adjustment: ThresholdAdjustments object with before/after values
            triggering_trades: List of trade IDs that triggered the adjustment
        """
        self.logger.info(
            "rl.threshold_adjustment",
            event_type="threshold_adjustment",
            conviction_thresholds=adjustment.conviction_thresholds if hasattr(adjustment, 'conviction_thresholds') else None,
            position_size_limits=adjustment.position_size_limits if hasattr(adjustment, 'position_size_limits') else None,
            signal_family_weights=adjustment.signal_family_weights if hasattr(adjustment, 'signal_family_weights') else None,
            ml_confidence_threshold=adjustment.ml_confidence_threshold if hasattr(adjustment, 'ml_confidence_threshold') else None,
            adjustments_reason=adjustment.adjustments_reason if hasattr(adjustment, 'adjustments_reason') else None,
            trades_analyzed=adjustment.trades_analyzed if hasattr(adjustment, 'trades_analyzed') else None,
            triggering_trades=triggering_trades,
        )
        try:
            self.std_logger.info("rl.threshold_adjustment", extra={"event_type": "threshold_adjustment"})
        except Exception:
            pass
    
    def log_sltp_adjustment(
        self,
        position_id: str,
        adjustment_type: str,
        old_stop_loss: float | None,
        new_stop_loss: float | None,
        old_take_profit: float | None,
        new_take_profit: float | None,
        trigger: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log dynamic stop-loss/take-profit adjustment.
        
        Args:
            position_id: ID of the position being adjusted
            adjustment_type: Type of adjustment (e.g., "tighten_sl", "widen_tp", "breakeven")
            old_stop_loss: Previous stop-loss level
            new_stop_loss: New stop-loss level
            old_take_profit: Previous take-profit level
            new_take_profit: New take-profit level
            trigger: What triggered the adjustment (e.g., "regime_change", "ml_confidence_increase")
            details: Additional details about the adjustment
        """
        self.logger.info(
            "sltp.adjustment",
            event_type="sltp_adjustment",
            position_id=position_id,
            adjustment_type=adjustment_type,
            old_stop_loss=old_stop_loss,
            new_stop_loss=new_stop_loss,
            old_take_profit=old_take_profit,
            new_take_profit=new_take_profit,
            trigger=trigger,
            details=details or {},
        )
        try:
            self.std_logger.info("sltp.adjustment", extra={"event_type": "sltp_adjustment", "position_id": position_id})
        except Exception:
            pass
    
    def log_ml_prediction(
        self,
        symbol: str,
        prediction: Any,
        features: dict[str, float] | None = None,
    ) -> None:
        """Log ML pipeline prediction.
        
        Args:
            symbol: Trading symbol
            prediction: ML prediction object
            features: Feature values used for prediction
        """
        self.logger.debug(
            "ml.prediction",
            event_type="ml_prediction",
            symbol=symbol,
            direction=prediction.direction if hasattr(prediction, 'direction') else None,
            probability=prediction.probability if hasattr(prediction, 'probability') else None,
            confidence=prediction.confidence if hasattr(prediction, 'confidence') else None,
            xgboost_score=prediction.xgboost_score if hasattr(prediction, 'xgboost_score') else None,
            ensemble_score=prediction.ensemble_score if hasattr(prediction, 'ensemble_score') else None,
            feature_importance=prediction.feature_importance if hasattr(prediction, 'feature_importance') else None,
            features=features,
        )
        try:
            self.std_logger.debug("ml.prediction", extra={"event_type": "ml_prediction", "symbol": symbol})
        except Exception:
            pass
    
    def log_regime_detection(
        self,
        symbol: str,
        regime_probs: dict[str, float],
        previous_regime: str | None = None,
        current_regime: str | None = None,
    ) -> None:
        """Log HMM regime detection.
        
        Args:
            symbol: Trading symbol
            regime_probs: Probability distribution over regimes
            previous_regime: Previous regime (if changed)
            current_regime: Current regime (if changed)
        """
        log_method = self.logger.info if previous_regime != current_regime else self.logger.debug
        
        log_method(
            "regime.detection",
            event_type="regime_detection",
            symbol=symbol,
            regime_probs=regime_probs,
            previous_regime=previous_regime,
            current_regime=current_regime,
            regime_changed=previous_regime != current_regime,
        )
        try:
            # Mirror to stdlib for capture
            if previous_regime != current_regime:
                self.std_logger.info("regime.detection", extra={"event_type": "regime_detection", "symbol": symbol})
            else:
                self.std_logger.debug("regime.detection", extra={"event_type": "regime_detection", "symbol": symbol})
        except Exception:
            pass
    
    def log_position_opened(
        self,
        position_id: str,
        symbol: str,
        direction: str,
        size: float,
        entry_price: float,
        stop_loss: float,
        take_profit_levels: list[float],
        conviction_score: float,
    ) -> None:
        """Log position opening.
        
        Args:
            position_id: Unique position identifier
            symbol: Trading symbol
            direction: Position direction (long/short)
            size: Position size
            entry_price: Entry price
            stop_loss: Initial stop-loss level
            take_profit_levels: Take-profit levels
            conviction_score: Conviction score that determined position size
        """
        self.logger.info(
            "position.opened",
            event_type="position_opened",
            position_id=position_id,
            symbol=symbol,
            direction=direction,
            size=size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_levels=take_profit_levels,
            conviction_score=conviction_score,
        )
        try:
            self.std_logger.info("position.opened", extra={"event_type": "position_opened", "position_id": position_id})
        except Exception:
            pass
    
    def log_position_closed(
        self,
        position_id: str,
        symbol: str,
        exit_price: float,
        pnl_dollars: float,
        pnl_percent: float,
        r_multiple: float,
        exit_reason: str,
        time_in_trade: float,
    ) -> None:
        """Log position closing.
        
        Args:
            position_id: Unique position identifier
            symbol: Trading symbol
            exit_price: Exit price
            pnl_dollars: P&L in dollars
            pnl_percent: P&L as percentage
            r_multiple: R-multiple (profit/initial_risk)
            exit_reason: Reason for exit
            time_in_trade: Time in trade (seconds)
        """
        self.logger.info(
            "position.closed",
            event_type="position_closed",
            position_id=position_id,
            symbol=symbol,
            exit_price=exit_price,
            pnl_dollars=pnl_dollars,
            pnl_percent=pnl_percent,
            r_multiple=r_multiple,
            exit_reason=exit_reason,
            time_in_trade_seconds=time_in_trade,
        )
        try:
            self.std_logger.info("position.closed", extra={"event_type": "position_closed", "position_id": position_id})
        except Exception:
            pass
    
    def log_error(
        self,
        error_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        exc_info: bool = False,
    ) -> None:
        """Log an error with details.
        
        Args:
            error_type: Type/category of error
            message: Error message
            details: Additional error details
            exc_info: Whether to include exception info
        """
        self.logger.error(
            message,
            event_type="error",
            error_type=error_type,
            details=details or {},
            exc_info=exc_info,
        )
        try:
            self.std_logger.error(message, extra={"event_type": "error", "error_type": error_type})
        except Exception:
            pass
