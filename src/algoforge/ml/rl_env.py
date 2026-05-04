"""FinRL-inspired Reinforcement Learning Environment.

Provides a gym.Env interface for training RL agents (PPO, A2C, SAC)
on the trading data with realistic constraints.
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from algoforge.core.models import OHLCV


class TradingEnvironment(gym.Env):
    """Custom Trading Environment that follows gym interface."""
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(self, data: list[OHLCV], initial_capital: float = 100000.0, transaction_fee_pct: float = 0.001):
        super().__init__()
        
        self.data = data
        self.initial_capital = initial_capital
        self.transaction_fee_pct = transaction_fee_pct
        
        # Action space: [-1, 1] representing target position size (-100% short to 100% long)
        self.action_space = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)
        
        # Observation space: 
        # [cash, holdings, current_price, return_1, return_5, vol_5, momentum]
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(7,), dtype=np.float32)
        
        self.reset()
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        self.current_step = max(5, 0) # Start with enough lookback
        self.cash = self.initial_capital
        self.holdings = 0.0
        self.equity = self.initial_capital
        self.peak_equity = self.initial_capital
        
        return self._get_observation(), {}
        
    def _get_observation(self):
        if self.current_step >= len(self.data):
            return np.zeros(7, dtype=np.float32)
            
        current_price = self.data[self.current_step].close
        
        # Calculate basic features
        closes = [c.close for c in self.data[self.current_step-5:self.current_step+1]]
        ret_1 = (closes[-1] / closes[-2]) - 1 if len(closes) >= 2 else 0
        ret_5 = (closes[-1] / closes[0]) - 1 if len(closes) >= 6 else 0
        vol_5 = np.std(closes) if len(closes) >= 2 else 0
        mom = closes[-1] - np.mean(closes) if len(closes) > 0 else 0
        
        obs = np.array([
            self.cash / self.initial_capital,  # Normalized cash
            self.holdings * current_price / self.initial_capital, # Normalized holdings value
            current_price / self.data[0].close, # Normalized price
            ret_1,
            ret_5,
            vol_5 / current_price,
            mom / current_price
        ], dtype=np.float32)
        
        return obs
        
    def step(self, action):
        target_weight = np.clip(action[0], -1.0, 1.0)
        
        current_price = self.data[self.current_step].close
        current_holdings_value = self.holdings * current_price
        self.equity = self.cash + current_holdings_value
        
        # Calculate target holdings
        target_holdings_value = self.equity * target_weight
        target_holdings = target_holdings_value / current_price
        
        # Execute trade
        trade_amount = target_holdings - self.holdings
        trade_value = trade_amount * current_price
        fee = abs(trade_value) * self.transaction_fee_pct
        
        self.cash -= (trade_value + fee)
        self.holdings = target_holdings
        
        # Update step
        self.current_step += 1
        
        # Calculate new equity and reward
        if self.current_step < len(self.data):
            next_price = self.data[self.current_step].close
            next_holdings_value = self.holdings * next_price
            new_equity = self.cash + next_holdings_value
            
            # Reward is percentage change in equity
            reward = (new_equity - self.equity) / self.equity
            self.equity = new_equity
            self.peak_equity = max(self.peak_equity, self.equity)
            done = False
        else:
            reward = 0
            done = True
            
        # Add penalty for excessive drawdown
        drawdown = (self.peak_equity - self.equity) / self.peak_equity
        if drawdown > 0.20:
            reward -= 1.0  # Big penalty for blowing up
            done = True
            
        info = {
            "equity": self.equity,
            "drawdown": drawdown,
            "cash": self.cash,
            "holdings": self.holdings
        }
        
        return self._get_observation(), float(reward), done, False, info
