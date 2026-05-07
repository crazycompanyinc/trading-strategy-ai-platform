import React from 'react';
import { useStore } from '../stores/appStore';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid } from 'recharts';

const MetricCard = ({ label, value, suffix = '', color = 'neutral' }: { label: string; value: number | string; suffix?: string; color?: string }) => {
  const colorClass = color === 'positive' ? 'text-accent-green' : color === 'negative' ? 'text-accent-red' : 'text-accent-blue';
  return (
    <div className="metric-card">
      <div className="text-text-muted text-xs uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-xl font-bold ${colorClass}`}>{typeof value === 'number' ? value.toFixed(2) : value}{suffix}</div>
    </div>
  );
};

export const BacktestReport = () => {
  const { backtestResults } = useStore();
  if (!backtestResults) return (
    <div className="flex items-center justify-center h-full text-text-secondary">
      <div className="text-center">
        <div className="text-4xl mb-3">📊</div>
        <p>Run a backtest to see results here</p>
      </div>
    </div>
  );

  const { metrics, trades, equity_curve, symbol, timeframe } = backtestResults;

  // Prepare equity chart data
  const equityData = equity_curve.slice(0, 500).map((eq: number, i: number) => ({ bar: i, equity: eq }));

  // Prepare trades data
  const tradesData = (trades || []).slice(0, 50).map((t: any, i: number) => ({
    trade: i + 1,
    pnl: t.pnl,
    is_win: t.is_win,
  }));

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div>
        <h2 className="text-xl font-bold text-accent-blue mb-1">Backtest Report</h2>
        <p className="text-text-muted text-sm">{symbol} | {timeframe} | {metrics.total_trades} trades</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <MetricCard label="Total Return" value={metrics.total_return} suffix="%" color={metrics.total_return > 0 ? 'positive' : 'negative'} />
        <MetricCard label="Sharpe Ratio" value={metrics.sharpe_ratio} />
        <MetricCard label="Sortino Ratio" value={metrics.sortino_ratio} />
        <MetricCard label="Max Drawdown" value={metrics.max_drawdown} suffix="%" color="negative" />
        <MetricCard label="Win Rate" value={metrics.win_rate} suffix="%" />
        <MetricCard label="Profit Factor" value={metrics.profit_factor} color={metrics.profit_factor > 1 ? 'positive' : 'negative'} />
        <MetricCard label="Calmar Ratio" value={metrics.calmar_ratio} />
        <MetricCard label="Omega Ratio" value={metrics.omega_ratio} />
        <MetricCard label="Expectancy" value={metrics.expectancy} color={metrics.expectancy > 0 ? 'positive' : 'negative'} />
        <MetricCard label="Recovery Factor" value={metrics.recovery_factor} />
        <MetricCard label="Net Profit" value={metrics.net_profit} color={metrics.net_profit > 0 ? 'positive' : 'negative'} />
        <MetricCard label="Total Trades" value={metrics.total_trades} />
      </div>

      {/* Equity Curve */}
      <div className="bg-bg-secondary border border-border rounded-lg p-4">
        <h3 className="text-sm font-semibold text-accent-blue mb-3">Equity Curve</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={equityData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis dataKey="bar" stroke="#484f58" tick={{ fontSize: 10 }} />
            <YAxis stroke="#484f58" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8 }} />
            <Line type="monotone" dataKey="equity" stroke="#58a6ff" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Trade PnL */}
      <div className="bg-bg-secondary border border-border rounded-lg p-4">
        <h3 className="text-sm font-semibold text-accent-blue mb-3">Trade PnL</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={tradesData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis dataKey="trade" stroke="#484f58" tick={{ fontSize: 10 }} />
            <YAxis stroke="#484f58" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8 }} />
            <Bar dataKey="pnl" fill="#3fb950" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Trade Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Avg Win" value={metrics.avg_win_pct} suffix="%" color="positive" />
        <MetricCard label="Avg Loss" value={metrics.avg_loss_pct} suffix="%" color="negative" />
        <MetricCard label="Largest Win" value={metrics.largest_win} color="positive" />
        <MetricCard label="Largest Loss" value={metrics.largest_loss} color="negative" />
        <MetricCard label="Max Consec Wins" value={metrics.max_consecutive_wins} />
        <MetricCard label="Max Consec Losses" value={metrics.max_consecutive_losses} />
        <MetricCard label="Winning Trades" value={metrics.winning_trades} color="positive" />
        <MetricCard label="Losing Trades" value={metrics.losing_trades} color="negative" />
      </div>

      {/* Trades Table */}
      <div className="bg-bg-secondary border border-border rounded-lg overflow-hidden">
        <h3 className="text-sm font-semibold text-accent-blue p-4 pb-2">Trades Log</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted text-xs uppercase">
                <th className="p-2 text-left">#</th>
                <th className="p-2">Direction</th>
                <th className="p-2">Entry</th>
                <th className="p-2">Exit</th>
                <th className="p-2">PnL</th>
                <th className="p-2">Return %</th>
                <th className="p-2">Result</th>
              </tr>
            </thead>
            <tbody>
              {(trades || []).slice(0, 100).map((t: any, i: number) => (
                <tr key={i} className="border-b border-border/50 hover:bg-bg-tertiary">
                  <td className="p-2">{i + 1}</td>
                  <td className="p-2 text-center">{t.direction?.toUpperCase()}</td>
                  <td className="p-2 font-mono">{t.entry_price?.toFixed(5)}</td>
                  <td className="p-2 font-mono">{t.exit_price?.toFixed(5)}</td>
                  <td className={`p-2 font-mono ${t.pnl > 0 ? 'text-accent-green' : 'text-accent-red'}`}>{t.pnl?.toFixed(4)}</td>
                  <td className={`p-2 font-mono ${t.return_pct > 0 ? 'text-accent-green' : 'text-accent-red'}`}>{t.return_pct?.toFixed(4)}%</td>
                  <td className={`p-2 font-medium ${t.is_win ? 'text-accent-green' : 'text-accent-red'}`}>{t.is_win ? 'WIN' : 'LOSS'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
