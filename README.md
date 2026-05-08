# Trading Strategy AI Platform

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/crazycompanyinc/trading-strategy-ai-platform?style=social)](https://github.com/crazycompanyinc/trading-strategy-ai-platform)

AI-powered desktop platform for trading strategy research via natural language. Describe your strategy in plain English — the AI parses it, generates a backtestable configuration, runs the backtest, and delivers performance metrics.

## Features

- **Natural Language Strategy Parser** — Describe strategies in any language, get structured JSON back
- **Universal Strategy Support** — ICT concepts, price action, indicators, ML-based signals
- **Backtesting Engine** — 10+ years of historical data, multiple timeframes
- **Risk Management** — Position sizing, max drawdown, Kelly Criterion
- **20+ Performance Metrics** — Sharpe, Sortino, Calmar, Win Rate, Profit Factor, and more
- **Walk-Forward Analysis** — Prevent overfitting with out-of-sample validation
- **Genetic Optimization** — Parameter optimization with genetic algorithms
- **MT5 Integration** — Generate Expert Advisors for MetaTrader 5

## Quick Start

```bash
git clone https://github.com/crazycompanyinc/trading-strategy-ai-platform.git
cd trading-strategy-ai-platform
pip install -r requirements.txt
python main.py
```

## Strategy Examples

```
"Enter long when price breaks above the 20 EMA on the 4H chart,
with RSI above 50, and place stop loss at the recent swing low.
Take profit at 2:1 risk-reward ratio."
```

The platform converts this into a structured strategy configuration, runs the backtest, and returns:

```json
{
  "total_return": "47.3%",
  "sharpe_ratio": 1.82,
  "max_drawdown": "12.1%",
  "win_rate": "58.4%",
  "profit_factor": 1.67,
  "total_trades": 342
}
```

## Architecture

```
src/
├── parser/          # LLM-based natural language strategy parser
├── backtester/      # Event-driven backtesting engine
├── signals/         # Signal generation (ICT, indicators, ML)
├── risk/            # Risk management module
├── optimization/    # Genetic algorithm + Walk-Forward
├── mt5/             # MetaTrader 5 EA generation
└── metrics/         # Performance metrics calculation
```

## Roadmap

- [x] Universal strategy parser via LLM
- [x] Position-aware exit logic (CLOSE_LONG/CLOSE_SHORT)
- [x] Walk-Forward Analysis
- [ ] Multi-asset portfolio backtesting
- [ ] Live paper trading mode
- [ ] Web dashboard (Next.js frontend)

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Built by [ZOO](https://zoo.dev) — AI-Native Technology Company
