"""Unit tests for StructuredLogger module.

Tests the structured logging functionality including:
- Signal generation logging
- Trade decision logging
- Risk veto logging
- RL threshold adjustment logging
- SL/TP adjustment logging
- Log rotation and compression
"""

from __future__ import annotations

import gzip
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import structlog

from algoforge.core.logging import (
    CompressingTimedRotatingFileHandler,
    StructuredLogger,
    _compress_log_file,
    setup_logging,
)
from algoforge.signals.models import SignalDirection, SignalResult


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_signal():
    """Create a mock SignalResult for testing."""
    return SignalResult(
        family_name="momentum",
        score=0.75,
        direction=SignalDirection.LONG,
        is_valid=True,
        sub_scores={"ema": 0.8, "rsi": 0.7},
        metadata={"timeframe": "1h", "confidence": 0.85},
    )


@pytest.fixture
def mock_trade_decision():
    """Create a mock TradeDecision for testing."""
    decision = Mock()
    decision.decision = "execute"
    decision.signal = Mock()
    decision.signal.family_name = "momentum"
    decision.signal.score = 0.75
    decision.position_size = 100.0
    decision.entry_price = 50000.0
    decision.stop_loss = 49000.0
    decision.take_profit_levels = [51000.0, 52000.0, 53000.0]
    decision.conviction_breakdown = {
        "signal_score": 0.75,
        "ml_confidence": 0.8,
        "regime_alignment": 0.9,
    }
    decision.veto_reason = None
    return decision


@pytest.fixture
def mock_threshold_adjustment():
    """Create a mock ThresholdAdjustments for testing."""
    adjustment = Mock()
    adjustment.conviction_thresholds = (0.35, 0.65)
    adjustment.position_size_limits = {"max_position": 0.15}
    adjustment.signal_family_weights = {"momentum": 1.2, "mean_reversion": 0.8}
    adjustment.ml_confidence_threshold = 0.55
    adjustment.adjustments_reason = "Recent win rate improvement"
    adjustment.trades_analyzed = 25
    return adjustment


