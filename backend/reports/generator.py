"""
Report Generator - Creates comprehensive backtest reports.
Generates HTML reports with charts, metrics, and analysis.
"""
from __future__ import annotations
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional


class ReportGenerator:
    """
    Generates HTML reports with embedded charts and metrics
    from backtest results.
    """

    def __init__(self, output_dir: str = "/tmp/reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, backtest_results: dict) -> str:
        """
        Generate an HTML report from backtest results.
        
        Returns path to generated report file.
        """
        metrics = backtest_results.get("metrics", {})
        trades = backtest_results.get("trades", [])
        equity_curve = backtest_results.get("equity_curve", [])

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_report_{timestamp}.html"
        filepath = os.path.join(self.output_dir, filename)

        html = self._generate_html(metrics, trades, equity_curve, backtest_results)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        return filepath

    def _generate_html(
        self,
        metrics: dict,
        trades: list,
        equity_curve: list,
        raw_results: dict,
    ) -> str:
        """Generate complete HTML report."""

        # Equity curve data for chart
        equity_json = json.dumps(equity_curve[:500])  # Limit for performance
        
        # Trades by month
        monthly = self._monthly_returns(trades)
        monthly_json = json.dumps(monthly)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Backtest Report - {raw_results.get('symbol', 'Unknown')}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0d1117; color: #c9d1d9; line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
  h1 {{ color: #58a6ff; margin-bottom: 10px; font-size: 28px; }}
  h2 {{ color: #79c0ff; margin: 20px 0 10px; font-size: 20px; border-bottom: 1px solid #30363d; padding-bottom: 8px; }}
  .subtitle {{ color: #8b949e; margin-bottom: 30px; }}
  
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
  .metric-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; }}
  .metric-card .label {{ color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }}
  .metric-card .value {{ font-size: 24px; font-weight: bold; }}
  .positive {{ color: #3fb950; }}
  .negative {{ color: #f85149; }}
  .neutral {{ color: #58a6ff; }}
  
  .chart-container {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin: 20px 0; }}
  canvas {{ width: 100% !important; height: 300px !important; }}
  
  table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
  th, td {{ padding: 10px 12px; text-align: right; border-bottom: 1px solid #21262d; }}
  th {{ background: #161b22; color: #79c0ff; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }}
  td:first-child, th:first-child {{ text-align: left; }}
  tr:hover {{ background: #161b22; }}
  
  .section {{ margin: 30px 0; }}
  .footer {{ text-align: center; color: #484f58; margin-top: 40px; padding: 20px; border-top: 1px solid #21262d; font-size: 12px; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
<div class="container">
  <h1>Backtest Report</h1>
  <p class="subtitle">
    {raw_results.get('symbol', 'EURUSD')} | {raw_results.get('timeframe', 'H1')} | 
    {raw_results.get('start_date', '')} → {raw_results.get('end_date', '')} | 
    Initial Capital: ${raw_results.get('initial_capital', 10000):,.2f}
  </p>

  <h2>Performance Summary</h2>
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="label">Total Return</div>
      <div class="value {'positive' if metrics.get('total_return', 0) > 0 else 'negative'}">{metrics.get('total_return', 0):.2f}%</div>
    </div>
    <div class="metric-card">
      <div class="label">Sharpe Ratio</div>
      <div class="value neutral">{metrics.get('sharpe_ratio', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Sortino Ratio</div>
      <div class="value neutral">{metrics.get('sortino_ratio', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Max Drawdown</div>
      <div class="value negative">{metrics.get('max_drawdown', 0):.2f}%</div>
    </div>
    <div class="metric-card">
      <div class="label">Win Rate</div>
      <div class="value neutral">{metrics.get('win_rate', 0):.2f}%</div>
    </div>
    <div class="metric-card">
      <div class="label">Profit Factor</div>
      <div class="value {'positive' if metrics.get('profit_factor', 0) > 1 else 'negative'}">{metrics.get('profit_factor', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Calmar Ratio</div>
      <div class="value neutral">{metrics.get('calmar_ratio', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Omega Ratio</div>
      <div class="value neutral">{metrics.get('omega_ratio', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Total Trades</div>
      <div class="value neutral">{metrics.get('total_trades', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="label">Expectancy</div>
      <div class="value {'positive' if metrics.get('expectancy', 0) > 0 else 'negative'}">{metrics.get('expectancy', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Recovery Factor</div>
      <div class="value neutral">{metrics.get('recovery_factor', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Net Profit</div>
      <div class="value {'positive' if metrics.get('net_profit', 0) > 0 else 'negative'}">{metrics.get('net_profit', 0):,.4f}</div>
    </div>
  </div>

  <div class="chart-container">
    <h2>Equity Curve</h2>
    <canvas id="equityChart"></canvas>
  </div>

  <div class="chart-container">
    <h2>Monthly Returns</h2>
    <canvas id="monthlyChart"></canvas>
  </div>

  <h2>Trade Statistics</h2>
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="label">Avg Win</div>
      <div class="value positive">{metrics.get('avg_win_pct', 0):.4f}%</div>
    </div>
    <div class="metric-card">
      <div class="label">Avg Loss</div>
      <div class="value negative">{metrics.get('avg_loss_pct', 0):.4f}%</div>
    </div>
    <div class="metric-card">
      <div class="label">Largest Win</div>
      <div class="value positive">{metrics.get('largest_win', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Largest Loss</div>
      <div class="value negative">{metrics.get('largest_loss', 0):.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Max Consec Wins</div>
      <div class="value neutral">{metrics.get('max_consecutive_wins', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="label">Max Consec Losses</div>
      <div class="value neutral">{metrics.get('max_consecutive_losses', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="label">Winning Trades</div>
      <div class="value positive">{metrics.get('winning_trades', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="label">Losing Trades</div>
      <div class="value negative">{metrics.get('losing_trades', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="label">Gross Profit</div>
      <div class="value positive">{metrics.get('gross_profit', 0):,.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Gross Loss</div>
      <div class="value negative">{metrics.get('gross_loss', 0):,.4f}</div>
    </div>
    <div class="metric-card">
      <div class="label">Avg Trade</div>
      <div class="value neutral">{metrics.get('avg_trade', 0):.4f}%</div>
    </div>
  </div>

  <h2>Trades Log</h2>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Direction</th>
        <th>Entry Price</th>
        <th>Exit Price</th>
        <th>PnL</th>
        <th>Return %</th>
        <th>Result</th>
      </tr>
    </thead>
    <tbody>
      {self._generate_trades_table(trades)}
    </tbody>
  </table>

  <div class="footer">
    Generated by Trading Strategy AI Platform | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} |
    <a href="https://github.com/crazycompanyinc/trading-strategy-ai-platform" style="color: #58a6ff;">View on GitHub</a>
  </div>
</div>

<script>
  // Equity Curve
  const equityData = {equity_json};
  new Chart(document.getElementById('equityChart'), {{
    type: 'line',
    data: {{
      labels: equityData.map((_, i) => i),
      datasets: [{{
        label: 'Equity',
        data: equityData,
        borderColor: '#58a6ff',
        backgroundColor: 'rgba(88, 166, 255, 0.1)',
        fill: true,
        tension: 0.1,
        pointRadius: 0
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ labels: {{ color: '#c9d1d9' }} }},
        tooltip: {{ mode: 'index', intersect: false }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }},
        y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }}
      }}
    }}
  }});

  // Monthly Returns
  const monthlyData = {monthly_json};
  new Chart(document.getElementById('monthlyChart'), {{
    type: 'bar',
    data: {{
      labels: monthlyData.map(m => m.month),
      datasets: [{{
        label: 'Return %',
        data: monthlyData.map(m => m.return),
        backgroundColor: monthlyData.map(m => m.return >= 0 ? '#3fb950' : '#f85149')
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ labels: {{ color: '#c9d1d9' }} }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }},
        y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }}
      }}
    }}
  }});
</script>
</body>
</html>"""

    def _generate_trades_table(self, trades: list) -> str:
        rows = []
        for i, t in enumerate(trades[:100]):  # Limit to 100 rows
            result_class = "positive" if t.get("is_win", False) else "negative"
            result_text = "WIN" if t.get("is_win", False) else "LOSS"
            rows.append(f"""      <tr>
        <td>{i + 1}</td>
        <td>{t.get('direction', '').upper()}</td>
        <td>{t.get('entry_price', 0):.6f}</td>
        <td>{t.get('exit_price', 0):.6f}</td>
        <td class="{result_class}">{t.get('pnl', 0):.4f}</td>
        <td class="{result_class}">{t.get('return_pct', 0):.4f}%</td>
        <td class="{result_class}">{result_text}</td>
      </tr>""")
        return "\n".join(rows) if rows else '<tr><td colspan="7">No trades</td></tr>'

    def _monthly_returns(self, trades: list) -> list:
        """Calculate monthly returns from trades."""
        from collections import defaultdict
        monthly = defaultdict(float)
        for t in trades:
            date_str = t.get("exit_date", "")
            if date_str:
                try:
                    month_key = date_str[:7]  # YYYY-MM
                    monthly[month_key] += t.get("return_pct", 0)
                except (ValueError, TypeError):
                    pass
        
        result = []
        for month in sorted(monthly.keys()):
            result.append({"month": month, "return": round(monthly[month], 4)})
        return result
