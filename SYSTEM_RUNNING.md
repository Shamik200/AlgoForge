# 🚀 AlgoForge Trading System - CURRENTLY RUNNING

## ✅ System Status: ACTIVE

### Backend API Server
- **URL**: http://127.0.0.1:8000
- **Status**: ✅ RUNNING
- **Health**: OK
- **Process ID**: Terminal 4

### Frontend Dashboard
- **URL**: http://localhost:3001
- **Status**: ✅ RUNNING
- **Process ID**: Terminal 3
- **Note**: Using port 3001 (port 3000 was in use)

## 📊 Initialized Components

✅ **28 Legacy Strategy Adapters**
- Momentum: 6 strategies
- Mean Reversion: 5 strategies
- Breakout: 6 strategies
- Structural: 7 strategies
- Microstructure: 4 strategies

✅ **7 Core Strategies**
- Trendline Pullback (primary)
- EMA Crossover
- Mean Reversion
- Breakout
- Liquidity Trap
- Reversal
- EMA Bounce

✅ **AI/ML Components**
- RL Agent (Reinforcement Learning)
- ML Pipeline Orchestrator
- FinGPT Client
- Confidence Aggregator

✅ **Risk Management**
- Dynamic SL/TP Manager
- Enhanced P&L Tracker
- Order Management System
- Risk Manager with circuit breakers

✅ **Data & Persistence**
- SQLite Database (data/algoforge.db)
- Order Management DB (data/oms_orders.db)
- RL Agent State (data/rl_agent_state.json)
- Trade History Persistence

## 🎮 How to Use the Dashboard

### 1. Open Dashboard
```
http://localhost:3001
```
Browser should have opened automatically.

### 2. Configure System (Left Sidebar)

**Market Selection:**
- Crypto (default)
- Forex
- Stocks

**Broker:**
- Binance (default)
- Bybit

**Universe Size:**
- Number of assets to scan (e.g., 50)
- Higher = more opportunities, slower

**Score Threshold:**
- Minimum score to trade (e.g., 65)
- Higher = fewer but higher quality trades

**Click "Apply Configuration"**

### 3. Start Trading

**Click "START TRADING"** (green button)

The system will:
1. Connect to exchange WebSocket
2. Scan universe for opportunities
3. Calculate scores and regimes
4. Execute trades based on confidence
5. Update dashboard in real-time

### 4. Monitor Performance

**Dashboard shows:**
- Live equity curve
- Open positions with P&L
- Closed positions (trade history)
- Market scanner with scores
- System logs
- Engine statistics

### 5. Control System

**PAUSE** - Stop trading, keep positions
**RESET** - Clear all data, start fresh
**FLATTEN** - Emergency close all positions

## 📈 Dashboard Features

### Top Stats Cards
- **Open Positions**: Number of active trades
- **Total Trades**: All trades executed (W/L breakdown)
- **Realized P&L**: Total profit/loss with commission
- **Max Drawdown**: Worst peak-to-trough decline

### Live Equity Curve
- Real-time portfolio value graph
- Shows profit/loss from $100,000 start
- Updates every bar

### Market Scanner
- **Symbol**: Asset name
- **Score**: Composite score (0-100)
- **Trend**: UP ↗ / DOWN ↘ / SIDEWAYS →
- **Regime**: Market state (trending/range/breakout/reversal/liquidity_trap)
- **Bid**: Current bid price
- **Status**: ACTIVE (trading) / EVAL (evaluating)

### Live Positions
- Symbol and direction (LONG/SHORT)
- Entry price and current price
- Stop loss and take profit levels
- Unrealized P&L ($ and %)
- Strategy that opened the trade

### Trade History
- Closed positions
- Realized P&L
- Strategy used
- Exit reason

### System Logs
- Real-time event log
- Color-coded by type:
  - 🟢 Green: Trade executions
  - 🟡 Yellow: Position closes
  - 🔴 Red: Errors, flatten events
  - 🔵 Blue: System start/reset

## 🔧 API Endpoints

### REST API (http://127.0.0.1:8000)

**Health Check:**
```
GET /api/health
```

