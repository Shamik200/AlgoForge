'use client';

import { useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';

// Demo data for when WebSocket is not connected
const DEMO_STATE = {
  timestamp: new Date().toISOString(),
  system: {
    state: 'running',
    uptimeSeconds: 14400,
    totalPnl: 3247.50,
    totalPnlPct: 0.0325,
    totalTrades: 47,
    winRate: 0.5745,
    sharpeRatio: 1.82,
  },
  positions: [
    { symbol: 'AAPL', side: 'LONG', quantity: 150, entryPrice: 178.50, currentPrice: 182.30, unrealizedPnl: 570.00, unrealizedPnlPct: 0.0213 },
    { symbol: 'TSLA', side: 'SHORT', quantity: 50, entryPrice: 245.00, currentPrice: 238.70, unrealizedPnl: 315.00, unrealizedPnlPct: 0.0257 },
    { symbol: 'NVDA', side: 'LONG', quantity: 80, entryPrice: 890.00, currentPrice: 905.40, unrealizedPnl: 1232.00, unrealizedPnlPct: 0.0173 },
  ],
  signals: [
    { familyName: 'momentum', currentScore: 0.65, healthMultiplier: 1.0, status: 'healthy', convictionWeight: 0.22 },
    { familyName: 'mean_reversion', currentScore: -0.30, healthMultiplier: 1.0, status: 'healthy', convictionWeight: 0.18 },
    { familyName: 'breakout', currentScore: 0.45, healthMultiplier: 0.5, status: 'degraded', convictionWeight: 0.12 },
    { familyName: 'regime', currentScore: 0.80, healthMultiplier: 1.0, status: 'healthy', convictionWeight: 0.20 },
    { familyName: 'microstructure', currentScore: 0.15, healthMultiplier: 1.0, status: 'healthy', convictionWeight: 0.16 },
    { familyName: 'pairs', currentScore: 0.0, healthMultiplier: 0.0, status: 'paused', convictionWeight: 0.00 },
  ],
  regime: {
    bullProb: 0.72,
    bearProb: 0.08,
    sidewaysProb: 0.20,
    currentRegime: 'bull',
    barsInRegime: 156,
  },
  equityCurve: Array.from({ length: 50 }, (_, i) => ({
    timestamp: new Date(Date.now() - (50 - i) * 60000).toISOString(),
    value: 100000 + Math.random() * 5000 + i * 50,
  })),
};

export default function DashboardPage() {
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8080/ws';
  const { state: liveState, connected, sendCommand } = useWebSocket(wsUrl);
  const [killConfirm, setKillConfirm] = useState(false);
  const [killExecuted, setKillExecuted] = useState(false);

  // Use live state if connected, otherwise demo data
  const state = liveState || DEMO_STATE;

  const handleKillSwitch = () => {
    if (!killConfirm) {
      setKillConfirm(true);
      return;
    }
    sendCommand('FLATTEN_ALL');
    setKillExecuted(true);
    setKillConfirm(false);
  };

  const formatPnl = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
  };

  const formatPct = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${(value * 100).toFixed(2)}%`;
  };

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <h1>⚡ AlgoForge Terminal</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {connected ? '● LIVE' : '○ DEMO'}
          </span>
          <div className={`status-badge ${state.system.state}`}>
            <span className={`status-dot ${state.system.state}`} />
            {state.system.state}
          </div>
        </div>
      </header>

      {/* Panel 1: P&L + System Metrics */}
      <div className="card" id="panel-pnl">
        <div className="card-title">Portfolio P&L</div>
        <div className={`metric-value ${state.system.totalPnl >= 0 ? 'positive' : 'negative'}`}>
          {formatPnl(state.system.totalPnl)}
        </div>
        <div className="metric-label">{formatPct(state.system.totalPnlPct)} total return</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', marginTop: '20px' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 600 }}>{state.system.totalTrades}</div>
            <div className="metric-label">Trades</div>
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 600 }}>{(state.system.winRate * 100).toFixed(1)}%</div>
            <div className="metric-label">Win Rate</div>
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 600 }}>{state.system.sharpeRatio.toFixed(2)}</div>
            <div className="metric-label">Sharpe</div>
          </div>
        </div>
      </div>

      {/* Panel 2: Open Positions */}
      <div className="card" id="panel-positions" style={{ gridColumn: 'span 2' }}>
        <div className="card-title">Open Positions</div>
        <table className="positions-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Side</th>
              <th>Qty</th>
              <th>Entry</th>
              <th>Current</th>
              <th>Unrealized P&L</th>
            </tr>
          </thead>
          <tbody>
            {state.positions.map((pos: any, i: number) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{pos.symbol}</td>
                <td style={{ color: pos.side === 'LONG' ? 'var(--profit)' : 'var(--loss)' }}>{pos.side}</td>
                <td>{pos.quantity}</td>
                <td>${pos.entryPrice.toFixed(2)}</td>
                <td>${pos.currentPrice.toFixed(2)}</td>
                <td style={{ color: pos.unrealizedPnl >= 0 ? 'var(--profit)' : 'var(--loss)' }}>
                  {formatPnl(pos.unrealizedPnl)} ({formatPct(pos.unrealizedPnlPct)})
                </td>
              </tr>
            ))}
            {state.positions.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>No open positions</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Panel 3: Regime Probabilities */}
      <div className="card" id="panel-regime">
        <div className="card-title">HMM Regime Detection</div>
        {state.regime && (
          <>
            <div style={{ textAlign: 'center', marginBottom: '12px' }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: '1.2rem', fontWeight: 700,
                color: state.regime.currentRegime === 'bull' ? 'var(--profit)' : state.regime.currentRegime === 'bear' ? 'var(--loss)' : 'var(--warning)'
              }}>
                {state.regime.currentRegime.toUpperCase()}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '8px' }}>
                ({state.regime.barsInRegime} bars)
              </span>
            </div>
            <div className="regime-bars">
              <div className="regime-bar bull" style={{ height: `${state.regime.bullProb * 100}%` }}>
                <span className="regime-bar-label">Bull {(state.regime.bullProb * 100).toFixed(0)}%</span>
              </div>
              <div className="regime-bar bear" style={{ height: `${state.regime.bearProb * 100}%` }}>
                <span className="regime-bar-label">Bear {(state.regime.bearProb * 100).toFixed(0)}%</span>
              </div>
              <div className="regime-bar sideways" style={{ height: `${state.regime.sidewaysProb * 100}%` }}>
                <span className="regime-bar-label">Side {(state.regime.sidewaysProb * 100).toFixed(0)}%</span>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Panel 4: Signal Family Health */}
      <div className="card" id="panel-signals">
        <div className="card-title">Signal Family Health</div>
        {state.signals.map((sig: any, i: number) => (
          <div className="health-bar" key={i}>
            <span className="health-bar-label">{sig.familyName}</span>
            <div className="health-bar-track">
              <div
                className={`health-bar-fill ${sig.status}`}
                style={{ width: `${sig.healthMultiplier * 100}%` }}
              />
            </div>
            <span className="health-bar-value">{(sig.healthMultiplier * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>

      {/* Panel 5: Signal Conviction Weights */}
      <div className="card" id="panel-conviction">
        <div className="card-title">Conviction Weights</div>
        {state.signals.filter((s: any) => s.convictionWeight > 0).map((sig: any, i: number) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '0.85rem' }}>{sig.familyName}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '80px', height: '6px', background: 'hsla(220,20%,20%,0.5)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${sig.convictionWeight * 100}%`, height: '100%', background: 'var(--info)', borderRadius: '3px' }} />
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)', width: '40px', textAlign: 'right' }}>
                {(sig.convictionWeight * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Panel 6: Kill Switch */}
      <div className="card" id="panel-killswitch">
        <div className="card-title">System Control</div>
        <div className="kill-switch">
          <div style={{ textAlign: 'center', marginBottom: '8px' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Uptime: {formatUptime(state.system.uptimeSeconds)}
            </span>
          </div>
          <button
            id="kill-switch-btn"
            className={`kill-switch-btn ${killConfirm ? 'confirming' : ''} ${killExecuted ? 'executed' : ''}`}
            onClick={handleKillSwitch}
          >
            {killExecuted ? '✓ POSITIONS FLATTENED' : killConfirm ? '⚠ CONFIRM: FLATTEN ALL?' : '⛔ KILL SWITCH'}
          </button>
          {killConfirm && (
            <button
              style={{ background: 'none', border: '1px solid var(--text-muted)', color: 'var(--text-muted)', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.8rem' }}
              onClick={() => setKillConfirm(false)}
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