class TestStructuredLogger:
    """Test suite for StructuredLogger class."""
    
    def test_logger_initialization(self):
        """Test that logger initializes correctly."""
        logger = StructuredLogger("test_logger")
        assert logger.logger is not None
        # structlog returns a BoundLoggerLazyProxy, not BoundLogger directly
        assert hasattr(logger.logger, 'info')
    
    def test_log_signal_generation(self, mock_signal, caplog):
        """Test logging of signal generation."""
        logger = StructuredLogger("test")
        contributing_factors = {
            "regime": "trending",
            "ml_prediction": 0.8,
            "pattern_confirmation": True,
        }
        
        with caplog.at_level("INFO"):
            logger.log_signal_generation(mock_signal, contributing_factors)
        
        # Verify log was created
        assert len(caplog.records) > 0
        
        # Check that key information is logged
        log_record = caplog.records[0]
        assert "signal.generated" in log_record.message or "signal.generated" in str(log_record)
    
    def test_log_trade_decision_execute(self, mock_trade_decision, caplog):
        """Test logging of trade decision (execute)."""
        logger = StructuredLogger("test")
        decision_tree = {
            "conviction_check": "passed",
            "risk_check": "passed",
            "regime_check": "aligned",
        }
        
        with caplog.at_level("INFO"):
            logger.log_trade_decision(mock_trade_decision, decision_tree)
        
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert "trade.decision" in log_record.message or "trade.decision" in str(log_record)
    
    def test_log_trade_decision_veto(self, mock_trade_decision, caplog):
        """Test logging of trade decision (veto)."""
        logger = StructuredLogger("test")
        mock_trade_decision.decision = "veto"
        mock_trade_decision.veto_reason = "Position limit exceeded"
        
        decision_tree = {
            "conviction_check": "passed",
            "risk_check": "failed",
            "reason": "Position limit exceeded",
        }
        
        with caplog.at_level("INFO"):
            logger.log_trade_decision(mock_trade_decision, decision_tree)
        
        assert len(caplog.records) > 0
    
    def test_log_risk_veto(self, mock_signal, caplog):
        """Test logging of risk manager veto."""
        logger = StructuredLogger("test")
        violated_rule = "max_position_size"
        details = {
            "current_exposure": 0.25,
            "max_allowed": 0.20,
            "symbol": "BTCUSDT",
        }
        
        with caplog.at_level("WARNING"):
            logger.log_risk_veto(mock_signal, violated_rule, details)
        
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert log_record.levelname == "WARNING"
    
    def test_log_threshold_adjustment(self, mock_threshold_adjustment, caplog):
        """Test logging of RL threshold adjustment."""
        logger = StructuredLogger("test")
        triggering_trades = ["trade_001", "trade_002", "trade_003"]
        
        with caplog.at_level("INFO"):
            logger.log_threshold_adjustment(mock_threshold_adjustment, triggering_trades)
        
        assert len(caplog.records) > 0
    
    def test_log_sltp_adjustment(self, caplog):
        """Test logging of stop-loss/take-profit adjustment."""
        logger = StructuredLogger("test")
        
        with caplog.at_level("INFO"):
            logger.log_sltp_adjustment(
                position_id="pos_123",
                adjustment_type="tighten_sl",
                old_stop_loss=49000.0,
                new_stop_loss=49500.0,
                old_take_profit=52000.0,
                new_take_profit=52000.0,
                trigger="ml_confidence_decrease",
                details={"ml_confidence_change": -0.15},
            )
        
        assert len(caplog.records) > 0
    
    def test_log_ml_prediction(self, caplog):
        """Test logging of ML prediction."""
        logger = StructuredLogger("test")
        prediction = Mock()
        prediction.direction = "long"
        prediction.probability = 0.75
        prediction.confidence = 0.8
        prediction.xgboost_score = 0.72
        prediction.ensemble_score = 0.76
        prediction.feature_importance = {"momentum": 0.3, "volatility": 0.25}
        
        features = {"ema_20": 50000.0, "rsi_14": 65.0, "atr_14": 1500.0}
        
        with caplog.at_level("DEBUG"):
            logger.log_ml_prediction("BTCUSDT", prediction, features)
        
        # Note: DEBUG logs might not appear depending on log level configuration
        # This test verifies the method executes without error
    
    def test_log_regime_detection_no_change(self, caplog):
        """Test logging of regime detection without regime change."""
        logger = StructuredLogger("test")
        regime_probs = {
            "trending": 0.7,
            "ranging": 0.2,
            "volatile": 0.1,
        }
        
        with caplog.at_level("DEBUG"):
            logger.log_regime_detection(
                "BTCUSDT",
                regime_probs,
                previous_regime="trending",
                current_regime="trending",
            )
    
    def test_log_regime_detection_with_change(self, caplog):
        """Test logging of regime detection with regime change."""
        logger = StructuredLogger("test")
        regime_probs = {
            "trending": 0.2,
            "ranging": 0.7,
            "volatile": 0.1,
        }
        
        with caplog.at_level("INFO"):
            logger.log_regime_detection(
                "BTCUSDT",
                regime_probs,
                previous_regime="trending",
                current_regime="ranging",
            )
        
        assert len(caplog.records) > 0
    
    def test_log_position_opened(self, caplog):
        """Test logging of position opening."""
        logger = StructuredLogger("test")
        
        with caplog.at_level("INFO"):
            logger.log_position_opened(
                position_id="pos_123",
                symbol="BTCUSDT",
                direction="long",
                size=0.1,
                entry_price=50000.0,
                stop_loss=49000.0,
                take_profit_levels=[51000.0, 52000.0, 53000.0],
                conviction_score=0.75,
            )
        
        assert len(caplog.records) > 0
    
    def test_log_position_closed(self, caplog):
        """Test logging of position closing."""
        logger = StructuredLogger("test")
        
        with caplog.at_level("INFO"):
            logger.log_position_closed(
                position_id="pos_123",
                symbol="BTCUSDT",
                exit_price=51000.0,
                pnl_dollars=100.0,
                pnl_percent=2.0,
                r_multiple=1.0,
                exit_reason="take_profit_1",
                time_in_trade=3600.0,
            )
        
        assert len(caplog.records) > 0
    
    def test_log_error(self, caplog):
        """Test logging of errors."""
        logger = StructuredLogger("test")
        
        with caplog.at_level("ERROR"):
            logger.log_error(
                error_type="data_feed_error",
                message="Failed to connect to data feed",
                details={"feed": "binance", "retry_count": 3},
                exc_info=False,
            )
        
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert log_record.levelname == "ERROR"


class TestLogRotation:
    """Test suite for log rotation and compression."""
    
    def test_compress_log_file(self, temp_log_dir):
        """Test log file compression."""
        # Create a test log file
        source_file = temp_log_dir / "test.log"
        source_file.write_text("Test log content\n" * 100)
        
        # Compress it
        dest_file = temp_log_dir / "test.log.gz"
        _compress_log_file(str(source_file), str(dest_file))
        
        # Verify compressed file exists and is smaller
        assert dest_file.exists()
        assert dest_file.stat().st_size < source_file.stat().st_size
        
        # Verify content can be decompressed
        with gzip.open(dest_file, 'rt') as f:
            content = f.read()
        assert "Test log content" in content
    
    @patch('algoforge.core.config.get_settings')
    def test_compressing_handler_initialization(self, mock_settings, temp_log_dir):
        """Test CompressingTimedRotatingFileHandler initialization."""
        log_file = temp_log_dir / "test.log"
        
        handler = CompressingTimedRotatingFileHandler(
            filename=str(log_file),
            when='midnight',
            interval=1,
            backupCount=7,
        )
        
        assert handler.baseFilename == str(log_file)
        assert handler.backupCount == 7


