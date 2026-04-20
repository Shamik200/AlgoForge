# Phase 10: Risk Management Engine - Research

## Context
Building the complete Risk Management Engine. This layer acts as the absolute authority on capital preservation. It must calculate exact position sizes (via Fractional Kelly) while simultaneously applying a heavy gauntlet of hard-veto limits (account equity limits, portfolio correlation limits, liquidity constraints, and circuit breakers).

## Technical Findings

1. **Kelly Criterion Position Sizing:**
   - **Formula:** `Kelly % = W - ((1 - W) / R)`
     - `W`: Win Probability (e.g., 0.55).
     - `R`: Payoff Ratio (Average Win / Average Loss).
   - **Data Source:** A `TradeLedger` tracking the last N closed trades.
   - **Fallback:** If `len(ledger) < 30`, use a strict Fixed Fractional size (e.g. 1.0% of equity).
   - **Fractional Kelly:** Full Kelly is too aggressive. We will use a `Kelly Fraction` (e.g., 0.5 or "Half-Kelly") to scale the output down.

2. **Global Account Limits (`AccountState` Model):**
   - The engine expects an `AccountState` containing:
     - `current_equity`: float
     - `daily_pnl`: float
     - `weekly_pnl`: float
     - `peak_equity`: float
     - `consecutive_losses`: int
   - **Hard Vetoes:** 
     - `daily_pnl / current_equity <= -0.03` (Daily Loss Killswitch).
     - `(current_equity - peak_equity) / peak_equity <= -0.15` (Drawdown Killswitch).
     - `consecutive_losses >= 5` (Cooldown activated).

3. **Portfolio Concentration Limits:**
   - The engine receives a list of `ActivePosition` models.
   - **Sector Limit:** Cannot exceed 25% of total equity in a single sector.
   - **Directional Limit:** Cannot exceed 60% of total equity leaning long or short (i.e. net exposure).
   - **Max Positions:** Hard cap at 5-10 open trades.

4. **Correlation Limit:**
   - A `CorrelationMatrix` cache class will store pairwise Pearson correlations of daily returns.
   - If `Correlation(Candidate, Any Open Position) > 0.70`, the trade is vetoed.

5. **Per-Trade Micro Limits:**
   - **Max Position Size:** Capped at 10% of equity (regardless of what Kelly says).
   - **Liquidity Check:** Target shares must be `< 0.01 * SMA_Volume(20)`.
   - **Circuit Breaker:** If `(Current Close - Session Open) / Session Open <= -0.05`, halt all trading on that symbol.
   - **R:R Check:** Target / Stop Loss distance must yield at least `1:2` Reward-to-Risk.

## Implementation Path
- Create `src/algoforge/risk/`
- Implement Data Models (`AccountState`, `TradeLedger`, `ActivePosition`).
- Implement `sizing.py` for Kelly calculations and Fixed Fractional fallbacks.
- Implement `limits.py` for account, portfolio, and liquidity hard-veto checks.
- Implement `correlation.py` for the O(1) correlation matrix cache.
- Implement `engine.py` as the main orchestrator (`RiskEngine`).
- Unit tests focusing on Kelly math edge cases (e.g., negative R) and killswitch triggers.
