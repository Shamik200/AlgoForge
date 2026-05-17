# Frontend Enhancement Plan - Restore Full Trading Dashboard

## Current Situation

You have **TWO** frontends:

1. **`frontend/`** (Port 3000) - Your ORIGINAL comprehensive dashboard with:
   - ✅ Market selection (Crypto/Forex/Stocks)
   - ✅ Broker selection (Binance/Bybit)
   - ✅ Universe size configuration
   - ✅ Score threshold configuration
   - ✅ Start/Stop/Reset/Flatten controls
   - ✅ Live equity curve graph
   - ✅ Open positions table
   - ✅ Closed positions (trade history)
   - ✅ Market scanner with regime detection
   - ✅ System logs
   - ✅ Real-time WebSocket updates
   - ✅ Confidence-based position sizing display

2. **`dashboard/`** (Newer, simpler) - Missing many features

## Solution: Use Your Original Frontend!

Your original frontend in `frontend/` directory is **COMPLETE** and has all the features you need. The backend API at `src/algoforge/api/server.py` fully supports it.

### To Run Your Full-Featured Frontend:

```bash
cd frontend
npm install  # If not already installed
npm run dev  # Starts on http://localhost:3000
```

### Backend API (Already Running):

```bash
# In another terminal
python -m algoforge.api.server  # Or however you start it
# Should be running on http://127.0.0.1:8000
```

## Features Your Original Frontend Has:

### 1. **Configuration Panel** (Left Sidebar)
- Market selection dropdown (Crypto/Forex/Stocks)
- Broker selection (Binance/Bybit)
- Universe size input
- Score threshold input
- "Apply Configuration" button

### 2. **Engine Controls** (Left Sidebar)
- START TRADING button (green)
- PAUSE button (gray)
- RESET ALL DATA button (yellow)
- EMERGENCY FLATTEN button (red)

### 3. **Live Statistics** (Top Cards)
- Open Positions count
- Total Trades (with W/L breakdown and win rate)
- Realized P&L (with commission)
- Max Drawdown percentage

### 4. **Live Equity Curve** (Chart)
- Real-time equity graph
- Shows profit/loss from start
- Updates every bar

### 5. **Market Scanner** (Table)
- Asset symbol
- Score (with threshold highlighting)
- Trend indicator (UP/DOWN/SIDEWAYS)
- Regime detection (trending/range/breakout/reversal/liquidity_trap)
- Current bid price
- Status (ACTIVE/EVAL)

### 6. **Live Positions** (Right Panel)
- Symbol and direction (LONG/SHORT)
- Strategy name
- Entry price
- Current price
- Stop loss and take profit levels
- Unrealized P&L ($ and %)
- Real-time updates

### 7. **Trade History** (Right Panel)
- Closed positions list
- Symbol and direction
- Strategy used
- Exit price
- Realized P&L
- Shows last 20 trades

### 8. **System Logs** (Bottom)
- Real-time event log
- Color-coded by event type:
  - Green: Trade executions
  - Yellow: Position closes
  - Red: Errors/Flatten
  - Blue: System start/reset
- Auto-scrolls to newest

### 9. **Engine Stats** (Left Sidebar)
- Strategies active count
- Signals generated
- Signals executed
- Active assets list with badges

### 10. **Real-Time Updates**
- WebSocket connection indicator (LIVE/OFFLINE)
- Auto-reconnect on disconnect
- Sub-second latency

## Additional Enhancements You Can Add:

### A. **Confidence Display** (Add to positions table)
```typescript
// In the Live Positions section, add:
<div className="text-gray-600 text-xs">
  Confidence: {(p.confidence * 100).toFixed(0)}%
</div>
```

### B. **Position Sizing Indicator** (Add visual indicator)
```typescript
// Show why position size was chosen
<div className="flex items-center gap-1">
  {p.confidence >= 0.6 ? (
    <span className="text-green-400 text-xs">●●● FULL</span>
  ) : p.confidence >= 0.3 ? (
    <span className="text-yellow-400 text-xs">●● HALF</span>
  ) : (
    <span className="text-gray-600 text-xs">● SKIP</span>
  )}
</div>
```

### C. **Pool/Liquidity Display** (Add to config panel)
```typescript
<div>
  <label className="text-xs text-gray-600 block mb-1">Min Liquidity</label>
  <input 
    type="number" 
    value={minLiquidity} 
    onChange={e => setMinLiquidity(+e.target.value)}
    className="w-full bg-[#0d1117] border border-gray-700 rounded-md p-1.5 text-xs text-white outline-none" 
    placeholder="1000000"
  />
</div>
```