**Configuration:**
```
GET /api/config
POST /api/config
```

**System Control:**
```
POST /api/system/start
POST /api/system/stop
POST /api/system/reset
POST /api/system/flatten
```

**Trade Data:**
```
GET /api/trades
GET /api/trades/stats
GET /api/trades/export
```

**WebSocket:**
```
WS /ws/telemetry
```

## 🛑 How to Stop the System

### Option 1: Use Kiro Commands
```
# Stop frontend
control_pwsh_process action="stop" terminalId="3"

# Stop backend
control_pwsh_process action="stop" terminalId="4"
```

### Option 2: Close Terminal Windows
- Close the terminal windows running the processes

### Option 3: Kill Processes
```powershell
# Find processes
Get-Process | Where-Object {$_.ProcessName -like "*node*" -or $_.ProcessName -like "*python*"}

# Kill specific process
Stop-Process -Id <PID>
```

## 📝 Configuration Files

**Main Config:**
```
config/settings.yaml
```

**Environment Variables:**
```
.env
```

**Market Configs:**
```
config/markets/crypto.yaml
config/markets/forex.yaml
config/markets/stocks.yaml
```

## 🔍 Monitoring & Logs

**Application Logs:**
```
logs/algoforge.log
logs/algoforge.log.2026-05-09
```

**Database:**
```
data/algoforge.db
data/oms_orders.db
```

**RL Agent State:**
```
data/rl_agent_state.json
```

## ⚠️ Important Notes

1. **Paper Trading Only** - This is a simulation, no real money
2. **Data Persistence** - Trades saved to SQLite database
3. **State Recovery** - System restores state on restart
4. **Risk Management** - Built-in position limits and circuit breakers
5. **Multi-Strategy** - 28 legacy + 7 core strategies running simultaneously

## 🎯 Current Configuration

**Market**: Stocks (US)
**Timeframe**: Intraday (1m base)
**Capital**: $100,000 (paper)
**Currency**: USD
**Max Risk per Trade**: 2%
**Max Position Size**: 10%
**Max Open Positions**: 5
**Max Daily Loss**: 5%
**Max Drawdown**: 20%

## 🚀 Performance Expectations

**Latency:**
- WebSocket updates: < 100ms
- UI refresh: 60 FPS
- Chart updates: Real-time
- API calls: < 50ms

**Resource Usage:**
- CPU: Moderate (multi-threaded)
- RAM: ~500MB-1GB
- Network: Continuous WebSocket connection
- Disk: Minimal (SQLite writes)

## 📚 Additional Resources

**Documentation:**
- `README.md` - Project overview
- `DASHBOARD_QUICK_START.md` - Dashboard guide
- `DASHBOARD_SUMMARY.md` - Feature comparison
- `FRONTEND_ENHANCEMENT_PLAN.md` - Enhancement ideas
- `TASK_PROGRESS_SUMMARY.md` - Implementation status

**Examples:**
- `examples/rl_agent_demo.py` - RL Agent demonstration
- `examples/confidence_aggregator_example.py` - Confidence scoring
- `examples/pattern_recognizer_example.py` - Pattern recognition

## 🆘 Troubleshooting

### Dashboard shows "OFFLINE"
- Backend not running
- Check: http://127.0.0.1:8000/api/health

### No data in scanner
- System not started
- Click "START TRADING" button

### Config not saving
- System is running
- Click "PAUSE" first, then configure

### WebSocket disconnected
- Backend crashed
- Check backend terminal for errors
- Restart backend

### Port already in use
- Frontend: Using port 3001 instead of 3000
- Backend: Check if port 8000 is free
- Use `netstat -ano | findstr :8000` to check

## ✅ System Health Checklist

- [x] Backend API running on port 8000
- [x] Frontend dashboard running on port 3001
- [x] Configuration validated successfully
- [x] 28 legacy strategies initialized
- [x] RL Agent initialized
- [x] Orchestrator initialized
- [x] Persistence store initialized
- [x] OMS initialized
- [x] Browser opened to dashboard

---

**System is ready for trading! Open http://localhost:3001 and click START TRADING!** 🚀📈💰
