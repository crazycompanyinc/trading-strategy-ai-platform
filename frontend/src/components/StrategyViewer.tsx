import React from 'react';
import { useStore } from '../stores/appStore';

export const StrategyViewer = () => {
  const { currentStrategy } = useStore();

  if (!currentStrategy) return (
    <div className="flex items-center justify-center h-full text-text-secondary">
      <div className="text-center">
        <div className="text-4xl mb-3">📋</div>
        <p>Describe a strategy to see its structure here</p>
      </div>
    </div>
  );

  const rm = currentStrategy.risk_management || {};

  return (
    <div className="h-full overflow-y-auto p-6 space-y-4">
      <div>
        <h2 className="text-xl font-bold text-accent-blue">{currentStrategy.name || 'Strategy'}</h2>
        <p className="text-text-muted text-sm">{currentStrategy.type} | {currentStrategy.instruments?.join(', ')} | {currentStrategy.timeframes?.join(', ')}</p>
      </div>

      {/* Indicators */}
      {currentStrategy.indicators?.length > 0 && (
        <div className="bg-bg-secondary border border-border rounded-lg p-4">
          <h3 className="text-sm font-semibold text-accent-blue mb-2">Indicators</h3>
          <div className="space-y-2">
            {currentStrategy.indicators.map((ind: any, i: number) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="text-accent-green font-mono">{ind.type?.toUpperCase()}</span>
                <span className="text-text-muted">{Object.entries(ind.parameters || {}).map(([k, v]) => `${k}=${v}`).join(', ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Entry Signals */}
      {currentStrategy.entry_signals?.length > 0 && (
        <div className="bg-bg-secondary border border-border rounded-lg p-4">
          <h3 className="text-sm font-semibold text-accent-green mb-2">Entry Signals</h3>
          {currentStrategy.entry_signals.map((sig: any, i: number) => (
            <div key={i} className="text-sm mb-2">
              <span className="text-accent-green font-medium">{sig.type?.toUpperCase()}</span>
              <span className="text-text-muted ml-2">Confidence: {(sig.confidence * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Risk Management */}
      <div className="bg-bg-secondary border border-border rounded-lg p-4">
        <h3 className="text-sm font-semibold text-accent-yellow mb-2">Risk Management</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          {rm.stop_loss && <div><span className="text-text-muted">Stop Loss:</span> <span className="text-accent-red">{rm.stop_loss}</span></div>}
          {rm.take_profit && <div><span className="text-text-muted">Take Profit:</span> <span className="text-accent-green">{rm.take_profit}</span></div>}
          {rm.trailing_stop && <div><span className="text-text-muted">Trailing Stop:</span> <span className="text-accent-yellow">{rm.trailing_stop}</span></div>}
          {rm.risk_per_trade && <div><span className="text-text-muted">Risk/Trade:</span> <span className="text-accent-blue">{rm.risk_per_trade}%</span></div>}
          {rm.max_position_size && <div><span className="text-text-muted">Position Size:</span> <span className="text-accent-blue">{rm.max_position_size} lots</span></div>}
          {rm.max_drawdown_limit && <div><span className="text-text-muted">Max Drawdown:</span> <span className="text-accent-red">{rm.max_drawdown_limit}%</span></div>}
        </div>
      </div>
    </div>
  );
};