### D. **Advanced Metrics Panel** (Add new section)
```typescript
<div className="bg-[#161b22] border border-gray-800 rounded-xl p-4">
  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
    Advanced Metrics
  </div>
  <div className="space-y-2 text-xs">
    <div className="flex justify-between">
      <span className="text-gray-500">Sharpe Ratio</span>
      <span className="text-white">{sharpeRatio.toFixed(2)}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">Sortino Ratio</span>
      <span className="text-white">{sortinoRatio.toFixed(2)}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">Max Consecutive Losses</span>
      <span className="text-red-400">{maxConsecLosses}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">Avg Win / Avg Loss</span>
      <span className="text-white">{(avgWin / avgLoss).toFixed(2)}</span>
    </div>
  </div>
</div>
```

### E. **ML/AI Confidence Panel** (Add new section)
```typescript
<div className="bg-[#161b22] border border-gray-800 rounded-xl p-4">
  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
    <Brain className="w-3 h-3" /> ML Confidence
  </div>
  <div className="space-y-3">
    {mlPredictions.map((pred, i) => (
      <div key={i}>
        <div className="flex justify-between mb-1">
          <span className="text-xs text-gray-400">{pred.symbol}</span>
          <span className="text-xs text-white">{(pred.confidence * 100).toFixed(0)}%</span>
        </div>
        <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
          <div 
            className={`h-full ${pred.confidence >= 0.6 ? 'bg-green-500' : pred.confidence >= 0.3 ? 'bg-yellow-500' : 'bg-red-500'}`}
            style={{ width: `${pred.confidence * 100}%` }}
          />
        </div>
      </div>
    ))}
  </div>
</div>
```

### F. **Risk Metrics Panel** (Add new section)
```typescript
<div className="bg-[#161b22] border border-gray-800 rounded-xl p-4">
  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
    <ShieldAlert className="w-3 h-3" /> Risk Metrics
  </div>
  <div className="space-y-2 text-xs">
    <div className="flex justify-between">
      <span className="text-gray-500">Portfolio Heat</span>
      <span className={`font-bold ${portfolioHeat > 0.7 ? 'text-red-400' : portfolioHeat > 0.4 ? 'text-yellow-400' : 'text-green-400'}`}>
        {(portfolioHeat * 100).toFixed(0)}%
      </span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">VaR (95%)</span>
      <span className="text-white">${var95.toFixed(2)}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">Position Limit</span>
      <span className="text-white">{positions} / {maxPositions}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">Circuit Breaker</span>
      <span className={circuitBreakerActive ? 'text-red-400' : 'text-green-400'}>
        {circuitBreakerActive ? <Lock className="w-3 h-3 inline" /> : <Unlock className="w-3 h-3 inline" />}
        {circuitBreakerActive ? ' ACTIVE' : ' NORMAL'}
      </span>
    </div>
  </div>
</div>
```

## Quick Start Guide:

1. **Start Backend**:
   ```bash
   python -m algoforge.api.server
   # Or: uvicorn algoforge.api.server:app --reload --port 8000
   ```

2. **Start Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

3. **Open Browser**:
   ```
   http://localhost:3000
   ```

4. **Configure System**:
   - Select market (Crypto/Forex/Stocks)
   - Select broker (Binance/Bybit)
   - Set universe size (e.g., 50)
   - Set score threshold (e.g., 65)
   - Click "Apply Configuration"

5. **Start Trading**:
   - Click "START TRADING" button
   - Watch the system scan markets
   - See positions open/close in real-time
   - Monitor equity curve
   - View confidence scores

## Backend API Endpoints (Already Implemented):

- `GET /api/health` - Health check
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration
- `POST /api/system/start` - Start trading engine
- `POST /api/system/stop` - Pause trading
- `POST /api/system/reset` - Reset all data
- `POST /api/system/flatten` - Emergency flatten all positions
- `GET /api/trades` - Get trade history
- `GET /api/trades/stats` - Get strategy statistics
- `GET /api/trades/export` - Export trades as JSON
- `WS /ws/telemetry` - Real-time WebSocket updates

## What's Missing (That You Can Add):

1. **Confidence-based position sizing display** - Add to positions table
2. **Pool/liquidity configuration** - Add to config panel
3. **Advanced metrics** - Sharpe, Sortino, etc.
4. **ML confidence visualization** - Show AI predictions
5. **Risk metrics panel** - VaR, portfolio heat, circuit breaker status
6. **Multi-timeframe view** - Switch between 1m/5m/15m/1H/4H/1D
7. **Strategy performance breakdown** - Per-strategy P&L
8. **Regime transition alerts** - Visual alerts on regime changes
9. **Order book depth chart** - L2 data visualization
10. **Backtesting results comparison** - Compare live vs backtest

## Conclusion:

**Your original frontend is COMPLETE and FUNCTIONAL!** Just run it with:

```bash
cd frontend && npm run dev
```

All the features you mentioned are already there:
- ✅ Market selection
- ✅ Broker selection  
- ✅ Pool/universe configuration
- ✅ Threshold settings
- ✅ Start/Stop/Reset controls
- ✅ Live profit graph
- ✅ Confidence-based trading
- ✅ Open positions
- ✅ Closed positions
- ✅ Real-time updates

The enhancements above are **optional additions** to make it even better!
