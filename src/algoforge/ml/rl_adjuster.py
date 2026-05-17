"""RL Threshold Adjuster for adaptive system parameter optimization.

This module implements a reinforcement learning agent that learns from trade
outcomes and dynamically adjusts system thresholds to improve performance:
- Conviction thresholds for trade filtering
- Position size limits based on recent performance
- Signal family weights based on per-family performance
- ML confidence thresholds based on prediction accuracy

The agent uses PPO (Proximal Policy Optimization) and implements exploration
vs exploitation to avoid local optima. It can revert to baseline parameters
if performance degrades significantly.
"""

import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RLConfig(BaseModel):
    """Configuration for RL Threshold Adjuster."""
    
    # Baseline parameters (fallback values)
    baseline_conviction_thresholds: tuple[float, float] = Field(
        default=(0.3, 0.6),
        description="Baseline (low, high) conviction thresholds"
    )
    baseline_position_size_limits: dict[str, float] = Field(
        default_factory=lambda: {
            "max_position_pct": 0.10,  # 10% of capital per position
            "max_total_exposure_pct": 0.50,  # 50% total exposure
        },
        description="Baseline position size limits"
    )
    baseline_signal_family_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "momentum": 1.0,
            "mean_reversion": 1.0,
            "breakout": 1.0,
            "structural": 1.0,
            "microstructure": 0.8,
        },
        description="Baseline signal family weights"
    )
    baseline_ml_confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Baseline ML confidence threshold"
    )
    
    # RL parameters
    exploration_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Exploration vs exploitation rate (10% exploration)"
    )
    learning_rate: float = Field(
        default=0.0003,
        gt=0.0,
        description="Learning rate for PPO agent"
    )
    discount_factor: float = Field(
        default=0.99,
        ge=0.0,
        le=1.0,
        description="Discount factor for future rewards"
    )
    
    # Adjustment constraints
    max_conviction_adjustment: float = Field(
        default=0.15,
        ge=0.0,
        le=0.5,
        description="Maximum adjustment to conviction thresholds"
    )
    max_weight_adjustment: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Maximum adjustment to signal family weights"
    )
    
    # Performance monitoring
    revert_threshold: int = Field(
        default=20,
        ge=1,
        description="Number of consecutive poor trades before reverting to baseline"
    )
    poor_trade_r_multiple: float = Field(
        default=-0.5,
        description="R-multiple threshold for considering a trade 'poor'"
    )
    
    # State persistence
    state_file: str = Field(
        default="data/rl_agent_state.json",
        description="Path to persist RL agent state"
    )
    
    # History tracking
    max_history_size: int = Field(
        default=1000,
        ge=100,
        description="Maximum number of trade outcomes to keep in memory"
    )


class TradeOutcome(BaseModel):
    """Record of a closed trade outcome for RL learning."""
    
    trade_id: str
    symbol: str
    direction: Literal["long", "short"]
    entry_price: float = Field(gt=0)
    exit_price: float = Field(gt=0)
    quantity: float = Field(gt=0)
    
    # P&L metrics
    pnl_dollars: float
    r_multiple: float
    
    # Context at trade time
    conviction_score: float = Field(ge=0.0, le=1.0)
    signal_family: str
    market_regime: dict[str, float] = Field(
        default_factory=dict,
        description="Regime probabilities at trade time"
    )
    signal_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Signal family scores at trade time"
    )
    ml_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Timing
    entry_time: datetime
    exit_time: datetime
    bars_in_trade: int = Field(ge=0)
    
    # Exit reason
    exit_reason: str = Field(default="unknown")