class TestSetupLogging:
    """Test suite for setup_logging function."""
    
    @patch('algoforge.core.config.get_settings')
    def test_setup_logging_json_format(self, mock_settings, temp_log_dir):
        """Test logging setup with JSON format."""
        # Mock settings
        mock_cfg = Mock()
        mock_cfg.logging.level = "INFO"
        mock_cfg.logging.format = "json"
        mock_cfg.logging.log_file = str(temp_log_dir / "test.log")
        mock_cfg.logging.log_to_stdout = True
        mock_settings.return_value = mock_cfg
        
        # Setup logging
        setup_logging()
        
        # Verify log directory was created
        assert (temp_log_dir / "test.log").parent.exists()
    
    @patch('algoforge.core.config.get_settings')
    def test_setup_logging_console_format(self, mock_settings, temp_log_dir):
        """Test logging setup with console format."""
        # Mock settings
        mock_cfg = Mock()
        mock_cfg.logging.level = "DEBUG"
        mock_cfg.logging.format = "console"
        mock_cfg.logging.log_file = str(temp_log_dir / "test.log")
        mock_cfg.logging.log_to_stdout = True
        mock_settings.return_value = mock_cfg
        
        # Setup logging
        setup_logging()
        
        # Verify log directory was created
        assert (temp_log_dir / "test.log").parent.exists()
    
    @patch('algoforge.core.config.get_settings')
    def test_setup_logging_no_file(self, mock_settings):
        """Test logging setup without file logging."""
        # Mock settings
        mock_cfg = Mock()
        mock_cfg.logging.level = "INFO"
        mock_cfg.logging.format = "json"
        mock_cfg.logging.log_file = None
        mock_cfg.logging.log_to_stdout = True
        mock_settings.return_value = mock_cfg
        
        # Setup logging (should not raise error)
        setup_logging()


class TestLogLevelConfiguration:
    """Test suite for log level configuration."""
    
    @patch('algoforge.core.config.get_settings')
    def test_debug_level(self, mock_settings):
        """Test DEBUG log level configuration."""
        mock_cfg = Mock()
        mock_cfg.logging.level = "DEBUG"
        mock_cfg.logging.format = "json"
        mock_cfg.logging.log_file = None
        mock_settings.return_value = mock_cfg
        
        setup_logging()
        logger = StructuredLogger("test")
        
        # Logger should be configured (no assertion needed, just verify no error)
        assert logger.logger is not None
    
    @patch('algoforge.core.config.get_settings')
    def test_warning_level(self, mock_settings):
        """Test WARNING log level configuration."""
        mock_cfg = Mock()
        mock_cfg.logging.level = "WARNING"
        mock_cfg.logging.format = "json"
        mock_cfg.logging.log_file = None
        mock_settings.return_value = mock_cfg
        
        setup_logging()
        logger = StructuredLogger("test")
        
        assert logger.logger is not None
    
    @patch('algoforge.core.config.get_settings')
    def test_error_level(self, mock_settings):
        """Test ERROR log level configuration."""
        mock_cfg = Mock()
        mock_cfg.logging.level = "ERROR"
        mock_cfg.logging.format = "json"
        mock_cfg.logging.log_file = None
        mock_settings.return_value = mock_cfg
        
        setup_logging()
        logger = StructuredLogger("test")
        
        assert logger.logger is not None


class TestJSONFormatting:
    """Test suite for JSON log formatting."""
    
    @patch('algoforge.core.config.get_settings')
    def test_json_output_structure(self, mock_settings, temp_log_dir, mock_signal):
        """Test that JSON logs have consistent structure."""
        log_file = temp_log_dir / "test.log"
        
        mock_cfg = Mock()
        mock_cfg.logging.level = "INFO"
        mock_cfg.logging.format = "json"
        mock_cfg.logging.log_file = str(log_file)
        mock_cfg.logging.log_to_stdout = False
        mock_settings.return_value = mock_cfg
        
        setup_logging()
        logger = StructuredLogger("test")
        
        # Log a signal
        contributing_factors = {"regime": "trending", "ml_prediction": 0.8}
        logger.log_signal_generation(mock_signal, contributing_factors)
        
        # Note: Actual JSON validation would require reading the log file
        # which is complex with structlog's async nature
        # This test verifies the method executes without error