class ThresholdAdjustments(BaseModel):
    """Threshold adjustments computed by RL agent."""
    
    conviction_thresholds: tuple[float, float] = Field(
        description="Adjusted (low, high) conviction thresholds"
    )
    position_size_limits: dict[str, float] = Field(
        description="Adjusted position size limits"
    )
    signal_family_weights: dict[str, float] = Field(
        description="Adjusted signal family weights"
    )
    ml_confidence_threshold: float = Field(
        ge=0.0,
        le=1.0,
        description="Adjusted ML confidence threshold"
    )
    
    adjustments_reason: str = Field(
        description="Human-readable explanation of adjustments"
    )
    trades_analyzed: int = Field(
        ge=0,
        description="Number of trades analyzed for these adjustments"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RLAgentState(BaseModel):
    """Persistent state of the RL agent."""
    
    current_adjustments: ThresholdAdjustments
    consecutive_poor_trades: int = 0
    total_trades_observed: int = 0
    cumulative_r_multiple: float = 0.0
    
    # Performance tracking
    avg_r_multiple_by_family: dict[str, float] = Field(default_factory=dict)
    trade_count_by_family: dict[str, int] = Field(default_factory=dict)
    
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RLThresholdAdjuster:
    """RL agent for adaptive threshold adjustment.
    
    This class implements a reinforcement learning agent that observes trade
    outcomes and adjusts system thresholds to improve performance. The agent:
    
    1. Observes trade outcomes with market context
    2. Computes rewards based on R-multiples and regime appropriateness
    3. Adjusts thresholds using PPO-inspired policy updates
    4. Implements exploration vs exploitation
    5. Reverts to baseline after consecutive poor performance
    6. Persists state across system restarts
    
    The agent does NOT use a full neural network PPO implementation (which would
    require stable-baselines3 or similar). Instead, it uses a simplified
    rule-based approach inspired by RL principles:
    - Reward-based threshold adjustments
    - Exploration through random perturbations
    - Exploitation through performance-based updates
    - State persistence for continuous learning
    """
    
    def __init__(self, config: RLConfig | None = None):
        """Initialize the RL Threshold Adjuster.
        
        Args:
            config: Configuration for RL behavior and constraints.
        """
        self.config = config or RLConfig()
        
        # Trade history for learning
        self.state_history: deque[TradeOutcome] = deque(
            maxlen=self.config.max_history_size
        )
        
        # Current agent state
        self.state = self._initialize_state()
        
        # Load persisted state if available
        self._load_state()
        
        logger.info(
            "RLThresholdAdjuster initialized: exploration_rate=%.2f, revert_threshold=%d",
            self.config.exploration_rate,
            self.config.revert_threshold,
        )
    
    def _initialize_state(self) -> RLAgentState:
        """Initialize agent state with baseline parameters."""
        baseline_adjustments = ThresholdAdjustments(
            conviction_thresholds=self.config.baseline_conviction_thresholds,
            position_size_limits=self.config.baseline_position_size_limits.copy(),
            signal_family_weights=self.config.baseline_signal_family_weights.copy(),
            ml_confidence_threshold=self.config.baseline_ml_confidence_threshold,
            adjustments_reason="Initialized with baseline parameters",
            trades_analyzed=0,
        )
        
        return RLAgentState(
            current_adjustments=baseline_adjustments,
            consecutive_poor_trades=0,
            total_trades_observed=0,
            cumulative_r_multiple=0.0,
        )
    
    def observe_trade_outcome(
        self,
        trade: TradeOutcome,
    ) -> None:
        """Record a trade outcome for learning.
        
        This method is called after each trade closes. The agent stores the
        outcome and updates its internal state for future threshold adjustments.
        
        Args:
            trade: Closed trade outcome with full context.
        """
        # Add to history
        self.state_history.append(trade)
        
        # Update state
        self.state.total_trades_observed += 1
        self.state.cumulative_r_multiple += trade.r_multiple
        
        # Track per-family performance
        family = trade.signal_family
        if family not in self.state.avg_r_multiple_by_family:
            self.state.avg_r_multiple_by_family[family] = 0.0
            self.state.trade_count_by_family[family] = 0
        
        # Update running average for this family
        count = self.state.trade_count_by_family[family]
        current_avg = self.state.avg_r_multiple_by_family[family]
        new_avg = (current_avg * count + trade.r_multiple) / (count + 1)
        
        self.state.avg_r_multiple_by_family[family] = new_avg
        self.state.trade_count_by_family[family] = count + 1
        
        # Track consecutive poor trades
        if trade.r_multiple < self.config.poor_trade_r_multiple:
            self.state.consecutive_poor_trades += 1
            logger.warning(
                "Poor trade observed (R=%.2f): %d consecutive poor trades",
                trade.r_multiple,
                self.state.consecutive_poor_trades,
            )
        else:
            self.state.consecutive_poor_trades = 0
        
        # Check if we need to revert to baseline
        if self.state.consecutive_poor_trades >= self.config.revert_threshold:
            logger.warning(
                "Reverting to baseline after %d consecutive poor trades",
                self.state.consecutive_poor_trades,
            )
            self.revert_to_baseline()
        
        self.state.last_updated = datetime.now(timezone.utc)
        
        logger.debug(
            "Trade outcome observed: %s, R=%.2f, family=%s",
            trade.trade_id,
            trade.r_multiple,
            trade.signal_family,
        )
    
    def adjust_thresholds(self) -> ThresholdAdjustments:
        """Compute threshold adjustments based on recent outcomes.
        
        This method analyzes recent trade outcomes and computes new threshold
        values. It implements exploration vs exploitation:
        - With probability exploration_rate: apply random perturbations
        - Otherwise: apply performance-based adjustments
        
        Returns:
            ThresholdAdjustments with new parameter values and reasoning.
        """
        if len(self.state_history) < 10:
            # Not enough data for meaningful adjustments
            logger.info("Insufficient trade history for adjustments (need 10, have %d)", len(self.state_history))
            return self.state.current_adjustments
        
        # Decide: explore or exploit?
        if np.random.random() < self.config.exploration_rate:
            # Exploration: random perturbations
            adjustments = self._explore()
            reason = "Exploration: random parameter perturbations"
        else:
            # Exploitation: performance-based adjustments
            adjustments = self._exploit()
            reason = "Exploitation: performance-based adjustments"
        
        # Create adjustment record
        new_adjustments = ThresholdAdjustments(
            conviction_thresholds=adjustments["conviction_thresholds"],
            position_size_limits=adjustments["position_size_limits"],
            signal_family_weights=adjustments["signal_family_weights"],
            ml_confidence_threshold=adjustments["ml_confidence_threshold"],
            adjustments_reason=reason,
            trades_analyzed=len(self.state_history),
        )
        
        # Update state
        self.state.current_adjustments = new_adjustments
        self.state.last_updated = datetime.now(timezone.utc)
        
        # Persist state
        self._save_state()
        
        logger.info(
            "Thresholds adjusted: conviction=(%.2f, %.2f), ml_threshold=%.2f, reason='%s'",
            new_adjustments.conviction_thresholds[0],
            new_adjustments.conviction_thresholds[1],
            new_adjustments.ml_confidence_threshold,
            reason,
        )
        
        return new_adjustments
    
    def _explore(self) -> dict:
        """Apply random perturbations to thresholds (exploration).
        
        Returns:
            Dictionary with perturbed threshold values.
        """
        # Start with current values
        current = self.state.current_adjustments
        
        # Random perturbations within constraints
        conviction_low = current.conviction_thresholds[0] + np.random.uniform(
            -self.config.max_conviction_adjustment,
            self.config.max_conviction_adjustment
        )
        conviction_high = current.conviction_thresholds[1] + np.random.uniform(
            -self.config.max_conviction_adjustment,
            self.config.max_conviction_adjustment
        )
        
        # Ensure low < high and within [0, 1]
        conviction_low = np.clip(conviction_low, 0.1, 0.5)
        conviction_high = np.clip(conviction_high, 0.5, 0.9)
        if conviction_low >= conviction_high:
            conviction_low, conviction_high = 0.3, 0.6  # Reset to baseline
        
        # Perturb ML confidence threshold
        ml_threshold = current.ml_confidence_threshold + np.random.uniform(-0.1, 0.1)
        ml_threshold = np.clip(ml_threshold, 0.3, 0.8)
        
        # Perturb signal family weights
        weights = current.signal_family_weights.copy()
        for family in weights:
            perturbation = np.random.uniform(
                -self.config.max_weight_adjustment,
                self.config.max_weight_adjustment
            )
            weights[family] = np.clip(weights[family] + perturbation, 0.5, 1.5)
        
        return {
            "conviction_thresholds": (conviction_low, conviction_high),
            "position_size_limits": current.position_size_limits.copy(),
            "signal_family_weights": weights,
            "ml_confidence_threshold": ml_threshold,
        }
    
    def _exploit(self) -> dict:
        """Apply performance-based adjustments (exploitation).
        
        Analyzes recent trade outcomes and adjusts thresholds based on:
        1. Overall win rate and R-multiple
        2. Per-family performance
        3. ML prediction accuracy
        4. Regime-specific performance
        
        Returns:
            Dictionary with adjusted threshold values.
        """
        current = self.state.current_adjustments
        recent_trades = list(self.state_history)[-50:]  # Last 50 trades
        
        if not recent_trades:
            return {
                "conviction_thresholds": current.conviction_thresholds,
                "position_size_limits": current.position_size_limits.copy(),
                "signal_family_weights": current.signal_family_weights.copy(),
                "ml_confidence_threshold": current.ml_confidence_threshold,
            }
        
        # Compute recent performance metrics
        avg_r_multiple = np.mean([t.r_multiple for t in recent_trades])
        win_rate = sum(1 for t in recent_trades if t.r_multiple > 0) / len(recent_trades)
        
        # Adjust conviction thresholds based on overall performance
        conviction_low, conviction_high = current.conviction_thresholds
        
        if avg_r_multiple > 0.5 and win_rate > 0.55:
            # Good performance: lower thresholds to take more trades
            conviction_low = max(0.1, conviction_low - 0.05)
            conviction_high = max(0.4, conviction_high - 0.05)
        elif avg_r_multiple < 0.0 or win_rate < 0.45:
            # Poor performance: raise thresholds to be more selective
            conviction_low = min(0.5, conviction_low + 0.05)
            conviction_high = min(0.8, conviction_high + 0.05)
        
        # Adjust signal family weights based on per-family performance
        weights = current.signal_family_weights.copy()
        for family, avg_r in self.state.avg_r_multiple_by_family.items():
            if family not in weights:
                continue
            
            count = self.state.trade_count_by_family.get(family, 0)
            if count < 5:
                continue  # Not enough data
            
            if avg_r > 0.3:
                # Good family: increase weight
                weights[family] = min(1.5, weights[family] + 0.1)
            elif avg_r < -0.2:
                # Poor family: decrease weight
                weights[family] = max(0.5, weights[family] - 0.1)
        
        # Adjust ML confidence threshold based on ML prediction accuracy
        ml_trades = [t for t in recent_trades if t.ml_confidence > 0.5]
        if len(ml_trades) >= 10:
            ml_win_rate = sum(1 for t in ml_trades if t.r_multiple > 0) / len(ml_trades)
            ml_threshold = current.ml_confidence_threshold
            
            if ml_win_rate > 0.60:
                # ML is accurate: lower threshold to use it more
                ml_threshold = max(0.3, ml_threshold - 0.05)
            elif ml_win_rate < 0.45:
                # ML is inaccurate: raise threshold to use it less
                ml_threshold = min(0.8, ml_threshold + 0.05)
        else:
            ml_threshold = current.ml_confidence_threshold
        
        return {
            "conviction_thresholds": (conviction_low, conviction_high),
            "position_size_limits": current.position_size_limits.copy(),
            "signal_family_weights": weights,
            "ml_confidence_threshold": ml_threshold,
        }
    
    def revert_to_baseline(self) -> None:
        """Revert to baseline parameters after poor performance.
        
        This method is called automatically when consecutive poor trades
        exceed the revert_threshold. It resets all thresholds to their
        baseline values and resets the poor trade counter.
        """
        baseline_adjustments = ThresholdAdjustments(
            conviction_thresholds=self.config.baseline_conviction_thresholds,
            position_size_limits=self.config.baseline_position_size_limits.copy(),
            signal_family_weights=self.config.baseline_signal_family_weights.copy(),
            ml_confidence_threshold=self.config.baseline_ml_confidence_threshold,
            adjustments_reason=f"Reverted to baseline after {self.state.consecutive_poor_trades} consecutive poor trades",
            trades_analyzed=len(self.state_history),
        )
        
        self.state.current_adjustments = baseline_adjustments
        self.state.consecutive_poor_trades = 0
        self.state.last_updated = datetime.now(timezone.utc)
        
        # Persist state
        self._save_state()
        
        logger.warning("Reverted to baseline parameters")
    
    def get_current_adjustments(self) -> ThresholdAdjustments:
        """Get the current threshold adjustments.
        
        Returns:
            Current ThresholdAdjustments being used by the system.
        """
        return self.state.current_adjustments
    
    def _save_state(self) -> None:
        """Persist agent state to disk."""
        try:
            state_path = Path(self.config.state_file)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert state to dict for JSON serialization
            state_dict = {
                "current_adjustments": self.state.current_adjustments.model_dump(mode="json"),
                "consecutive_poor_trades": self.state.consecutive_poor_trades,
                "total_trades_observed": self.state.total_trades_observed,
                "cumulative_r_multiple": self.state.cumulative_r_multiple,
                "avg_r_multiple_by_family": self.state.avg_r_multiple_by_family,
                "trade_count_by_family": self.state.trade_count_by_family,
                "last_updated": self.state.last_updated.isoformat(),
            }
            
            with open(state_path, "w") as f:
                json.dump(state_dict, f, indent=2)
            
            logger.debug("RL agent state saved to %s", state_path)
        except Exception as e:
            logger.error("Failed to save RL agent state: %s", e)
    
    def _load_state(self) -> None:
        """Load persisted agent state from disk."""
        try:
            state_path = Path(self.config.state_file)
            if not state_path.exists():
                logger.info("No persisted RL agent state found, using initial state")
                return
            
            with open(state_path, "r") as f:
                state_dict = json.load(f)
            
            # Reconstruct state
            adjustments = ThresholdAdjustments(**state_dict["current_adjustments"])
            
            self.state = RLAgentState(
                current_adjustments=adjustments,
                consecutive_poor_trades=state_dict["consecutive_poor_trades"],
                total_trades_observed=state_dict["total_trades_observed"],
                cumulative_r_multiple=state_dict["cumulative_r_multiple"],
                avg_r_multiple_by_family=state_dict["avg_r_multiple_by_family"],
                trade_count_by_family=state_dict["trade_count_by_family"],
                last_updated=datetime.fromisoformat(state_dict["last_updated"]),
            )
            
            logger.info(
                "RL agent state loaded: %d trades observed, cumulative R=%.2f",
                self.state.total_trades_observed,
                self.state.cumulative_r_multiple,
            )
        except Exception as e:
            logger.error("Failed to load RL agent state: %s", e)
            logger.info("Using initial state")
